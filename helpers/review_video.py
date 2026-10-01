#!/usr/bin/env python3
"""Make a bounded contact sheet from the actual encoded video, with beat coverage.

This is visual evidence, not automatic aesthetic approval. Final export still
performs the separate full-video and audio decode checks.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MAX_SAMPLES = 12


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
                "-select_streams",
                "v:0",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )
    if not metadata.get("streams"):
        raise ValueError("Review requires a video stream")
    video = metadata["streams"][0]
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
