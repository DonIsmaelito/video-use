#!/usr/bin/env python3
"""Prepare and verify product demos using OpenScreen's native renderer."""
from __future__ import annotations

import argparse
import json
import errno
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import tempfile
import uuid

from openscreen_project import prepare_project, read_json, sha256_file

UPSTREAM_SHA = "47ab52fd0907ed07336fa1ff868e671d5d5a469f"
ROOT = Path(__file__).resolve().parents[1]


def checked(command, **kwargs):
    return subprocess.run(command, check=True, text=True, capture_output=True, **kwargs)


def runtime_command(runtime: Path, app: Path):
    """Use a pinned JS checkout with the official app's native addon."""
    runtime, app = runtime.resolve(), app.resolve()
    stamp = read_json(runtime / "video-use-runtime.json")
    if stamp.get("upstream_sha") != UPSTREAM_SHA:
        raise ValueError("Unrecognized runtime revision; run the documented setup first")
    patches = ROOT / "integrations/openscreen/patches"
    expected_patches = {name: sha256_file(patches / name) for name in (
        "cli-source-dimensions.patch", "cli-cursor-settings.patch", "cli-wallpaper-file-url.patch")}
    if stamp.get("patches") != expected_patches:
        raise ValueError("Runtime was built with a different integration patch; rebuild it")
    for rel, digest in stamp["files"].items():
        if sha256_file(runtime / rel) != digest:
            raise ValueError(f"Runtime changed since build: {rel}; rebuild and stamp it")
    addon = app / "Contents/Resources/electron/native/bin/darwin-arm64/compositor_view.node"
    if not addon.is_file() or sha256_file(addon) != stamp["native_addon_sha256"]:
        raise ValueError("Native addon missing or changed; rebuild against OpenScreen 1.11.0")
    native_files = stamp.get("native_files", {})
    actual_names = {str(p.relative_to(addon.parent)) for p in addon.parent.rglob("*") if p.is_file()}
    if not native_files or actual_names != set(native_files):
        raise ValueError("Native library set changed; rebuild the runtime stamp")
    for rel, digest in native_files.items():
        if sha256_file(addon.parent / rel) != digest:
            raise ValueError(f"Native library changed: {rel}; rebuild against the pinned app")
    electron = runtime / "node_modules/.bin/electron"
    if not electron.exists():
        raise ValueError("Electron runtime missing; finish setup first")
    env = dict(os.environ, OPENSCREEN_COMPOSITOR_VIEW_NODE=str(addon))
    env.pop("ELECTRON_RUN_AS_NODE", None)
    return [str(electron), str(runtime)], env


def validate_inputs(manifest_path: Path):
    manifest = read_json(manifest_path)
    base = manifest_path.resolve().parent
    for item in manifest["artifacts"].values():
        path = (base / item["path"]).resolve()
        if not path.is_relative_to(base) or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Prepared input changed or escaped the project: {item['path']}")
    return manifest


def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def run_native(command, env, evidence: Path, timeout_s=1800):
    """Persist the real NDJSON stream, including failure evidence."""
    events = evidence / "native-events.jsonl"
    errors = evidence / "native-stderr.log"
    started = time.monotonic()
    with events.open("w") as out, errors.open("w") as err:
        process = subprocess.Popen(command, env=env, stdout=out, stderr=err,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout_s)
        finally:
            stop_process(process)
    done = successful_done(events)
    if code != 0:
        raise ValueError(f"OpenScreen export failed; inspect {events} and {errors}")
    return {"elapsed_s": time.monotonic() - started, "exit_code": code,
            "events_sha256": sha256_file(events), "result": done}


def successful_done(events: Path):
    records = []
    for line in events.read_text().splitlines():
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
        except json.JSONDecodeError:
            pass  # Native diagnostics can accompany the CLI protocol. Retain the raw log.
    done = [r for r in records if r.get("event") == "done"]
    if not done or done[-1].get("success") is not True:
        raise ValueError(f"OpenScreen export failed; inspect {events}")
    return done[-1]


def probe(path: Path):
    return json.loads(checked(["ffprobe", "-v", "error",
                               "-show_streams", "-show_format", "-of", "json", str(path)]).stdout)


