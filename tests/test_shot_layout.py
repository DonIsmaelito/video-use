"""Real source-pixel crops and output windows through the shared extractor."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from helpers import render
from helpers.shot_layout import build_shot_layout_filters


def _run(*args: str) -> bytes:
    return subprocess.run(list(args), check=True, capture_output=True, timeout=60).stdout


def _source(path: Path) -> None:
    _run("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=640x360:r=24:d=2",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=2",
         "-vf", "drawbox=x=320:y=0:w=320:h=180:color=green:t=fill,drawbox=x=0:y=180:w=320:h=180:color=blue:t=fill,drawbox=x=320:y=180:w=320:h=180:color=yellow:t=fill",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path))


def _frame(path: Path, width: int, height: int, time: float = 0.2) -> np.ndarray:
    raw = _run("ffmpeg", "-v", "error", "-ss", str(time), "-i", str(path), "-frames:v", "1",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3).astype(int)


def _color(actual: np.ndarray, expected: tuple[int, int, int]) -> None:
    assert np.max(np.abs(actual - expected)) < 7


has_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="Requires FFmpeg")


@has_ffmpeg
def test_original_pixel_crop_and_grade_leave_the_requested_matte_intact(tmp_path):
    source, target = tmp_path / "source.mp4", tmp_path / "out.mp4"
    _source(source)
    spec = {"width": 320, "height": 480, "background": "#102030",
            "crop": {"x": 320, "y": 180, "width": 320, "height": 180},
            "window": {"x": 40, "y": 140, "width": 240, "height": 180, "fit": "contain"}}
    original = copy.deepcopy(spec)
    render.extract_segment(source, 0.1, 1, "eq=saturation=0", target, rate="30", layout=spec)
    image = _frame(target, 320, 480)
    _color(image[10, 10], (16, 32, 48))
    _color(image[145, 160], (16, 32, 48))  # Letterbox inside the picture window.
    assert image[230, 160].min() > 180
    assert np.ptp(image[230, 160]) < 5  # The selected yellow quadrant was graded.
    assert spec == original
    data = json.loads(_run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(target)))
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert int(video["nb_read_frames"]) == 30
    assert float(video["start_time"]) == pytest.approx(0)
    assert any(s["codec_type"] == "audio" for s in data["streams"])


@has_ffmpeg
@pytest.mark.parametrize("fit", ["contain", "cover"])
def test_picture_window_preserves_aspect_and_only_cover_fills_it(tmp_path, fit):
    source, target = tmp_path / "source.mp4", tmp_path / "out.mp4"
    _source(source)
    spec = {"width": 320, "height": 480, "background": "#102030",
            "crop": {"x": 0, "y": 0, "width": 640, "height": 180},
            "window": {"x": 100, "y": 100, "width": 120, "height": 180, "fit": fit}}
    render.extract_segment(source, 0.1, 0.5, "", target, rate="30", layout=spec)
    image = _frame(target, 320, 480)
    _color(image[190, 125], (255, 0, 0))
    _color(image[190, 195], (0, 128, 0))
    _color(image[110, 125], (16, 32, 48) if fit == "contain" else (255, 0, 0))
    _color(image[95, 125], (16, 32, 48))
    _color(image[285, 125], (16, 32, 48))


@has_ffmpeg
def test_preview_scales_canvas_and_window_without_scaling_source_crop(tmp_path):
    source, target = tmp_path / "source.mp4", tmp_path / "out.mp4"
    _source(source)
    spec = {"width": 1200, "height": 1600, "background": "#102030",
            "crop": {"x": 0, "y": 180, "width": 320, "height": 180},
            "window": {"x": 200, "y": 400, "width": 800, "height": 600, "fit": "cover"}}
    render.extract_segment(source, 0.1, 0.5, "", target, preview=True, rate="30", layout=spec)
    image = _frame(target, 960, 1280)
    _color(image[350, 170], (0, 0, 255))
    _color(image[300, 170], (16, 32, 48))
    _color(image[350, 150], (16, 32, 48))
    _color(image[800, 480], (16, 32, 48))


@has_ffmpeg
def test_edl_ranges_switch_windows_without_changing_output_size_or_audio(tmp_path):
    source = tmp_path / "source.mp4"
    _source(source)
    edl = {"sources": {"stock": str(source)}, "ranges": [
        {"source": "stock", "start": 0.1, "end": 0.6,
         "layout": {"width": 320, "height": 480, "crop": {"x": 320, "y": 180, "width": 320, "height": 180}}},
        {"source": "stock", "start": 0.7, "end": 1.2,
         "layout": {"width": 320, "height": 480, "crop": {"x": 0, "y": 180, "width": 320, "height": 180},
                    "window": {"x": 40, "y": 140, "width": 240, "height": 180}}},
    ]}
    clips = render.extract_all_segments(edl, tmp_path, preview=False, fps="30")
    target = tmp_path / "final.mp4"
    render.concat_segments(clips, target, tmp_path)
    _color(_frame(target, 320, 480, 0.25)[10, 10], (255, 255, 0))
    second = _frame(target, 320, 480, 0.75)
    _color(second[10, 10], (0, 0, 0))
    _color(second[230, 160], (0, 0, 255))
    probe = json.loads(_run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(target)))
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert int(video["nb_read_frames"]) == 30
    assert float(video["duration"]) == pytest.approx(1)
    assert any(s["codec_type"] == "audio" for s in probe["streams"])


@pytest.mark.parametrize("changes", [
    {"width": 321}, {"height": float("nan")}, {"width": True}, {"width": 8000},
    {"background": "red"}, {"background": "#000000,reverse"}, {"unknown": 1},
    {"crop": {"x": -2, "y": 0, "width": 640, "height": 360}},
    {"crop": {"x": 2, "y": 0, "width": 640, "height": 360}},
    {"crop": {"x": 0, "y": 0, "width": 640}},
    {"window": {"x": 2}}, {"window": {"width": 0}},
    {"window": {"x": float("inf")}}, {"window": {"fit": "stretch"}},
])
def test_invalid_rectangles_and_unbounded_filter_values_are_rejected(changes):
    with pytest.raises(ValueError):
        build_shot_layout_filters({"width": 320, "height": 480, **changes}, 640, 360)


def test_partial_or_different_canvas_edls_fail_before_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "extract_segment", lambda *a, **k: pytest.fail("must reject before extraction"))
    first = {"source": "source", "start": 0, "end": 1, "layout": {"width": 320, "height": 480}}
    for second in ({"source": "source", "start": 1, "end": 2},
                   {**first, "layout": {"width": 480, "height": 320}}):
        with pytest.raises(ValueError):
            render.extract_all_segments({"sources": {"source": "missing.mp4"}, "ranges": [first, second]}, tmp_path, False)
