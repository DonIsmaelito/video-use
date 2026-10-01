#!/usr/bin/env python3
"""Make a bounded contact sheet from the actual encoded video, with beat coverage.

This is visual evidence, not automatic aesthetic approval. Final export still
performs the separate full-video and audio decode checks.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MAX_SAMPLES = 12
MAX_AUDIO_SECONDS = 180.0
AUDIO_TIMEOUT_SECONDS = 20
AUDIO_LIMITATION = (
    "Measurements of the first encoded audio track are not listening, speech "
    "transcription, or verification that narration matches the visuals. Other "
    "audio tracks are not analyzed. Stream timestamps alone do not prove sync."
)


def _finite_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def measure_audio_evidence(
    path: Path, metadata: dict, *, max_seconds: float = MAX_AUDIO_SECONDS
) -> dict:
    """Measure bounded encoded audio without claiming an editorial listening pass."""
    if not math.isfinite(max_seconds) or not 0 < max_seconds <= MAX_AUDIO_SECONDS:
        raise ValueError(f"Audio measurement limit must be in (0, {MAX_AUDIO_SECONDS}]")
    streams = metadata.get("streams", [])
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    evidence = {
        "status": "no_audio" if not audio else "unavailable",
        "audio_stream_count": len(audio),
        "limitations": AUDIO_LIMITATION,
        "warnings": [],
    }
    if not audio:
        return evidence  # Silent films need no invented missing-audio defect.
    stream = audio[0]
    duration = _finite_number(stream.get("duration"))
    start = _finite_number(stream.get("start_time"))
    sample_rate = _finite_number(stream.get("sample_rate"))
    channels = _finite_number(stream.get("channels"))
    evidence.update(
        {
            "stream_index": stream.get("index"),
            "codec": stream.get("codec_name"),
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "stream_start_seconds": start,
            "stream_duration_seconds": duration,
            "measurement_limit_seconds": max_seconds,
        }
    )
    video_stream = next(
        (item for item in streams if item.get("codec_type") == "video"), {}
    )
    video_start = _finite_number(video_stream.get("start_time"))
    evidence["video_stream_start_seconds"] = video_start
    evidence["audio_video_start_offset_seconds"] = (
        round(start - video_start, 6)
        if start is not None and video_start is not None
        else None
    )
    # Keep decoder diagnostics out of memory; inspect only a bounded tail. A
    # prefix limit and wall timeout protect the surrounding 120-second review.
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-xerror",
        "-loglevel",
        "info",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        "-t",
        str(max_seconds),
        "-af",
        f"atrim=duration={max_seconds},ebur128=peak=true:framelog=verbose,volumedetect",
        "-f",
        "null",
        "-",
    ]
    with tempfile.TemporaryFile() as diagnostics:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=diagnostics,
                timeout=AUDIO_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            evidence["error"] = (
                "Audio measurement timed out; no loudness result is claimed."
            )
            return evidence
        except OSError:
            evidence["error"] = "Audio measurement could not start."
            return evidence
        diagnostics.seek(0, 2)
        diagnostics.seek(max(0, diagnostics.tell() - 32768))
        log = diagnostics.read().decode("utf-8", errors="replace")
    if result.returncode:
        evidence["error"] = "The selected encoded audio track could not be measured."
        return evidence

    def value(pattern):
        matches = re.findall(pattern, log)
        return matches[-1] if matches else None

    number = r"(-?(?:\d+(?:\.\d+)?|inf))"
    sample_count = _finite_number(value(r"n_samples:\s*(\d+)"))
    loudness = _finite_number(value(r"\bI:\s*" + number + r"\s*LUFS"))
    raw_peak = value(r"\bPeak:\s*" + number + r"\s*dBFS")
    true_peak = _finite_number(raw_peak)
    mean = _finite_number(value(r"mean_volume:\s*" + number + r"\s*dB"))
    sample_peak = _finite_number(value(r"max_volume:\s*" + number + r"\s*dB"))
    if not sample_count or raw_peak is None or mean is None or sample_peak is None:
        evidence["error"] = "The audio analyzer returned no complete measurement."
        return evidence
    measured_seconds = (
        sample_count / (sample_rate * channels)
        if sample_rate and channels and sample_rate > 0 and channels > 0
        else None
    )
    # If stream duration is unknown, reaching the prefix limit cannot establish
    # complete coverage. Do not infer audio duration from the video container.
    tolerance = (
        max(0.05, 2048 / sample_rate) if sample_rate and sample_rate > 0 else 0.05
    )
    complete = bool(
        measured_seconds is not None
        and (
            (
                duration is not None
                and duration <= max_seconds
                and measured_seconds + tolerance >= duration
            )
            or (duration is None and measured_seconds < max_seconds - tolerance)
        )
    )
    silence = raw_peak == "-inf"
    evidence.update(
        {
            "status": "measured" if complete else "partial",
            "coverage": "complete_first_audio_track"
            if complete
            else "audio_prefix_only",
            "measured_seconds": round(measured_seconds, 4)
            if measured_seconds is not None
            else None,
            "decoded_sample_count": int(sample_count),
            "integrated_loudness_lufs": loudness
            if loudness is not None and loudness > -70
            else None,
            "true_peak_dbtp": true_peak,
            "mean_volume_dbfs": mean,
            "sample_peak_dbfs": sample_peak,
            "digital_silence": silence,
            "method": "FFmpeg ebur128 true peak and volumedetect on decoded audio",
        }
    )
    if silence:
        evidence["warnings"].append("Decoded samples in the measured range are silent.")
    elif true_peak is not None and true_peak > 0:
        evidence["warnings"].append(
            "Measured true peak exceeds 0 dBTP; playback clipping is possible, not established."
        )
    elif sample_peak >= 0:
        evidence["warnings"].append(
            "Measured sample peak reaches 0 dBFS; this alone does not establish clipping."
        )
    elif sample_peak < -60:
        evidence["warnings"].append(
            "Measured audio peak is below -60 dBFS (very low level)."
        )
    if not complete:
        evidence["warnings"].append(
            "Loudness and peak evidence does not cover the complete audio track."
        )
    return evidence


def sample_times(duration: float, fps: float, beats: list | None = None) -> list[float]:
    """Cover opening/end plus beat holds and boundaries, or the full timeline."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video duration must be finite and positive")
    if not math.isfinite(fps) or fps <= 0:
        fps = 30.0
    last = max(0.0, duration - 1 / fps)
    frame_count = max(1, math.ceil(duration * fps))
    count = min(MAX_SAMPLES, frame_count)
    first = min(0.2, duration / 10, last)
    end = max(first, last - min(0.08, duration / 20))

    # A stale or differently timed plan is worse than uniform sampling.
    durations = []
    try:
        durations = [float(beat["seconds"]) for beat in (beats or [])]
        if not all(math.isfinite(d) and d > 0 for d in durations):
            durations = []
        if durations and abs(sum(durations) - duration) > max(0.25, duration * 0.05):
            durations = []
    except (TypeError, KeyError, ValueError):
        durations = []

    candidates = [first, end]
    if durations:
        starts = [sum(durations[:i]) for i in range(len(durations))]
        holds = [start + length * 0.6 for start, length in zip(starts, durations)]
        # Keep every beat represented when there is room. Longer plans are
        # sampled across their complete span rather than dropping the ending.
        budget = max(0, count - len(candidates))
        if len(holds) > budget:
            holds = [
                holds[round(i * (len(holds) - 1) / max(1, budget - 1))]
                for i in range(budget)
            ]
        candidates.extend(holds)
        boundaries = [
            start + min(0.2, length / 4)
            for start, length in zip(starts[1:], durations[1:])
        ]
        remaining = max(0, count - len(candidates))
        if len(boundaries) > remaining:
            boundaries = [
                boundaries[round(i * (len(boundaries) - 1) / max(1, remaining - 1))]
                for i in range(remaining)
            ]
        candidates.extend(boundaries)
    else:
        candidates = [
            first + (end - first) * i / max(1, count - 1) for i in range(count)
        ]

    # Quantize to distinct decodable frames, including extremely short videos.
    indices = {min(frame_count - 1, max(0, round(t * fps))) for t in candidates}
    while len(indices) < count:
        available = [i for i in range(frame_count) if i not in indices]
        if not available:
            break
        indices.add(max(available, key=lambda i: min(abs(i - j) for j in indices)))
    return [min(last, i / fps) for i in sorted(indices)[:count]]