def verify_media(path: Path, expected: dict, audio: bool):
    data = probe(path)
    video = [s for s in data["streams"] if s["codec_type"] == "video"]
    if len(video) != 1:
        raise ValueError("Expected exactly one rendered video stream")
    v = video[0]
    if (v["width"], v["height"]) != (expected["width"], expected["height"]):
        raise ValueError("Native export dimensions do not match the project")
    if v["codec_name"] != "h264" or v["avg_frame_rate"] != "60/1":
        raise ValueError("Expected native H264 at 60 fps")
    declared_frames = v.get("nb_frames")
    if declared_frames not in (None, "N/A") and int(declared_frames) != expected["frame_count"]:
        raise ValueError(f"Frame count mismatch: {declared_frames} vs {expected['frame_count']}")
    if abs(float(v["duration"]) - expected["duration_s"]) > 1 / 60 + 0.001:
        raise ValueError("Export duration changed")
    tracks = [s for s in data["streams"] if s["codec_type"] == "audio"]
    if len(tracks) != int(audio):
        raise ValueError("Audio stream presence does not match the recording")
    if any(v.get(key) != "bt709" for key in ("color_space", "color_transfer", "color_primaries")):
        raise ValueError("BT709 metadata missing from delivery")
    if v.get("color_range") != "tv":
        raise ValueError("Delivery must retain limited-range video")
    # Count decoded video frames during the one required full decode. A separate
    # ffprobe -count_frames would repeat that expensive operation before this.
    command = ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0"]
    if audio:
        command += ["-map", "0:a:0"]
    command += ["-fps_mode", "passthrough", "-progress", "pipe:1", "-nostats", "-f", "null", "-"]
    decoded = checked(command)
    progress = {}
    for line in decoded.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            progress[key] = value.strip()
    if progress.get("progress") != "end" or not progress.get("frame", "").isdigit():
        raise ValueError("Full decode did not report a complete frame count")
    frames = int(progress["frame"])
    if frames != expected["frame_count"]:
        raise ValueError(f"Decoded frame count mismatch: {frames} vs {expected['frame_count']}")
    data["decode_verification"] = {"completed": True, "frame_count": frames,
                                   "audio_decoded": audio, "frame_sync": "passthrough"}
    return data


def publish_file(source: Path, output: Path):
    """Publish without replacing another writer, including on external drives."""
    try:
        os.link(source, output)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        fd, name = tempfile.mkstemp(prefix=".openscreen-", suffix=".mp4", dir=output.parent)
        staged = Path(name)
        try:
            with os.fdopen(fd, "wb") as dest, source.open("rb") as src:
                shutil.copyfileobj(src, dest)
                dest.flush()
                os.fsync(dest.fileno())
            os.link(staged, output)
        finally:
            staged.unlink(missing_ok=True)
    source.unlink()


def validate_output(output: Path):
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new path")
    if output.suffix.lower() != ".mp4":
        raise ValueError("This adapter delivers MP4")


