"""Copy explicitly approved source media and transcripts into a creative job.

Shared acquisition runs separately from creative workers. Workers receive only
the named, hash-bound inputs; provider credentials never travel with the media.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path, PurePosixPath

ALLOWED = {".mp4", ".mov", ".webm", ".mkv", ".mp3", ".wav", ".m4a", ".flac",
           ".json", ".txt", ".md", ".jpg", ".jpeg", ".png", ".webp", ".srt", ".vtt"}
MAX_FILE = 4 * 1024**3
MAX_TOTAL = 8 * 1024**3


def _path(value, prefix):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ValueError("Prepared input paths must be relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part.startswith(".") for part in path.parts):
        raise ValueError("Prepared input paths cannot contain hidden or traversal components")
    if path.parts[:len(prefix)] != prefix or len(path.parts) <= len(prefix):
        raise ValueError("Prepared input path is outside its approved namespace")
    if path.suffix.lower() not in ALLOWED:
        raise ValueError("Unsupported prepared input type")
    return path


def validate_inputs(values):
    if not isinstance(values, list) or len(values) > 24:
        raise ValueError("Select at most 24 prepared input files")
    targets = set()
    total = 0
    for value in values:
        if not isinstance(value, dict) or set(value) != {"source", "target", "sha256", "bytes"}:
            raise ValueError("Each prepared input needs source target sha256 and bytes")
        _path(value["source"], ("prepared-assets",))
        target = _path(value["target"], ("edit",))
        if len(target.parts) < 3 or target.parts[1] not in {"downloads", "transcripts", "tracks", "references"}:
            raise ValueError("Prepared inputs may only populate media and evidence directories")
        if target in targets:
            raise ValueError("Duplicate prepared input target")
        targets.add(target)
        if not isinstance(value["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"]):
            raise ValueError("Prepared input requires an exact SHA256")
        size = value["bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_FILE:
            raise ValueError("Invalid prepared input byte count")
        total += size
    if total > MAX_TOTAL:
        raise ValueError("Prepared inputs exceed the per-job size limit")
    return values


def _no_links(root, relative):
    path = root
    if root.is_symlink():
        raise ValueError("Prepared input root must not be a symlink")
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Prepared input paths must not follow symlinks")
    return path


def _digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def stage_inputs(values, project: Path, volume_root: Path = Path("/results")):
    values = validate_inputs(values)
    plan = []
    for value in values:
        source = _no_links(volume_root, PurePosixPath(value["source"]))
        target = _no_links(project, PurePosixPath(value["target"]))
        if not source.is_file() or source.stat().st_size != value["bytes"] or _digest(source) != value["sha256"]:
            raise ValueError("Prepared source bytes differ from the approved input")
        if target.exists():
            raise ValueError("Prepared inputs must not overwrite existing project files")
        plan.append((value, source, target))
    installed = []
    try:
        for value, source, target in plan:
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as incoming, target.open("xb") as outgoing:
                installed.append(target)
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
            if target.stat().st_size != value["bytes"] or _digest(target) != value["sha256"]:
                raise ValueError("Prepared source changed while copying")
    except BaseException:
        for target in installed:
            target.unlink(missing_ok=True)
        raise
    return values
