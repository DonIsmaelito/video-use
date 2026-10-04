"""Validate camera keys against actual encoded positions and frame clocks."""

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image
import pytest

from helpers import render, visuals


def _filter(spec: dict, **overrides) -> str:
    return visuals.build_reframe_filter(spec, **{"width": 160, "height": 90, "fps": "30", **overrides})


@pytest.mark.parametrize("keys", [
    [], [{"time": -1}], [{"time": 1}, {"time": 1}], [{"time": 2}, {"time": 1}],
    [{"time": float("nan")}], [{"time": 0, "zoom": 3.1}],
    [{"time": 0, "zoom": True}], [{"time": 0, "focus_y": float("inf")}],
    [{"time": 0, "focus_x": -0.1}], [{"time": 0, "typo": 2}],
    [{"zoom": 2}], [None], [{"time": index} for index in range(25)],
])
def test_invalid_camera_keys_fail_before_render(keys) -> None:
    with pytest.raises(ValueError):
        _filter({"keyframes": keys})


@pytest.mark.parametrize("arguments", [{"width": 161}, {"height": None}, {"fps": None}, {"fps": "0/0"}, {"fps": "300"}])
def test_animation_requires_real_dimensions_and_frame_rate(arguments) -> None:
    with pytest.raises(ValueError):
        _filter({"keyframes": [{"time": 0}]}, **arguments)


def _run(*arguments: str) -> bytes:
    return subprocess.run(list(arguments), capture_output=True, check=True, timeout=90).stdout


def _fixture(tmp_path: Path, width: int, height: int, rate: str, frames: int) -> Path:
    # Pixel position is encoded into color, so an actual crop can be measured.
    gradient = np.zeros((height, width, 3), dtype=np.uint8)
    gradient[:, :, 0] = np.linspace(0, 255, width).round().astype(np.uint8)
    gradient[:, :, 1] = np.linspace(0, 255, height).round().astype(np.uint8)[:, None]
    gradient[:, :, 2] = 80
    image = tmp_path / "position-map.png"
    Image.fromarray(gradient).save(image)
    clip = tmp_path / "segment.mp4"
    _run(
        "ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", rate, "-i", str(image),
        "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip),
    )
    base = tmp_path / "base.mp4"
    render.concat_segments([clip, clip, clip], base, tmp_path)
    return base


def _decoded(path: Path, width: int, height: int) -> np.ndarray:
    return np.frombuffer(_run(
        "ffmpeg", "-v", "error", "-i", str(path), "-an", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ), dtype=np.uint8).reshape(-1, height, width, 3)


has_ffmpeg = shutil.which("ffmpeg") and shutil.which("ffprobe")


@pytest.mark.skipif(not has_ffmpeg, reason="Encoded crop checks require ffmpeg and ffprobe")
@pytest.mark.parametrize("width,height,rate,segment_frames", [(160, 90, "24", 16), (90, 160, "30000/1001", 20)])
@pytest.mark.parametrize("interpolation", ["linear", "smooth", "hold"])
def test_output_clock_pan_crosses_cuts_at_the_actual_frame_rate(
    tmp_path: Path, width: int, height: int, rate: str, segment_frames: int, interpolation: str,
) -> None:
    base = _fixture(tmp_path, width, height, rate, segment_frames)
    final = tmp_path / "final.mp4"
    render.build_final_composite(
        base, [], None, final, tmp_path,
        treatment={"reframe": {"interpolation": interpolation, "keyframes": [
            {"time": 0, "zoom": 2, "focus_x": 0, "focus_y": 0},
            {"time": 1, "focus_x": 1, "focus_y": 1},
            {"time": 2, "focus_x": 0, "focus_y": 0},
        ]}},
    )
    decoded = _decoded(final, width, height)
    assert len(decoded) == 3 * segment_frames
    frames = json.loads(_run(
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(final),
    ))["frames"]
    fps = float(Fraction(rate))
    assert [float(frame["best_effort_timestamp_time"]) for frame in frames] == pytest.approx(
        [index / fps for index in range(len(decoded))], abs=0.000002,
    )
    # Include the frames immediately before/after both source joins. The camera
    # keeps moving on the output clock instead of restarting on each clip.
    for index in sorted({0, segment_frames - 1, segment_frames, 2 * segment_frames - 1, 2 * segment_frames, len(decoded) - 1}):
        time = index / fps
        progress = time if time < 1 else time - 1
        if interpolation == "smooth":
            progress = progress * progress * (3 - 2 * progress)
        if interpolation == "hold":
            progress = 0
        focus = progress if time < 1 else 1 - progress
        expected = 255 * (0.25 + 0.5 * focus)
        pixel = decoded[index, height // 2, width // 2, :2].astype(float)
        assert pixel == pytest.approx([expected, expected], abs=9)


@pytest.mark.skipif(not has_ffmpeg, reason="Encoded crop checks require ffmpeg and ffprobe")
def test_zoom_changes_the_visible_source_region_and_holds_final_state(tmp_path: Path) -> None:
    base = _fixture(tmp_path, 160, 90, "30", 20)
    final = tmp_path / "final.mp4"
    render.build_final_composite(
        base, [], None, final, tmp_path,
        treatment={"reframe": {"keyframes": [{"time": 0, "zoom": 1}, {"time": 1, "zoom": 2}]}},
    )
    decoded = _decoded(final, 160, 90)
    assert len(decoded) == 60
    # The quarter-width pixel samples x≈40 at zoom1 and x≈60 at zoom2.
    values = decoded[[0, 30, 59], 45, 40, 0].astype(float)
    assert values == pytest.approx([64, 96, 96], abs=7)