def review_video(path: Path, output: Path, beats: list | None = None) -> dict:
    metadata = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            timeout=10,
        )
    )
    videos = [
        stream
        for stream in metadata.get("streams", [])
        if stream.get("codec_type") == "video"
    ]
    if not videos:
        raise ValueError("Review requires a video stream")
    video = videos[0]
    duration = float(video.get("duration") or metadata["format"]["duration"])
    try:
        fps = float(Fraction(video.get("avg_frame_rate", "30")))
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    times = sample_times(duration, fps, beats)
    ratio = video["width"] / video["height"]
    if ratio > 1.1:
        columns, cell_width, cell_height = 3, 480, 270
    elif ratio < 0.9:
        columns, cell_width, cell_height = 4, 270, 480
    else:
        columns, cell_width, cell_height = 4, 384, 384
    columns = min(columns, len(times))
    label_height = 28
    rows = math.ceil(len(times) / columns)
    sheet = Image.new(
        "RGB", (columns * cell_width, rows * (cell_height + label_height)), "#171717"
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    output.parent.mkdir(parents=True, exist_ok=True)
    for i, timestamp in enumerate(times):
        frame_path = output.parent / f"output-review-{i:02d}.png"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.8f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={cell_width}:{cell_height}:force_original_aspect_ratio=decrease,setsar=1",
                str(frame_path),
            ],
            check=True,
            capture_output=True,
            timeout=6,
        )
        x, y = (i % columns) * cell_width, (i // columns) * (cell_height + label_height)
        with Image.open(frame_path) as frame:
            sheet.paste(
                frame,
                (
                    x + (cell_width - frame.width) // 2,
                    y + (cell_height - frame.height) // 2,
                ),
            )
        draw.text(
            (x + 10, y + cell_height + 5), f"{timestamp:.2f}s", fill="white", font=font
        )
    sheet.save(output)
    report = {
        "video": str(path),
        "duration": duration,
        "sample_times": times,
        "contact_sheet": str(output),
        "width": sheet.width,
        "height": sheet.height,
        "audio_evidence": measure_audio_evidence(path, metadata),
        "limitation": "Sampled still frames do not verify every frame, motion continuity, or audible quality.",
    }
    output.with_suffix(".json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/workspace/edit/verify/output-review.png")
    )
    parser.add_argument("--beats-json", default="[]")
    args = parser.parse_args()
    beats = json.loads(args.beats_json)
    print(json.dumps(review_video(args.video, args.output, beats)))


if __name__ == "__main__":
    main()
