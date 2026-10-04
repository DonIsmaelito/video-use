"""Publish only an explicitly reviewed, hash-bound Video Use production attempt.

The producer has no publishing credentials. This separate process receives one
review record after visual inspection; it never discovers or approves videos.
Usage: uv run --extra mcp python -m experiments.publish_useful_video --approval review.json --output receipt.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

VOLUME_NAME = "video-use-useful-library-20261003"
SAFE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")
SECRET_TEXT = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:sk-proj-|sk-ant-api|sk-|AKIA)[A-Za-z0-9_-]{16,}|\"(?:access_token|refresh_token)\"\s*:\s*\"[^\"]+")
SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss",
                   ".json", ".toml", ".yaml", ".yml", ".txt", ".md", ".svg", ".png", ".jpg", ".jpeg", ".webp",
                   ".woff", ".woff2", ".ttf", ".otf", ".glb", ".gltf", ".obj", ".mtl", ".stl", ".blend",
                   ".sh", ".srt", ".vtt", ".ass", ".csv", ".ipynb"}
DEPENDENCY_LOCK_NAMES = {"requirements.lock", "uv.lock", "poetry.lock", "Pipfile.lock", "yarn.lock"}


def contains_secret(stream) -> bool:
    tail = b""
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        data = tail + chunk
        if SECRET_TEXT.search(data):
            return True
        tail = data[-16384:]
    return False


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(data)
    return result.hexdigest()


def validate_approval(value: dict) -> dict:
    for key in ("batch", "id", "attempt"):
        if not isinstance(value.get(key), str) or not SAFE_ID.fullmatch(value[key]):
            raise ValueError("Invalid review identifier")
    for key in ("sha256", "sourceSha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", value.get(key, "")):
            raise ValueError("Review must identify exact video and editable archive SHA256 values")
    if value.get("approved") is not True or value.get("sourceReviewed") is not True:
        raise ValueError("Both final media and editable source require review")
    if not isinstance(value.get("review"), str) or len(value["review"].strip()) < 80:
        raise ValueError("Record what was visually inspected and any remaining limitations")
    moment = value.get("posterTime")
    if isinstance(moment, bool) or not isinstance(moment, (int, float)) or not math.isfinite(moment) or moment < 0:
        raise ValueError("Choose a finite nonnegative poster time")
    return value


def check_archive(path: Path) -> dict:
    """Refuse private traces, unlicensed raw video bundles and credential files."""
    count = total = 0
    forbidden_parts = {"node_modules", "__pycache__", "downloads", "frames", "verify"}
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            relative = Path(entry.filename)
            if "\\" in entry.filename or re.match(r"^[A-Za-z]:", entry.filename) or relative.is_absolute() or any(part.startswith(".") or part in forbidden_parts for part in relative.parts):
                raise ValueError("Unsafe source archive path")
            is_notice = bool(re.fullmatch(r"(?:.*[-_.])?(?:LICENSE|NOTICE|COPYING)", relative.name, re.IGNORECASE))
            if relative.name in {"auth.json", "credentials.json"} or (relative.suffix.lower() not in SOURCE_SUFFIXES and relative.name not in DEPENDENCY_LOCK_NAMES and not is_notice and relative.name.upper() != "MAKEFILE"):
                raise ValueError("Non-source or private file in source archive: " + str(relative))
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symlink in source archive")
            total += entry.file_size
            count += 1
            if total > 300_000_000 or count > 10000:
                raise ValueError("Source archive exceeds delivery limits")
            with archive.open(entry) as stream:
                if contains_secret(stream):
                    raise ValueError("Possible credential found in source archive")
    return {"files": count, "uncompressedBytes": total, "sha256": digest(path)}


def checked_run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, timeout=300)
    if result.returncode:
        raise RuntimeError("Media preparation failed: " + result.stderr.decode(errors="replace")[-1500:])


def verify_public(url: str, expected: str) -> dict:
    checksum = hashlib.sha256()
    size = 0
    headers = {"User-Agent": "Mozilla/5.0 VideoUseGalleryVerifier/1.0"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                checksum.update(chunk)
                size += len(chunk)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise RuntimeError(f"Public media verification returned HTTP {status}") from None
    if checksum.hexdigest() != expected:
        raise ValueError("Public media differs from the reviewed bytes")
    with urllib.request.urlopen(urllib.request.Request(url, headers={**headers, "Range": "bytes=0-1023"}), timeout=30) as response:
        status = response.status
        response.read(1024)
    if status != 206:
        raise ValueError("Public media does not support byte range playback")
    return {"sha256": expected, "bytes": size, "rangeStatus": status}


def publish(approval: dict) -> dict:
    import boto3
    approval = validate_approval(approval)
    root = Path("/results") / approval["batch"] / approval["id"]
    if approval["attempt"] != "original":
        root = root / "repairs" / approval["attempt"]
    run = json.loads((root / "run.json").read_text())
    brief = json.loads((root / "brief.json").read_text())
    # Public research credits may be corrected after the creative brief ran.
    # The executed prompt remains byte-for-byte unchanged.
    corrections = approval.get("creditCorrections", {})
    allowed_credits = {"sourceRepo", "sourceFile", "license", "licenseUrl", "sourceConcept", "promptSource"}
    if not isinstance(corrections, dict) or not set(corrections).issubset(allowed_credits) or not all(isinstance(value, str) for value in corrections.values()):
        raise ValueError("Only public research credits may be corrected")
    brief.update(corrections)
    audit = run.get("audit", {})
    if not audit.get("technical_pass") or audit.get("missing_handoff_files"):
        raise ValueError("Production has not passed technical and editable handoff checks")
    final = root / "project/edit/final.mp4"
    if digest(final) != approval["sha256"] or audit.get("sha256") != approval["sha256"]:
        raise ValueError("Final media changed after review")
    if approval["posterTime"] >= brief["duration"]:
        raise ValueError("Poster time lies beyond the video")
    archive = root / "source.zip"
    archive_evidence = check_archive(archive)
    if archive_evidence["sha256"] != approval["sourceSha256"] or audit.get("archive", {}).get("sha256") != approval["sourceSha256"]:
        raise ValueError("Editable source changed after review")
    qa = json.loads((root / "qa/qa.json").read_text())
    provenance = json.loads((root / "project/edit/provenance.json").read_text())
    client = boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                          aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
    bucket = os.environ["R2_BUCKET"]
    release = hashlib.sha256(json.dumps(approval, sort_keys=True).encode()).hexdigest()[:8]
    prefix = f"website/useful-workflows/20261003/{approval['id']}-{approval['sha256'][:12]}-{release}"
    base = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/") + "/" + prefix
    with tempfile.TemporaryDirectory(prefix="reviewed-publish-") as temporary:
        staging = Path(temporary)
        poster = staging / "poster.jpg"
        checked_run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(approval["posterTime"]), "-i", str(final), "-frames:v", "1", "-q:v", "2", str(poster)])
        published_review = staging / "review.md"
        published_review.write_text("# Publication review\n\n" + approval["review"].strip() + "\n\nReviewed video SHA256: " + approval["sha256"] + "\n\n## Production review\n\n" + (root / "project/edit/review.md").read_text())
        verification = staging / "verification.json"
        verification.write_text(json.dumps({"media": {key: qa.get(key) for key in ("duration", "width", "height", "fps", "audioStreams", "technicalPass", "errors", "faststart")}, "frameMetrics": qa.get("metrics", {}), "sha256": approval["sha256"], "sourceArchive": archive_evidence, "frameworkCommit": run["framework_commit"], "frameworkSnapshot": run["runtime_sha256"], "visualReview": approval["review"]}, indent=2))
        public_provenance = staging / "provenance.json"
        public_provenance.write_text(json.dumps({"production": provenance, "promptInspiration": {key: brief.get(key) for key in ("sourceRepo", "sourceFile", "license", "licenseUrl", "sourceConcept", "promptSource")}}, indent=2))
        files = [(final, "final.mp4", "video/mp4"), (poster, "poster.jpg", "image/jpeg"),
                 (archive, "source.zip", "application/zip"), (root / "qa/contact-sheet.jpg", "storyboard.jpg", "image/jpeg"),
                 (root / "project/edit/creative-prompt.txt", "creative-prompt.txt", "text/plain; charset=utf-8"),
                 (published_review, "review.md", "text/markdown; charset=utf-8"),
                 (verification, "verification.json", "application/json"), (public_provenance, "provenance.json", "application/json")]
        if approval["id"] == "mcp-launch":
            autoplay = staging / "autoplay.mp4"
            checked_run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(final), "-vf", "scale=1280:-2,fps=24", "-an", "-c:v", "libx264", "-crf", "25", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(autoplay)])
            files.append((autoplay, "autoplay.mp4", "video/mp4"))
        hashes = {}
        for path, name, content_type in files:
            hashes[name] = digest(path)
            if path.suffix in {".json", ".md", ".txt"} and SECRET_TEXT.search(path.read_bytes()):
                raise ValueError("Possible credential in public metadata")
        for path, name, content_type in files:
            client.upload_file(str(path), bucket, prefix + "/" + name,
                               ExtraArgs={"ContentType": content_type, "CacheControl": "public, max-age=31536000, immutable"})
        public_check = verify_public(base + "/final.mp4", approval["sha256"])
        if approval["id"] == "mcp-launch":
            verify_public(base + "/autoplay.mp4", hashes["autoplay.mp4"])
    example_fields = ("id", "title", "category", "description", "prompt", "duration", "promptKind", "orientation", "audiences", "useCases", "technique", "sourceRepo", "promptSource")
    example = {key: brief[key] for key in example_fields if key in brief}
    example.update(video=base + "/final.mp4", poster=base + "/poster.jpg", sourceArchive=base + "/source.zip", reviewUrl=base + "/review.md")
    source = {"id": brief["id"], "kind": "original useful workflow produced with Video Use", "sourceBatch": approval["batch"],
              "sourceRun": brief["id"], "model": run["model"], "reasoningEffort": run["reasoning_effort"],
              "frameworkBranch": run["framework_branch"], "frameworkCommit": run["framework_commit"],
              "frameworkArchiveSha256": run["runtime_sha256"], "production": "Independent Video Use agent and render in Modal; encoded output reviewed before publication", "storage": "Cloudflare R2",
              "websiteSha256": approval["sha256"], "promptSource": brief.get("promptSource"), "sourceArchive": base + "/source.zip",
              "editableSourceSha256": approval["sourceSha256"],
              "sourceArchiveScope": "Editable project and small assets; raw downloaded footage, private traces and caches excluded",
              "cloudProject": VOLUME_NAME + "/" + str(root.relative_to("/results")) + "/project/edit",
              "reviewUrl": base + "/review.md", "verificationUrl": base + "/verification.json", "storyboardUrl": base + "/storyboard.jpg",
              "promptUrl": base + "/creative-prompt.txt", "provenanceUrl": base + "/provenance.json",
              "websiteAssets": [{"field": name, "url": example[name]} for name in ("video", "poster")]}
    return {"example": example, "source": source, "publicCheck": public_check, "assets": {name: base + "/" + name for name in hashes}, "hashes": hashes}


def main() -> None:
    import modal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    approval = validate_approval(json.loads(args.approval.read_text()))
    app = modal.App("video-use-reviewed-publisher")
    image = modal.Image.debian_slim(python_version="3.12").apt_install("ffmpeg").pip_install("boto3")
    worker = app.function(image=image, cpu=2, memory=4096, timeout=900, serialized=True,
                          volumes={"/results": modal.Volume.from_name(VOLUME_NAME)}, secrets=[modal.Secret.from_name("video-use-r2")])(publish)
    with modal.enable_output(), app.run():
        result = worker.remote(approval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"published": result["example"]["id"], "video": result["example"]["video"], "verified": result["publicCheck"]}, indent=2))


if __name__ == "__main__":
    main()
