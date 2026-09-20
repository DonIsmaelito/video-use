"""Explicit, retry-safe migration of legacy local GUI videos into R2."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

from gui.r2_storage import R2Storage, poster_object_key, video_object_key
from gui.run_store import RunStore


POSTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class LegacyRun:
    run_id: str
    run_dir: Path
    entry: dict[str, Any]
    videos: tuple[Path, ...]
    poster: Path | None


def _video_sort_key(path: Path) -> tuple[int, str]:
    return (0 if path.name == "output.mp4" else 1, path.name)


def _artifact_id(path: Path) -> str:
    if path.name == "output.mp4":
        return "preview"
    return path.stem.removeprefix("output-") or "preview"


def discover_legacy_runs(
    store: RunStore,
    *,
    only_run_id: str | None = None,
) -> list[LegacyRun]:
    runs: list[LegacyRun] = []
    for entry in store.list_runs():
        run_id = str(entry["run_id"])
        if only_run_id and run_id != only_run_id:
            continue
        if str(entry.get("status") or "") != "ready":
            continue
        try:
            run_dir = store.resolve(run_id)
        except FileNotFoundError:
            continue
        videos = tuple(sorted(run_dir.glob("output*.mp4"), key=_video_sort_key))
        posters = sorted(
            path
            for path in run_dir.glob("poster.*")
            if path.is_file() and path.suffix.casefold() in POSTER_SUFFIXES
        )
        if videos:
            runs.append(
                LegacyRun(
                    run_id=run_id,
                    run_dir=run_dir,
                    entry=entry,
                    videos=videos,
                    poster=posters[0] if posters else None,
                )
            )
    return runs


def _trace(run: LegacyRun) -> dict[str, Any]:
    path = run.run_dir / "trace.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _artifact_metadata(run: LegacyRun) -> list[dict[str, Any]]:
    trace_artifacts = _trace(run).get("artifacts") or []
    artifacts: list[dict[str, Any]] = []
    for index, path in enumerate(run.videos):
        traced = trace_artifacts[index] if index < len(trace_artifacts) else {}
        artifact_id = str(traced.get("id") or _artifact_id(path))
        artifacts.append(
            {
                "id": artifact_id,
                "label": str(
                    traced.get("label")
                    or artifact_id.replace("_", " ").replace("-", " ")
                ),
                "primary": bool(traced.get("primary", index == 0)),
                "path": path,
            }
        )
    if artifacts and not any(item["primary"] for item in artifacts):
        artifacts[0]["primary"] = True
    return artifacts


def _generate_poster(video: Path, destination: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "0.1",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            "scale='min(960,iw)':-2",
            "-q:v",
            "3",
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not destination.is_file():
        raise RuntimeError(f"could not generate poster for {video.name}")


def _convert_poster(source: Path, destination: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not destination.is_file():
        raise RuntimeError(f"could not convert poster {source.name} to JPEG")


def migrate_run(store: RunStore, storage: R2Storage, run: LegacyRun) -> dict[str, Any]:
    artifacts = _artifact_metadata(run)
    trace = _trace(run)
    uploaded: list[dict[str, Any]] = []
    uploaded_keys: list[tuple[str, int]] = []

    with tempfile.TemporaryDirectory(prefix=f"video-use-{run.run_id}-") as temporary:
        poster = run.poster
        if poster is None:
            generated = Path(temporary) / "poster.jpg"
            _generate_poster(run.videos[0], generated)
            poster = generated
        elif poster.suffix.casefold() not in {".jpg", ".jpeg"}:
            converted = Path(temporary) / "poster.jpg"
            _convert_poster(poster, converted)
            poster = converted

        poster_key = poster_object_key(run.run_id)
        poster_url = storage.upload_file(
            poster,
            poster_key,
            content_type="image/jpeg",
        )
        uploaded_keys.append((poster_key, poster.stat().st_size))

        for artifact in artifacts:
            key = video_object_key(run.run_id, str(artifact["id"]))
            path = Path(artifact["path"])
            video_url = storage.upload_file(path, key, content_type="video/mp4")
            uploaded_keys.append((key, path.stat().st_size))
            uploaded.append(
                {
                    "id": artifact["id"],
                    "label": artifact["label"],
                    "video_url": video_url,
                    "primary": artifact["primary"],
                }
            )

        for key, size in uploaded_keys:
            storage.verify_object(key, expected_size=size)

        history = store.record_history(
            run.run_id,
            query=str(run.entry.get("query") or trace.get("prompt") or ""),
            completed_at=str(
                run.entry.get("completed_at")
                or run.entry.get("finished_at")
                or trace.get("finished_at")
                or run.entry.get("updated_at")
            ),
            poster_url=poster_url,
            artifacts=uploaded,
        )

    for path in (*run.videos, *((run.poster,) if run.poster else ())):
        path.unlink()
    return history


def migrate(
    store: RunStore,
    *,
    apply: bool,
    only_run_id: str | None = None,
    storage: R2Storage | None = None,
) -> list[dict[str, Any]]:
    runs = discover_legacy_runs(store, only_run_id=only_run_id)
    planned = [
        {
            "run_id": run.run_id,
            "videos": [path.name for path in run.videos],
            "poster": run.poster.name if run.poster else "generate from primary video",
        }
        for run in runs
    ]
    if not apply:
        return planned
    remote = storage or R2Storage.from_env()
    return [migrate_run(store, remote, run) for run in runs]


def _print_plan(items: Iterable[dict[str, Any]], *, applied: bool) -> None:
    action = "migrated" if applied else "would migrate"
    count = 0
    for item in items:
        count += 1
        print(f"{action} {item['run_id']}")
    if count == 0:
        print("no legacy runs found")
    elif not applied:
        print("dry run only; pass --apply to upload and remove verified local media")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the migration")
    parser.add_argument("--run-id", help="migrate one run only")
    parser.add_argument("--data-dir", type=Path, help="override the GUI data directory")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    store = (
        RunStore(args.data_dir, create=args.apply)
        if args.data_dir
        else RunStore(create=args.apply)
    )
    results = migrate(store, apply=args.apply, only_run_id=args.run_id)
    _print_plan(results, applied=args.apply)


if __name__ == "__main__":
    main()
