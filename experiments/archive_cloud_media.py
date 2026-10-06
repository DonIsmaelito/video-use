"""Archive explicit Modal Volume files as authenticated ciphertext in R2.

Usage (only JSON receipts reach the local machine):
  python experiments/archive_cloud_media.py init-key
  python experiments/archive_cloud_media.py archive --inputs inputs.json --output receipts.json
  python experiments/archive_cloud_media.py restore --receipt receipt.json --destination new/file.mp4 --output restored.json

inputs.json is [{"path": "relative/volume/file.mp4", "sha256": "<64 lowercase hex>"}].
Restore takes one receipt from the returned receipts list; destination parents
must already exist in the Volume. No input is deleted. Raw video is processed
only in the cloud workers. The bucket may be public: uploaded bytes are always
AES-256-GCM ciphertext, never plaintext. Keep the durable Modal Secret: losing
it makes these archives unrecoverable. Never rotate it by overwriting its name.

Format v1: magic (8), nonce (12), plaintext length (8, big endian), plaintext
SHA256 (32), ciphertext (length), GCM tag (16). The complete 60-byte header and
R2 object key are authenticated as AAD. Decryption succeeds only after tag,
plaintext hash/size and ciphertext hash/size verification. Restore writes a
cloud temporary file, then creates the destination with O_EXCL only after
authentication. Failed copies remove their incomplete destination. Modal
Volumes do not support hard links, so readers should wait for the success
receipt rather than treating destination visibility as completion.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import tempfile
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

VOLUME_NAME = "video-use-useful-library-20261003"
SECRET_NAME = "video-use-source-archive-v1"
KEY_ENV = "VIDEO_USE_SOURCE_ARCHIVE_KEY_B64"
FORMAT = "video-use-source-archive-aes256gcm-v1"
PREFIX = "private/source-archive/v1/"
MAGIC = b"VUARCH1\0"
HEADER = struct.Struct(">8s12sQ32s")
CHUNK = 1024 * 1024
MAX_BYTES = (1 << 36) - 32  # GCM's per-message plaintext limit.


def relative_path(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or "\\" in value or ":" in value or "\0" in value:
        raise ValueError("Expected a relative POSIX path")
    parts = tuple(value.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Empty, absolute and traversal paths are forbidden")
    return parts


def sha256_value(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA256")
    return value


def validate_inputs(items: list) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise ValueError("An explicit nonempty input list is required")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("Each input requires only path and sha256")
        relative_path(item["path"])
        sha256_value(item["sha256"])
        if item["path"] in seen:
            raise ValueError("Duplicate source path")
        seen.add(item["path"])
    return items


@contextmanager
def parent_fd(root: Path, relative: str):
    """Walk pinned directory descriptors; symlinks are never followed."""
    parts = relative_path(relative)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd, parts[-1]
    finally:
        os.close(fd)


@contextmanager
def source_file(root: Path, relative: str):
    with parent_fd(root, relative) as (directory, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Source must be a regular file")
            yield stream


def archive_key() -> bytes:
    try:
        key = base64.b64decode(os.environ[KEY_ENV], validate=True)
    except (KeyError, ValueError):
        raise ValueError("Archive secret missing or invalid") from None
    if len(key) != 32:
        raise ValueError("Archive secret must contain 32 bytes")
    return key


def encrypt(source, output, key: bytes, object_key: str, expected_sha: str) -> dict:
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    size = os.fstat(source.fileno()).st_size
    if not 0 <= size <= MAX_BYTES:
        raise ValueError("Source exceeds the GCM message limit")
    header = HEADER.pack(MAGIC, os.urandom(12), size, bytes.fromhex(sha256_value(expected_sha)))
    cipher = Cipher(algorithms.AES(key), modes.GCM(header[8:20])).encryptor()
    cipher.authenticate_additional_data(header + object_key.encode("utf-8"))
    plain_hash, cipher_hash = hashlib.sha256(), hashlib.sha256()
    count = 0

    def emit(data):
        output.write(data)
        cipher_hash.update(data)

    emit(header)
    while block := source.read(CHUNK):
        count += len(block)
        if count > size:
            raise ValueError("Source changed while archiving")
        plain_hash.update(block)
        emit(cipher.update(block))
    if count != size or plain_hash.hexdigest() != expected_sha:
        raise ValueError("Source size or SHA256 differs from the explicit input")
    emit(cipher.finalize())
    emit(cipher.tag)
    return {"key": object_key, "sha256": expected_sha, "bytes": size,
            "cipherSha256": cipher_hash.hexdigest(), "cipherBytes": size + HEADER.size + 16,
            "format": FORMAT, "keySecret": SECRET_NAME}


def validate_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict) or receipt.get("format") != FORMAT or receipt.get("keySecret") != SECRET_NAME:
        raise ValueError("Unsupported archive format or key identity")
    if not re.fullmatch(re.escape(PREFIX) + r"[0-9a-f]{32}\.aesgcm", receipt.get("key", "")):
        raise ValueError("Invalid archive object key")
    sha256_value(receipt.get("sha256"))
    sha256_value(receipt.get("cipherSha256"))
    size = receipt.get("bytes")
    if type(size) is not int or not 0 <= size <= MAX_BYTES:
        raise ValueError("Invalid plaintext size")
    if type(receipt.get("cipherBytes")) is not int or receipt["cipherBytes"] != size + HEADER.size + 16:
        raise ValueError("Invalid ciphertext size")
    return receipt


def decrypt_verify(body, receipt: dict, key: bytes, output=None) -> None:
    """Consume bounded reads; callers must not expose output before return."""
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    validate_receipt(receipt)
    cipher_hash, plain_hash = hashlib.sha256(), hashlib.sha256()

    def read_exact(size):
        pieces, remaining = [], size
        while remaining:
            block = body.read(min(remaining, CHUNK))
            if not block:
                raise ValueError("Truncated archive")
            remaining -= len(block)
            pieces.append(block)
            cipher_hash.update(block)
        return b"".join(pieces)

    header = read_exact(HEADER.size)
    magic, nonce, size, digest = HEADER.unpack(header)
    if magic != MAGIC or size != receipt["bytes"] or digest.hex() != receipt["sha256"]:
        raise ValueError("Archive header does not match receipt")
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).decryptor()
    cipher.authenticate_additional_data(header + receipt["key"].encode("utf-8"))
    remaining = size
    while remaining:
        block = read_exact(min(remaining, CHUNK))
        remaining -= len(block)
        plain = cipher.update(block)
        plain_hash.update(plain)
        if output is not None:
            output.write(plain)
    cipher.finalize_with_tag(read_exact(16))
    if body.read(1):
        raise ValueError("Unexpected trailing archive bytes")
    if plain_hash.hexdigest() != receipt["sha256"] or cipher_hash.hexdigest() != receipt["cipherSha256"]:
        raise ValueError("Archive hash verification failed")


def archive_one(root: Path, item: dict, client, bucket: str, key: bytes) -> dict:
    validate_inputs([item])
    object_key = PREFIX + uuid.uuid4().hex + ".aesgcm"
    with tempfile.TemporaryDirectory(prefix="encrypted-source-") as temporary:
        ciphertext = Path(temporary) / "source.aesgcm"
        with source_file(root, item["path"]) as source, ciphertext.open("xb") as output:
            receipt = encrypt(source, output, key, object_key, item["sha256"])
        try:
            client.upload_file(str(ciphertext), bucket, object_key,
                               ExtraArgs={"ContentType": "application/octet-stream", "CacheControl": "private, no-store"})
            response = client.get_object(Bucket=bucket, Key=object_key)
            try:
                decrypt_verify(response["Body"], receipt, key)
            finally:
                response["Body"].close()
        except Exception:
            # The key is unique to this attempted upload. Never leave a success
            # receipt for an incomplete/unverified object; cleanup only our key.
            try:
                client.delete_object(Bucket=bucket, Key=object_key)
            except Exception:
                raise RuntimeError("Archive failed; ciphertext cleanup also failed") from None
            raise RuntimeError("Archive upload or authenticated download verification failed") from None
    return {**receipt, "path": item["path"]}


def restore_one(root: Path, destination: str, receipt: dict, client, bucket: str, key: bytes) -> dict:
    validate_receipt(receipt)
    with parent_fd(root, destination) as (directory, name):
        try:
            os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError("Restore destination already exists")
        with tempfile.TemporaryFile(mode="w+b") as verified:
            response = client.get_object(Bucket=bucket, Key=receipt["key"])
            try:
                decrypt_verify(response["Body"], receipt, key, verified)
            finally:
                response["Body"].close()
            verified.seek(0)
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            identity = os.fstat(fd)
            try:
                with os.fdopen(fd, "wb") as output:
                    while block := verified.read(CHUNK):
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
                current = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
                    raise FileExistsError("Restore destination changed during copy")
            except Exception:
                # Remove only the file this operation created, never a racing
                # replacement written by another process.
                try:
                    current = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                        os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    pass
                raise
    return {"destination": destination, "sha256": receipt["sha256"], "bytes": receipt["bytes"], "verified": True}


def r2_client():
    import boto3
    return boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")


def cloud_archive(items: list) -> dict:
    validate_inputs(items)
    client, bucket, key = r2_client(), os.environ["R2_BUCKET"], archive_key()
    result = {"receipts": [], "failures": []}
    for item in items:
        try:
            result["receipts"].append(archive_one(Path("/results"), item, client, bucket, key))
        except Exception as error:
            result["failures"].append({"path": item["path"], "error": type(error).__name__})
    return result


def cloud_restore(receipt: dict, destination: str) -> dict:
    import modal
    result = restore_one(Path("/results"), destination, receipt, r2_client(), os.environ["R2_BUCKET"], archive_key())
    modal.Volume.from_name(VOLUME_NAME).commit()
    return result


def remote_archive(items: list) -> dict:
    # Import inside the worker: direct-script CLI functions would otherwise
    # pickle native cipher/Struct globals from __main__.
    from experiments.archive_cloud_media import cloud_archive
    return cloud_archive(items)


def remote_restore(receipt: dict, destination: str) -> dict:
    from experiments.archive_cloud_media import cloud_restore
    return cloud_restore(receipt, destination)


def initialize_secret() -> dict:
    """Key exists briefly in process RAM and durably only in Modal Secret."""
    import modal
    contents = {KEY_ENV: base64.b64encode(os.urandom(32)).decode("ascii")}
    try:
        modal.Secret.objects.create(SECRET_NAME, contents, allow_existing=False)
    except Exception:
        # Do not render SDK exception/request payloads containing the key.
        raise RuntimeError("Archive secret was not created; check whether it already exists. Existing secrets are never overwritten.") from None
    finally:
        contents.clear()
    return {"secret": SECRET_NAME, "created": True}


def main() -> None:
    import modal
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-key")
    archive_parser = commands.add_parser("archive")
    archive_parser.add_argument("--inputs", type=Path, required=True)
    archive_parser.add_argument("--output", type=Path, required=True)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--receipt", type=Path, required=True)
    restore_parser.add_argument("--destination", required=True)
    restore_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init-key":
        print(json.dumps(initialize_secret()))
        return
    if args.command == "archive":
        payload = validate_inputs(json.loads(args.inputs.read_text()))
    else:
        payload = validate_receipt(json.loads(args.receipt.read_text()))
        relative_path(args.destination)
    app = modal.App("video-use-encrypted-source-archive")
    image = (modal.Image.debian_slim(python_version=f"{sys.version_info.major}.{sys.version_info.minor}")
             .pip_install("boto3==1.42.30", "cryptography==50.0.1")
             .add_local_file(str(Path(__file__).resolve()), "/root/experiments/archive_cloud_media.py"))
    function = remote_archive if args.command == "archive" else remote_restore
    worker = app.function(image=image, cpu=1, memory=2048, timeout=3600, serialized=True,
                          volumes={"/results": modal.Volume.from_name(VOLUME_NAME)},
                          secrets=[modal.Secret.from_name("video-use-r2"), modal.Secret.from_name(SECRET_NAME)])(function)
    with modal.enable_output(), app.run():
        result = worker.remote(payload) if args.command == "archive" else worker.remote(payload, args.destination)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"operation": args.command, "receiptFile": str(args.output), "failures": len(result.get("failures", []))}))
    if result.get("failures"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
