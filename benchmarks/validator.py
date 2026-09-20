from __future__ import annotations

import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


def probe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
        data = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}

    video_stream = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    audio_stream = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    try:
        duration = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "ok": video_stream is not None,
        "path": str(path),
        "duration_s": duration,
        "video": video_stream,
        "audio": audio_stream,
    }


def audio_is_audible(path: Path, threshold_db: float = -50.0) -> tuple[bool, float | None]:
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-vn", "-af", "volumedetect", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    match = re.search(r"mean_volume:\s*(-?inf|-?[0-9.]+)\s*dB", result.stderr, re.IGNORECASE)
    if not match or match.group(1).lower() == "-inf":
        return False, None
    mean_db = float(match.group(1))
    return mean_db > threshold_db, mean_db


def media_is_decodable(path: Path) -> tuple[bool, str | None]:
    command = [
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        return False, detail[-1] if detail else f"ffmpeg exited with {result.returncode}"
    return True, None


def _fps_as_float(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def validate_media(path: Path, rules: dict[str, Any]) -> dict[str, Any]:
    probe = probe_media(path)
    errors: list[str] = []
    warnings: list[str] = []
    if not probe["ok"]:
        return {"path": str(path), "passed": False, "errors": [probe.get("error", "no video stream")], "warnings": []}

    decodable, decode_error = media_is_decodable(path)
    if not decodable:
        errors.append(f"media is not fully decodable: {decode_error}")

    duration = probe["duration_s"]
    if duration < float(rules.get("min_duration_s", 0.0)):
        errors.append(f"duration {duration:.3f}s is below minimum {rules['min_duration_s']}s")
    if rules.get("max_duration_s") is not None and duration > float(rules["max_duration_s"]):
        errors.append(f"duration {duration:.3f}s exceeds maximum {rules['max_duration_s']}s")

    video = probe["video"] or {}
    width = int(video.get("width", 0) or 0)
    height = int(video.get("height", 0) or 0)
    expected_width = rules.get("width")
    expected_height = rules.get("height")
    if expected_width is not None and width != int(expected_width):
        errors.append(f"width {width} != {expected_width}")
    if expected_height is not None and height != int(expected_height):
        errors.append(f"height {height} != {expected_height}")

    expected_aspect = rules.get("aspect_ratio")
    if expected_aspect and height:
        numerator, denominator = (int(part) for part in str(expected_aspect).split(":", 1))
        actual = width / height
        target = numerator / denominator
        if abs(actual - target) > float(rules.get("aspect_tolerance", 0.01)):
            errors.append(f"aspect ratio {width}:{height} is not {expected_aspect}")

    expected_fps = rules.get("fps")
    actual_fps = _fps_as_float(video.get("avg_frame_rate"))
    if expected_fps is not None and (
        actual_fps is None or abs(actual_fps - float(expected_fps)) > float(rules.get("fps_tolerance", 0.02))
    ):
        errors.append(f"frame rate {actual_fps} != {expected_fps}")

    expected_video_codec = rules.get("video_codec")
    if expected_video_codec and video.get("codec_name") != expected_video_codec:
        errors.append(f"video codec {video.get('codec_name')} != {expected_video_codec}")

    audio = probe["audio"]
    if rules.get("require_audio") and audio is None:
        errors.append("missing audio stream")
    expected_audio_codec = rules.get("audio_codec")
    if expected_audio_codec and audio and audio.get("codec_name") != expected_audio_codec:
        errors.append(f"audio codec {audio.get('codec_name')} != {expected_audio_codec}")
    mean_volume_db: float | None = None
    if rules.get("require_audible_audio") and audio is not None:
        audible, mean_volume_db = audio_is_audible(
            path, float(rules.get("audible_threshold_db", -50.0))
        )
        if not audible:
            errors.append("audio is silent or below the audible threshold")

    if rules.get("require_caption_sidecar") and not path.with_suffix(".srt").exists():
        errors.append(f"missing caption sidecar {path.with_suffix('.srt').name}")

    return {
        "path": str(path),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "duration_s": duration,
        "width": width,
        "height": height,
        "fps": actual_fps,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "mean_volume_db": mean_volume_db,
    }


def validate_task_outputs(workspace: Path, task: dict[str, Any]) -> dict[str, Any]:
    output_config = task["outputs"]
    pattern = str(output_config["glob"])
    paths = sorted(path for path in workspace.glob(pattern) if path.is_file())
    minimum_count = int(output_config.get("min_count", 1))
    errors: list[str] = []
    if len(paths) < minimum_count:
        errors.append(f"found {len(paths)} output(s), expected at least {minimum_count} matching {pattern}")
    artifacts = [validate_media(path, output_config["validation"]) for path in paths]
    for artifact in artifacts:
        errors.extend(f"{Path(artifact['path']).name}: {message}" for message in artifact["errors"])
    total_duration = sum(float(artifact.get("duration_s", 0.0)) for artifact in artifacts)
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": [warning for artifact in artifacts for warning in artifact["warnings"]],
        "clip_count": len(artifacts),
        "total_duration_s": total_duration,
        "artifacts": artifacts,
    }