def write_report(path: Path, result: dict):
    """An interrupted report write must leave the native checkpoint intact."""
    fd, name = tempfile.mkstemp(prefix=".result-", suffix=".json", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def record_failure(result: dict, error: BaseException, report: Path):
    result.update(status="failed", error=str(error))
    attempts = result.get("finalization_attempts", [])
    attempt = attempts[-1] if attempts and attempts[-1]["status"] == "running" else None
    if attempt is not None:
        attempt.update(status="failed", error=str(error))
    if isinstance(error, subprocess.CalledProcessError):
        prefix = f"attempt-{attempt['id']}" if attempt else "native-command"
        details = {"command": error.cmd, "returncode": error.returncode}
        for key, value in (("stdout", error.stdout), ("stderr", error.stderr)):
            if value is None:
                continue
            path = report.parent / f"{prefix}-{key}.log"
            text = value.decode(errors="replace") if isinstance(value, bytes) else value
            try:
                path.write_text(text)
                details[key] = path.name
            except OSError:
                details[f"{key}_unwritten"] = text
        (attempt if attempt is not None else result)["subprocess_error"] = details
    try:
        write_report(report, result)
    except OSError as storage_error:
        # In particular ENOSPC: the last atomic native checkpoint still exists.
        print(f"Could not update failure report: {storage_error}", file=sys.stderr)


def validate_native_checkpoint(result: dict, evidence: Path):
    """Only a completed, unchanged native export can skip the render phase."""
    if result.get("upstream_sha") != UPSTREAM_SHA or result.get("native_path") != "native.mp4":
        raise ValueError("Result lacks a recognized native checkpoint")
    native = evidence / "native.mp4"
    if native.is_symlink() or native.resolve().parent != evidence.resolve():
        raise ValueError("Native output escaped its evidence directory")
    digest = result.get("native_sha256")
    if not digest or sha256_file(native) != digest:
        raise ValueError("Native output changed since its checkpoint")
    completed = result.get("native", {})
    events = evidence / "native-events.jsonl"
    if (events.is_symlink() or completed.get("exit_code") != 0 or
            sha256_file(events) != completed.get("events_sha256")):
        raise ValueError("Native completion evidence changed or is incomplete")
    done = successful_done(events)
    output_path = done.get("outputPath")
    if (done != completed.get("result") or not isinstance(output_path, str) or
            Path(output_path).resolve() != native.resolve()):
        raise ValueError("Native completion evidence names a different output")
    return native


def finalize_export(manifest_path: Path, manifest: dict, output: Path, result: dict, report: Path):
    """Retryable delivery: native picture stays immutable across attempts."""
    evidence = report.parent
    if sha256_file(manifest_path) != result["manifest_sha256"]:
        raise ValueError("Prepared manifest changed during rendering")
    validate_inputs(manifest_path)
    native = validate_native_checkpoint(result, evidence)
    attempt_id = uuid.uuid4().hex[:12]
    ready = evidence / f"ready-{attempt_id}.mp4"
    attempt = {"id": attempt_id, "status": "running", "ready_path": ready.name}
    result.setdefault("finalization_attempts", []).append(attempt)
    result.update(status="finalizing")
    result.pop("error", None)
    write_report(report, result)
    # This full-length 1x route preserves source audio instead of native silence
    # fallback, and tags the native shader's known BT709 output without encoding it.
    source = manifest_path.parent / manifest["artifacts"]["source"]["path"]
    source_probe = probe(source)
    tracks = [s for s in source_probe["streams"] if s["codec_type"] == "audio"]
    audio = bool(tracks)
    if len(tracks) > 1:
        raise ValueError("Select or mix the recording's audio tracks before this route")
    remux = ["ffmpeg", "-v", "error", "-n", "-i", str(native)]
    if audio:
        remux += ["-i", str(source)]
    remux += ["-map", "0:v:0", "-c:v", "copy"]
    remux += (["-map", "1:a:0", "-c:a", "copy" if tracks[0]["codec_name"] == "aac" else "aac"]
              if audio else ["-an"])
    remux += ["-bsf:v", "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
              "-color_range", "tv", "-colorspace", "bt709", "-color_trc", "bt709",
              "-color_primaries", "bt709", "-movflags", "+faststart", str(ready)]
    checked(remux)
    result["verification"] = verify_media(ready, manifest["expected_video"], audio)
    if sha256_file(manifest_path) != result["manifest_sha256"]:
        raise ValueError("Prepared manifest changed during rendering")
    validate_inputs(manifest_path)
    validate_native_checkpoint(result, evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    publish_file(ready, output)
    attempt.update(status="complete")
    result.update(status="technically_verified", output_path=str(output),
                  output_sha256=sha256_file(output), bytes=output.stat().st_size,
                  remux="stream copy no second image encode")
    write_report(report, result)
    return result


def export_project(manifest_path: Path, runtime: Path, app: Path, output: Path):
    manifest_path, output = manifest_path.resolve(), output.resolve()
    validate_output(output)
    manifest = validate_inputs(manifest_path)
    base = manifest_path.parent
    command, env = runtime_command(runtime, app)
    evidence = base / ("export-" + uuid.uuid4().hex[:10])
    evidence.mkdir()
    native = evidence / "native.mp4"
    project = base / manifest["artifacts"]["project"]["path"]
    result = {"schema_version": 1, "status": "running", "renderer": "OpenScreen 1.11.0 native",
              "upstream_sha": UPSTREAM_SHA, "manifest_sha256": sha256_file(manifest_path),
              "visual_review": "pending", "evidence_path": str(evidence)}
    report = evidence / "result.json"
    try:
        result["native"] = run_native(command + ["export", str(project), "-o", str(native),
                                                  "--quality", "good", "--json"], env, evidence)
        result.update(status="native_complete", native_path="native.mp4", native_sha256=sha256_file(native))
        validate_native_checkpoint(result, evidence)
        write_report(report, result)  # durable before remux, decoding or publication
        return finalize_export(manifest_path, manifest, output, result, report)
    except BaseException as exc:
        record_failure(result, exc, report)
        raise


def resume_export(report_path: Path, manifest_path: Path, output: Path):
    report_path, manifest_path, output = report_path.resolve(), manifest_path.resolve(), output.resolve()
    validate_output(output)
    result = read_json(report_path)
    if result.get("schema_version") != 1 or result.get("status") not in {"failed", "native_complete", "finalizing"}:
        raise ValueError("Only an unfinished export with a native checkpoint can resume")
    if result.get("evidence_path") != str(report_path.parent):
        raise ValueError("Result does not belong to this evidence directory")
    if sha256_file(manifest_path) != result.get("manifest_sha256"):
        raise ValueError("Prepared manifest changed since the native checkpoint")
    manifest = validate_inputs(manifest_path)
    validate_native_checkpoint(result, report_path.parent)
    try:
        return finalize_export(manifest_path, manifest, output, result, report_path)
    except BaseException as exc:
        record_failure(result, exc, report_path)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("--spec", required=True, type=Path)
    prepare.add_argument("--out", required=True, type=Path)
    prepare.add_argument("--recording-project", type=Path,
                         help="Original OpenScreen v2 editable-overlay capture project")
    commands.add_parser("backgrounds", help="List the bundled background presets")
    export = commands.add_parser("export")
    export.add_argument("manifest", type=Path)
    export.add_argument("--runtime", required=True, type=Path)
    export.add_argument("--app", type=Path, default=Path("/Applications/Openscreen.app"))
    export.add_argument("--out", required=True, type=Path)
    resume = commands.add_parser("resume", help="Retry delivery from a completed native checkpoint")
    resume.add_argument("result", type=Path)
    resume.add_argument("manifest", type=Path)
    resume.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_project(args.source, read_json(args.spec), args.out,
                                     recording_project=args.recording_project)
        elif args.command == "backgrounds":
            from openscreen_backgrounds import list_backgrounds
            result = list_backgrounds()
        elif args.command == "export":
            result = export_project(args.manifest, args.runtime, args.app, args.out)
        else:
            result = resume_export(args.result, args.manifest, args.out)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"OpenScreen: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
