"""Encrypted archive boundaries: authenticity, bounded IO and failure safety."""
import base64
import hashlib
import io
from pathlib import Path
import runpy
from types import SimpleNamespace
import sys

import pytest
from cryptography.exceptions import InvalidTag

from experiments import archive_cloud_media as archive

KEY = bytes(range(32))  # Public test fixture, never a production key.


class BoundedBody(io.BytesIO):
    def read(self, size=-1):
        assert 0 <= size <= archive.CHUNK, "Download must be streamed"
        return super().read(size)


class FakeR2:
    def __init__(self, failure=None):
        self.objects = {}
        self.failure = failure
        self.upload_path = None
        self.deleted = []

    def upload_file(self, path, bucket, key, ExtraArgs):
        self.upload_path = Path(path)
        data = self.upload_path.read_bytes()
        assert data.startswith(archive.MAGIC)
        assert ExtraArgs["ContentType"] == "application/octet-stream"
        self.objects[key] = data
        if self.failure == "upload":
            raise OSError("Upload interrupted after remote bytes arrived")

    def get_object(self, Bucket, Key):
        data = self.objects[Key]
        if self.failure == "download":
            raise OSError("Download interrupted")
        if self.failure == "truncated":
            data = data[:-1]
        if self.failure == "tampered":
            data = data[:archive.HEADER.size] + bytes([data[archive.HEADER.size] ^ 1]) + data[archive.HEADER.size + 1:]
        return {"Body": BoundedBody(data)}

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)
        del self.objects[Key]


def source(tmp_path, data=b"PRIVATE MEDIA\0" * 37):
    path = tmp_path / "original.mp4"
    path.write_bytes(data)
    return {"path": path.name, "sha256": hashlib.sha256(data).hexdigest()}, data


@pytest.mark.parametrize("data", [b"", b"a", b"private film frames\0" * 37])
def test_roundtrip_streams_authenticated_ciphertext_and_never_overwrites(tmp_path, monkeypatch, data):
    monkeypatch.setattr(archive, "CHUNK", 7)  # Header, payload and tag cross boundaries.
    item, data = source(tmp_path, data)
    client = FakeR2()
    receipt = archive.archive_one(tmp_path, item, client, "bucket", KEY)
    assert receipt["bytes"] == len(data)
    assert receipt["cipherBytes"] == len(data) + archive.HEADER.size + 16
    assert hashlib.sha256(client.objects[receipt["key"]]).hexdigest() == receipt["cipherSha256"]
    if len(data) > 20:
        assert data not in client.objects[receipt["key"]]
    assert not client.upload_path.exists()
    result = archive.restore_one(tmp_path, "restored.mp4", receipt, client, "bucket", KEY)
    assert result["verified"] and (tmp_path / "restored.mp4").read_bytes() == data
    assert (tmp_path / "restored.mp4").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        archive.restore_one(tmp_path, "restored.mp4", receipt, client, "bucket", KEY)
    assert (tmp_path / "restored.mp4").read_bytes() == data
    assert not list(tmp_path.glob(".archive-restore-*"))


@pytest.mark.parametrize("change", ["payload", "tag", "header", "key", "truncated", "extra", "cipherhash", "wrong-secret"])
def test_tamper_never_publishes_plaintext_or_leaves_partial_restore(tmp_path, change):
    item, _ = source(tmp_path)
    client = FakeR2()
    receipt = archive.archive_one(tmp_path, item, client, "bucket", KEY)
    blob = client.objects[receipt["key"]]
    key = KEY
    if change in {"payload", "tag", "header"}:
        offset = {"payload": archive.HEADER.size + 3, "tag": len(blob) - 1, "header": 10}[change]
        blob = blob[:offset] + bytes([blob[offset] ^ 1]) + blob[offset + 1:]
        # Even an attacker able to replace the public checksum cannot forge GCM.
        receipt["cipherSha256"] = hashlib.sha256(blob).hexdigest()
    elif change == "key":
        receipt["key"] = archive.PREFIX + "f" * 32 + ".aesgcm"
    elif change == "truncated":
        blob = blob[:-8]
    elif change == "extra":
        blob += b"unexpected"
    elif change == "cipherhash":
        receipt["cipherSha256"] = "0" * 64
    elif change == "wrong-secret":
        key = b"X" * 32
    client.objects[receipt["key"]] = blob
    with pytest.raises((ValueError, InvalidTag)):
        archive.restore_one(tmp_path, "restored.mp4", receipt, client, "bucket", key)
    assert not (tmp_path / "restored.mp4").exists()
    assert not list(tmp_path.glob(".archive-restore-*"))


@pytest.mark.parametrize("failure", ["upload", "download", "truncated", "tampered"])
def test_partial_archive_failure_removes_its_ciphertext_and_preserves_source(tmp_path, failure):
    item, original = source(tmp_path)
    client = FakeR2(failure)
    with pytest.raises(RuntimeError, match="verification failed"):
        archive.archive_one(tmp_path, item, client, "bucket", KEY)
    assert not client.objects and len(client.deleted) == 1
    assert not client.upload_path.exists()
    assert (tmp_path / item["path"]).read_bytes() == original


