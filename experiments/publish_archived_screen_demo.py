"""Publish approved historical screen films without claiming an editable project.

The private manifest contains entries with file, example, source, approval and
publicProvenance fields. Only the approved MP4 and explicitly public metadata
are sent to the publishing container. No historical traces or project files
are uploaded. Usage: python -m experiments.publish_archived_screen_demo
--manifest reviewed-archives.json --output-dir published
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

ARCHIVE_KIND = "archived screen demo created with Video Use"
ARCHIVE_SCOPE = "Published film and reconstructed starter prompt; editable project not included"
EXAMPLE_FIELDS = {"id", "title", "category", "description", "prompt", "promptKind", "promptSource",
                  "duration", "orientation", "technique", "audiences", "useCases"}
SOURCE_FIELDS = {"id", "kind", "sourceRun", "production", "promptSource", "sourceArchiveScope"}
APPROVAL_FIELDS = {"id", "approved", "sha256", "review", "posterTime"}


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def validate_entry(entry: dict) -> dict:
    """Fail before upload when the approval, public contract or bytes differ."""
    example, source, approval = (entry[key] for key in ("example", "source", "approval"))
    if set(example) != EXAMPLE_FIELDS or set(source) != SOURCE_FIELDS or set(approval) != APPROVAL_FIELDS:
        raise ValueError("Only the bounded public archive fields are accepted")
    if not re.fullmatch(r"screen-demo-[a-z0-9-]+", example["id"]):
        raise ValueError("Use the archived screen-demo namespace")
    if source["id"] != example["id"] or approval["id"] != example["id"] or approval["approved"] is not True:
        raise ValueError("Explicit approval must identify this archive")
    if not re.fullmatch(r"[a-f0-9]{64}", approval["sha256"]):
        raise ValueError("Approval must bind the exact film SHA256")
    if not isinstance(approval["review"], str) or len(approval["review"].strip()) < 80:
        raise ValueError("Describe the actual review and archive limitations")
    duration, moment = example["duration"], approval["posterTime"]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in (duration, moment)) or not 0 <= moment < duration:
        raise ValueError("Choose a finite poster time inside the film")
    if example["promptKind"] != "Starter prompt" or source["kind"] != ARCHIVE_KIND or source["sourceArchiveScope"] != ARCHIVE_SCOPE:
        raise ValueError("This archive has a reconstructed starter and no editable source")
    if example["category"] != "Video Edits" or example["technique"] != "video-editing":
        raise ValueError("An archived screen film belongs to Video Edits")
    if source["promptSource"] != example["promptSource"] or len(example["promptSource"].strip()) < 25:
        raise ValueError("Prompt provenance must be explicit and consistent")
    if len(example["prompt"].strip()) < 25 or len(source["production"].strip()) < 40 or not source["sourceRun"]:
        raise ValueError("Preserve the prompt and historical creation evidence")
    public = {key: entry[key] for key in ("example", "source", "approval", "publicProvenance")}
    serialized = json.dumps(public, ensure_ascii=False)
    if re.search(r"/Users/|/home/|-----BEGIN .*PRIVATE KEY|(?:sk-proj-|sk-ant-api|AKIA)[A-Za-z0-9_-]{16,}", serialized):
        raise ValueError("Private paths or credential-like text cannot be published")
    return public


def publish(entries: list[dict]) -> list[dict]:
    import os
    import subprocess
    import tempfile
    import urllib.request
    import boto3

    def command(args: list[str]) -> bytes:
        result = subprocess.run(args, capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError("Archive media check failed: " + result.stderr.decode(errors="replace")[-1000:])
        return result.stdout

    def verify(url: str, expected: str, ranged: bool = False) -> dict:
        headers = {"User-Agent": "Mozilla/5.0 VideoUseArchivePublisher/1.0"}
        checksum, size = hashlib.sha256(), 0
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
            for part in iter(lambda: response.read(1024 * 1024), b""):
                checksum.update(part)
                size += len(part)
        if checksum.hexdigest() != expected:
            raise ValueError("Public asset differs from the approved publication")
        result = {"sha256": expected, "bytes": size}
        if ranged:
            with urllib.request.urlopen(urllib.request.Request(url, headers={**headers, "Range": "bytes=0-1023"}), timeout=30) as response:
                if response.status != 206:
                    raise ValueError("Public film must support byte-range playback")
                response.read(1024)
                result["rangeStatus"] = response.status
        return result

    # Validate every movie before the first external write.
    for index, entry in enumerate(entries):
        validate_entry(entry)
        final = Path(f"/reviewed/{index}.mp4")
        if digest(final) != entry["approval"]["sha256"]:
            raise ValueError("Archive movie changed after approval")
    client = boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                          aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
    receipts = []
    for index, entry in enumerate(entries):
        example, source, approval = (entry[key].copy() for key in ("example", "source", "approval"))
        final = Path(f"/reviewed/{index}.mp4")
        probe = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(final)]))
        streams = probe["streams"]
        video = [stream for stream in streams if stream["codec_type"] == "video"]
        audio = [stream for stream in streams if stream["codec_type"] == "audio"]
        if len(video) != 1 or audio or video[0]["codec_name"] != "h264":
            raise ValueError("These approved archive deliveries must be silent H264 films")
        if (video[0]["width"], video[0]["height"]) != (1920, 1080) or abs(float(probe["format"]["duration"]) - example["duration"]) > 0.05:
            raise ValueError("Media dimensions or duration differ from the reviewed metadata")
        command(["ffmpeg", "-v", "error", "-xerror", "-i", str(final), "-f", "null", "-"])
        release = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:12]
        prefix = f"website/archived-screen-demos/20261004/{example['id']}-{approval['sha256'][:12]}-{release}"
        base = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/") + "/" + prefix
        with tempfile.TemporaryDirectory(prefix="archive-publish-") as temporary:
            staging = Path(temporary)
            poster = staging / "poster.jpg"
            command(["ffmpeg", "-v", "error", "-ss", str(approval["posterTime"]), "-i", str(final), "-frames:v", "1", "-q:v", "2", str(poster)])
            (staging / "prompt.txt").write_text(example["prompt"] + "\n", encoding="utf-8")
            (staging / "review.md").write_text("# " + example["title"] + "\n\n" + approval["review"] + "\n\n" + source["sourceArchiveScope"] + ".\n\nReviewed movie SHA256: `" + approval["sha256"] + "`\n", encoding="utf-8")
            (staging / "provenance.json").write_text(json.dumps(entry["publicProvenance"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (staging / "verification.json").write_text(json.dumps({"sha256": approval["sha256"], "duration": float(probe["format"]["duration"]), "width": video[0]["width"], "height": video[0]["height"], "fps": video[0]["avg_frame_rate"], "frames": int(video[0]["nb_frames"]), "audioStreams": 0, "fullDecodePass": True, "posterTime": approval["posterTime"], "visualReview": approval["review"]}, indent=2) + "\n")
            files = [(final, "final.mp4", "video/mp4"), (poster, "poster.jpg", "image/jpeg"),
                     (staging / "prompt.txt", "prompt.txt", "text/plain; charset=utf-8"),
                     (staging / "review.md", "review.md", "text/markdown; charset=utf-8"),
                     (staging / "provenance.json", "provenance.json", "application/json"),
                     (staging / "verification.json", "verification.json", "application/json")]
            hashes = {name: digest(path) for path, name, _ in files}
            for path, name, mime in files:
                client.upload_file(str(path), os.environ["R2_BUCKET"], prefix + "/" + name,
                                   ExtraArgs={"ContentType": mime, "CacheControl": "public, max-age=31536000, immutable"})
            public_checks = {name: verify(base + "/" + name, checksum, name == "final.mp4") for name, checksum in hashes.items()}
        example.update(video=base + "/final.mp4", poster=base + "/poster.jpg", reviewUrl=base + "/review.md")
        source.update(storage="Cloudflare R2", websiteSha256=approval["sha256"], promptUrl=base + "/prompt.txt",
                      reviewUrl=base + "/review.md", provenanceUrl=base + "/provenance.json", verificationUrl=base + "/verification.json",
                      websiteAssets=[{"field": field, "url": example[field]} for field in ("video", "poster")])
        receipts.append({"example": example, "source": source, "approval": {key: approval[key] for key in ("id", "approved", "sha256", "review")},
                         "assets": {name: base + "/" + name for name in hashes}, "hashes": hashes,
                         "publicCheck": public_checks["final.mp4"], "assetChecks": public_checks})
    return receipts


def main() -> None:
    import modal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    entries = json.loads(args.manifest.read_text())["entries"]
    if not 1 <= len(entries) <= 3 or len({entry["example"]["id"] for entry in entries}) != len(entries):
        raise ValueError("Publish one to three distinct approved archives at a time")
    image = modal.Image.debian_slim(python_version="3.12").apt_install("ffmpeg").pip_install("boto3")
    public_entries = []
    for index, entry in enumerate(entries):
        public_entries.append(validate_entry(entry))
        final = Path(entry["file"])
        if final.stat().st_size > 100_000_000 or digest(final) != entry["approval"]["sha256"]:
            raise ValueError("Local archive movie exceeds the bounded size or changed after approval")
        image = image.add_local_file(final, f"/reviewed/{index}.mp4")
    app = modal.App("video-use-reviewed-screen-archive-publisher")
    worker = app.function(image=image, cpu=2, memory=2048, timeout=900, serialized=True,
                          secrets=[modal.Secret.from_name("video-use-r2")])(publish)
    with modal.enable_output(), app.run():
        receipts = worker.remote(public_entries)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for receipt in receipts:
        target = args.output_dir / (receipt["example"]["id"] + ".json")
        target.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"published": receipt["example"]["id"], "verified": receipt["publicCheck"], "receipt": str(target)}))


if __name__ == "__main__":
    main()
