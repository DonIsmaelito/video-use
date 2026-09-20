"""Modal workers for the local video-use GUI.

Deploy with:
    modal deploy gui/modal_app.py

The deployed image receives the current working-tree snapshot, so every worker
runs the exact video-use code present at deploy time.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import modal


APP_NAME = "video-use-gui"
FUNCTION_PREFIX = "run_lane_"
VOLUME_NAME = "video-use-gui-runs"
REMOTE_REPO = Path("/opt/video-use")
REMOTE_RUNS = Path("/runs")

LOCAL_REPO = Path(__file__).resolve().parents[1]

# Modal imports this entry module from /root while the working-tree snapshot is
# baked into /opt/video-use. Make package imports available during module load,
# before any remote function is hydrated.
if REMOTE_REPO.is_dir() and str(REMOTE_REPO) not in sys.path:
    sys.path.insert(0, str(REMOTE_REPO))

from gui.r2_storage import R2Storage, poster_object_key, video_object_key  # noqa: E402

app = modal.App(APP_NAME)
run_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
r2_secret = modal.Secret.from_name("video-use-r2")

video_use_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "git", "fonts-dejavu-core")
    .uv_pip_install("requests", "librosa", "matplotlib", "pillow", "numpy", "boto3")
    .add_local_dir(
        LOCAL_REPO,
        remote_path=str(REMOTE_REPO),
        ignore=[
            ".git",
            ".venv",
            ".env",
            ".env.*",
            "**/__pycache__",
            "**/*.pyc",
            "gui/.runtime",
        ],
    )
)


def function_name(lane_id: int) -> str:
    if lane_id not in (1, 2, 3, 4):
        raise ValueError(f"invalid lane: {lane_id}")
    return f"{FUNCTION_PREFIX}{lane_id}"


def _event(
    lane_id: int,
    run_id: str,
    event_type: str,
    message: str,
    *,
    progress: float | None = None,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "lane_id": lane_id,
        "run_id": run_id,
        "type": event_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if progress is not None:
        payload["progress"] = max(0.0, min(1.0, progress))
    payload.update(extra)
    return payload


def _render_progress(line: str, current: float) -> float:
    stripped = line.strip().lower()
    if stripped.startswith("extracting "):
        return max(current, 0.18)
    if re.match(r"^\[\d+\]", stripped):
        return min(0.66, current + 0.06)
    if stripped.startswith("concat"):
        return max(current, 0.70)
    if stripped.startswith("reframing"):
        return max(current, 0.76)
    if stripped.startswith("compositing"):
        return max(current, 0.80)
    if stripped.startswith("loudness normalization"):
        return max(current, 0.88)
    if stripped.startswith("done:"):
        return 0.98
    return current


def _show_trace(line: str) -> bool:
    """Keep the pane readable while retaining decisions and failure context."""

    stripped = line.strip()
    lowered = stripped.lower()
    useful_prefixes = (
        "extracting ",
        "concat ",
        "reframing ",
        "compositing ",
        "overlays:",
        "master srt ",
        "loudness normalization",
        "loudnorm ",
        "measured:",
        "done:",
        "warning:",
        "no transcript ",
        "traceback ",
        "file ",
        "subprocess.",
        "edl is not renderable:",
    )
    return (
        bool(re.match(r"^\[\d+\]", stripped))
        or lowered.startswith(useful_prefixes)
        or " error" in lowered
        or " failed" in lowered
        or "invalid" in lowered
    )


def _run_command(command: list[str], log_path: Path) -> Iterator[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as render_log:
        render_log.write(f"$ {shlex.join(command)}\n")
        process = subprocess.Popen(
            command,
            cwd=REMOTE_REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            render_log.write(line)
            cleaned = line.rstrip()
            if cleaned:
                yield cleaned
        return_code = process.wait()
        render_log.write(f"[process exited {return_code}]\n")
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)


def _diagnostic_video(
    output_path: Path,
    lane_id: int,
    prompt: str,
    log_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    label_path = output_path.with_suffix(".txt")
    short_prompt = re.sub(r"\s+", " ", prompt).strip()[:90]
    label_path.write_text(
        f"video-use lane {lane_id}\nmodal worker ready\n{short_prompt}",
        encoding="utf-8",
    )
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x080808:s=1280x720:d=3:r=30",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo",
        "-vf",
        (
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"textfile={label_path}:fontcolor=white:fontsize=42:line_spacing=18:"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        ),
        "-t",
        "3",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    with log_path.open("a", encoding="utf-8") as render_log:
        render_log.write(f"$ {shlex.join(command)}\n")
        result = subprocess.run(
            command,
            check=False,
            stdout=render_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        render_log.write(f"[process exited {result.returncode}]\n")
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command)
    label_path.unlink(missing_ok=True)


def _create_poster(video_path: Path, poster_path: Path, log_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        "0.1",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale='min(960,iw)':-2",
        "-q:v",
        "3",
        str(poster_path),
    ]
    with log_path.open("a", encoding="utf-8") as render_log:
        render_log.write(f"$ {shlex.join(command)}\n")
        result = subprocess.run(
            command,
            check=False,
            stdout=render_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        render_log.write(f"[process exited {result.returncode}]\n")
    if result.returncode != 0 or not poster_path.is_file():
        raise RuntimeError("could not generate the primary R2 poster")


WORKER_OPTIONS = dict(
    image=video_use_image,
    cpu=8.0,
    memory=16_384,
    max_containers=1,
    scaledown_window=300,
    timeout=7_200,
    volumes={str(REMOTE_RUNS): run_volume},
    secrets=[r2_secret],
)


def _run_lane(job: dict[str, object]) -> Iterator[dict[str, object]]:
    """Run one isolated lane and yield structured progress to localhost."""

    # Modal imports this module from /root, while the complete working-tree
    # snapshot is mounted at /opt/video-use. Resolve reusable helpers only after
    # entering the worker so deployment does not depend on the caller's cwd.
    remote_repo_text = str(REMOTE_REPO)
    if remote_repo_text not in sys.path:
        sys.path.insert(0, remote_repo_text)
    from helpers.edl import normalize_deliverables, validate_edl

    lane_id = int(job["lane_id"])
    run_id = str(job["run_id"])
    prompt = str(job.get("prompt") or "")
    has_project = bool(job.get("has_project"))
    run_root = REMOTE_RUNS / run_id
    project_root = run_root / "input"
    edit_dir = project_root / "edit"
    render_log_path = run_root / "render.log"
    deliverables: list[dict[str, object]] = []

    # Warm containers retain the Volume snapshot from their startup. Reload so
    # a project uploaded by localhost immediately before invocation is visible.
    run_volume.reload()
    run_root.mkdir(parents=True, exist_ok=True)
    render_log_path.write_text(
        (
            f"video-use GUI Modal render\n"
            f"run_id={run_id}\n"
            f"lane_id={lane_id}\n"
            f"started_at={datetime.now(timezone.utc).isoformat()}\n"
        ),
        encoding="utf-8",
    )
    yield _event(lane_id, run_id, "started", "container ready", progress=0.04)

    try:
        required = [
            REMOTE_REPO / "SKILL.md",
            REMOTE_REPO / "helpers" / "render.py",
            REMOTE_REPO / "helpers" / "timeline_view.py",
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise RuntimeError(
                f"video-use snapshot incomplete: {', '.join(missing)}"
            )

        yield _event(
            lane_id,
            run_id,
            "trace",
            "video-use branch snapshot verified",
            progress=0.08,
        )
        ffmpeg_version = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()[0]
        yield _event(lane_id, run_id, "trace", ffmpeg_version, progress=0.12)

        if has_project and (edit_dir / "edl.json").exists():
            edl_path = edit_dir / "edl.json"
            staged_edl = json.loads(edl_path.read_text(encoding="utf-8"))
            validate_edl(
                staged_edl,
                edit_dir,
                require_caption_provenance=True,
            )
            output_dir = edit_dir / "runs" / run_id / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            deliverables = normalize_deliverables(
                staged_edl,
                edit_dir,
                output_dir=output_dir,
            )
            yield _event(
                lane_id,
                run_id,
                "decision",
                (
                    f"rendering {len(deliverables)} declared deliverables"
                    if deliverables
                    else "rendering the staged EDL as an evaluable preview"
                ),
                progress=0.15,
            )
            command = [
                "python",
                "-u",
                str(REMOTE_REPO / "helpers" / "render.py"),
                str(edl_path),
                "--preview",
            ]
            if deliverables:
                command.extend(["--all-deliverables", "--output-dir", str(output_dir)])
                output_paths = [Path(item["output_path"]) for item in deliverables]
            else:
                output_path = output_dir / "preview.mp4"
                command.extend(["-o", str(output_path)])
                output_paths = [output_path]
            transcript_files = list((edit_dir / "transcripts").glob("*.json"))
            has_subtitle_file = bool(staged_edl.get("subtitles"))
            has_caption_contract = isinstance(staged_edl.get("captions"), dict)
            if has_caption_contract and not has_subtitle_file:
                if not transcript_files:
                    raise RuntimeError(
                        "captions were declared without a rendered subtitle file or "
                        "source transcripts; generate the subtitle track from audible "
                        "speech before remote rendering"
                    )
                command.append("--build-subtitles")
            elif not has_subtitle_file:
                command.append("--no-subtitles")
                yield _event(
                    lane_id,
                    run_id,
                    "decision",
                    "no caption contract declared; rendering without subtitles",
                    progress=0.16,
                )
            progress = 0.15
            for line in _run_command(command, render_log_path):
                progress = _render_progress(line, progress)
                if _show_trace(line):
                    yield _event(lane_id, run_id, "trace", line, progress=progress)
        else:
            output_path = run_root / "diagnostic.mp4"
            message = "no edit/edl.json staged; creating a container check"
            yield _event(lane_id, run_id, "decision", message, progress=0.20)
            _diagnostic_video(output_path, lane_id, prompt, render_log_path)
            yield _event(
                lane_id,
                run_id,
                "trace",
                "diagnostic video encoded",
                progress=0.90,
            )
            output_paths = [output_path]
    except Exception:
        with render_log_path.open("a", encoding="utf-8") as render_log:
            render_log.write("\n[worker exception]\n")
            render_log.write(traceback.format_exc())
        raise
    finally:
        with render_log_path.open("a", encoding="utf-8") as render_log:
            render_log.write(f"finished_at={datetime.now(timezone.utc).isoformat()}\n")
        run_volume.commit()
    poster_path = run_root / "poster.jpg"
    storage: R2Storage | None = None
    try:
        _create_poster(output_paths[0], poster_path, render_log_path)
        storage = R2Storage.from_env()
        poster_url = storage.upload_file(
            poster_path,
            poster_object_key(run_id),
            content_type="image/jpeg",
        )
        uploaded: list[dict[str, object]] = []
        for index, artifact_path in enumerate(output_paths):
            deliverable = (
                deliverables[index]
                if has_project and deliverables
                else {"id": "preview", "label": "preview"}
            )
            artifact_id = str(deliverable["id"])
            video_url = storage.upload_file(
                artifact_path,
                video_object_key(run_id, artifact_id),
                content_type="video/mp4",
            )
            uploaded.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_label": str(
                        deliverable.get("label")
                        or deliverable.get("name")
                        or artifact_id.replace("_", " ")
                    ),
                    "artifact_url": video_url,
                    "primary": index == 0,
                }
            )
    except Exception:
        upload_traceback = traceback.format_exc()
        cleanup_traceback = ""
        if storage is not None:
            try:
                storage.delete_run(run_id)
            except Exception:
                cleanup_traceback = (
                    "\n[R2 partial-upload cleanup exception]\n"
                    + traceback.format_exc()
                )
        with render_log_path.open("a", encoding="utf-8") as render_log:
            render_log.write("\n[R2 upload exception]\n")
            render_log.write(upload_traceback)
            render_log.write(cleanup_traceback)
        poster_path.unlink(missing_ok=True)
        run_volume.commit()
        raise RuntimeError(
            "R2 output upload failed; inspect the durable render log"
        ) from None
    finally:
        poster_path.unlink(missing_ok=True)

    run_volume.commit()

    for artifact in uploaded:
        is_primary = bool(artifact["primary"])
        yield _event(
            lane_id,
            run_id,
            "artifact",
            f"video output uploaded: {artifact['artifact_id']}",
            progress=0.98,
            **artifact,
            poster_url=poster_url,
            **({"video_url": artifact["artifact_url"]} if is_primary else {}),
        )
    yield _event(lane_id, run_id, "completed", "complete", progress=1.0)
    if bool(job.get("cleanup_after")):
        storage.delete_run(run_id)
        shutil.rmtree(run_root, ignore_errors=True)
        run_volume.commit()


# Four separate Function pools make the lane-to-container mapping explicit.
# Each pool can run exactly one input, so no lane shares CPU or RAM with another.
@app.function(name=function_name(1), **WORKER_OPTIONS)
def run_lane_1(job: dict[str, object]) -> Iterator[dict[str, object]]:
    yield from _run_lane(job)


@app.function(name=function_name(2), **WORKER_OPTIONS)
def run_lane_2(job: dict[str, object]) -> Iterator[dict[str, object]]:
    yield from _run_lane(job)


@app.function(name=function_name(3), **WORKER_OPTIONS)
def run_lane_3(job: dict[str, object]) -> Iterator[dict[str, object]]:
    yield from _run_lane(job)


@app.function(name=function_name(4), **WORKER_OPTIONS)
def run_lane_4(job: dict[str, object]) -> Iterator[dict[str, object]]:
    yield from _run_lane(job)


@app.function(
    name="verify_r2_storage",
    image=video_use_image,
    cpu=1.0,
    memory=1_024,
    timeout=300,
    secrets=[r2_secret],
)
def verify_r2_storage() -> dict[str, object]:
    """Upload, publicly range-read, and delete one temporary MP4."""

    import requests

    run_id = f"smoke-{uuid.uuid4().hex}"
    video_path = Path("/tmp") / f"{run_id}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=1:r=24",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    payload = video_path.read_bytes()
    storage = R2Storage.from_env()
    key = video_object_key(run_id, "range-test")
    public_url = storage.upload_file(video_path, key, content_type="video/mp4")
    try:
        playback = None
        for _attempt in range(10):
            playback = requests.get(public_url, timeout=30)
            if playback.status_code == 200:
                break
            time.sleep(1)
        if playback is None or playback.status_code != 200:
            raise RuntimeError("public R2 playback did not become available")
        if b"ftyp" not in playback.content[:32]:
            raise RuntimeError("public R2 object is not the uploaded MP4")
        partial = requests.get(
            public_url,
            headers={"Range": "bytes=128-255"},
            timeout=30,
        )
        if partial.status_code != 206 or partial.content != payload[128:256]:
            raise RuntimeError("public R2 byte-range seeking verification failed")
    finally:
        deleted = storage.delete_run(run_id)
        video_path.unlink(missing_ok=True)
    if deleted < 1:
        raise RuntimeError("R2 smoke object deletion was not verified")
    return {
        "status": "ok",
        "playback_status": playback.status_code,
        "range_status": partial.status_code,
        "deleted_objects": deleted,
    }


@app.local_entrypoint()
def smoke_test(lane_id: int = 1) -> None:
    """Run one diagnostic lane from the CLI."""

    run_id = f"smoke-{int(time.time())}"
    job = {
        "lane_id": lane_id,
        "run_id": run_id,
        "prompt": "modal worker smoke test",
        "has_project": False,
        "cleanup_after": True,
    }
    for event in run_lane_1.remote_gen(job):
        print(json.dumps(event, sort_keys=True))


@app.local_entrypoint()
def r2_smoke_test() -> None:
    """Verify live R2 public playback, seeking, and cleanup from Modal."""

    print(json.dumps(verify_r2_storage.remote(), sort_keys=True))