def test_hash_mismatch_never_reaches_upload(tmp_path):
    item, _ = source(tmp_path)
    item["sha256"] = "0" * 64
    client = FakeR2()
    with pytest.raises(ValueError, match="SHA256"):
        archive.archive_one(tmp_path, item, client, "bucket", KEY)
    assert not client.objects and client.upload_path is None


@pytest.mark.parametrize("path", ["", "/absolute", "../secret", "a/../secret", "a/./b", "a//b", "a/", "a\\b", "C:/secret", "a\0b"])
def test_unsafe_paths_rejected_before_io(path):
    with pytest.raises(ValueError):
        archive.validate_inputs([{"path": path, "sha256": "a" * 64}])


def test_symlink_source_parent_and_restore_destination_are_rejected(tmp_path):
    item, data = source(tmp_path)
    (tmp_path / "alias.mp4").symlink_to(tmp_path / item["path"])
    (tmp_path / "alias-dir").symlink_to(tmp_path, target_is_directory=True)
    client = FakeR2()
    for path in ["alias.mp4", "alias-dir/original.mp4"]:
        with pytest.raises(OSError):
            archive.archive_one(tmp_path, {**item, "path": path}, client, "bucket", KEY)
    receipt = archive.archive_one(tmp_path, item, client, "bucket", KEY)
    with pytest.raises(OSError):
        archive.restore_one(tmp_path, "alias-dir/restored.mp4", receipt, client, "bucket", KEY)
    (tmp_path / "restored.mp4").symlink_to(tmp_path / item["path"])
    with pytest.raises(FileExistsError):
        archive.restore_one(tmp_path, "restored.mp4", receipt, client, "bucket", KEY)
    assert (tmp_path / item["path"]).read_bytes() == data


def test_destination_created_during_download_is_never_overwritten(tmp_path, monkeypatch):
    item, _ = source(tmp_path)
    client = FakeR2()
    receipt = archive.archive_one(tmp_path, item, client, "bucket", KEY)
    original = client.get_object

    def raced_get(**kwargs):
        (tmp_path / "restored.mp4").write_bytes(b"other writer")
        return original(**kwargs)

    monkeypatch.setattr(client, "get_object", raced_get)
    with pytest.raises(FileExistsError):
        archive.restore_one(tmp_path, "restored.mp4", receipt, client, "bucket", KEY)
    assert (tmp_path / "restored.mp4").read_bytes() == b"other writer"
    assert not list(tmp_path.glob(".archive-restore-*"))


def test_restore_copy_failure_removes_new_destination(tmp_path, monkeypatch):
    item, _ = source(tmp_path)
    client = FakeR2()
    receipt = archive.archive_one(tmp_path, item, client, "bucket", KEY)

    def interrupted_sync(fd):
        raise OSError("Disk became unavailable during restore")

    monkeypatch.setattr(archive.os, "fsync", interrupted_sync)
    with pytest.raises(OSError, match="unavailable"):
        archive.restore_one(tmp_path, "restored.mp4", receipt, client, "bucket", KEY)
    assert not (tmp_path / "restored.mp4").exists()
    assert (tmp_path / item["path"]).exists()


def test_secret_creation_is_nonoverwriting_and_never_logs_key(monkeypatch, capsys):
    calls = []

    def create(name, contents, *, allow_existing):
        value = contents[archive.KEY_ENV]
        assert len(base64.b64decode(value)) == 32
        assert name == archive.SECRET_NAME and allow_existing is False
        calls.append(value)
        if len(calls) == 2:
            raise RuntimeError("Simulated SDK payload: " + value)

    monkeypatch.setitem(sys.modules, "modal", SimpleNamespace(Secret=SimpleNamespace(objects=SimpleNamespace(create=create))))
    assert archive.initialize_secret() == {"secret": archive.SECRET_NAME, "created": True}
    with pytest.raises(RuntimeError, match="never overwritten") as caught:
        archive.initialize_secret()
    assert all(value not in str(caught.value) for value in calls)
    assert not capsys.readouterr().out and caught.value.__suppress_context__


def test_duplicate_inputs_and_non_aes256_keys_fail(tmp_path):
    item, _ = source(tmp_path)
    with pytest.raises(ValueError, match="Duplicate"):
        archive.validate_inputs([item, item])
    with pytest.raises(ValueError, match="32-byte"):
        archive.archive_one(tmp_path, item, FakeR2(), "bucket", b"x" * 16)


def test_direct_script_workers_serialize_without_native_crypto_globals():
    serialization = pytest.importorskip("modal._serialization")
    namespace = runpy.run_path(archive.__file__, run_name="archive_cli_serialization_check")
    for name in ["remote_archive", "remote_restore"]:
        assert serialization.serialize(namespace[name])
