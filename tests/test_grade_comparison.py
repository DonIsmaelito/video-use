"""Frame correspondence, portable replay preflight and failed-render cleanup."""

import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from helpers import grade_comparison as comparison


def config(**changes):
    return {"version": 1, "source": "source.mkv", "source_start": .5, "duration": 1,
            "width": 192, "height": 96, "fps": 12, "audio": "none",
            "rgb_coefficients": [.12, 0, -.06], "wipe": [[0, .5], [1, .5]], **changes}


@pytest.mark.parametrize("changes", [
    {"version": True}, {"duration": float("nan")}, {"source_start": -1},
    {"duration": .12}, {"fps": 12.5}, {"fps": True}, {"width": 191},
    {"width": 4096, "height": 4096}, {"audio": "preserve"}, {"audio": None},
    {"rgb_coefficients": [.25, 0, 0]}, {"rgb_coefficients": [0, 0]},
    {"rgb_coefficients": [0, float("inf"), 0]}, {"source_sha256": "wrong"},
    {"wipe": [[0, 1], [0, .5], [1, 0]]}, {"wipe": [[.1, 1], [1, 0]]},
    {"wipe": [[0, 1], [1.1, 0]]}, {"wipe": [[0, 1.1], [1, 0]]},
    {"wipe": [[0, 1], [1, float("nan")]]}, {"unimplemented_hdr": True},
    {"labels": {"original": "Two\nlines", "corrected": "B", "font": "font.ttf"}},
])
def test_invalid_inputs_fail_before_render(changes):
    with pytest.raises(ValueError):
        comparison.validate_config(config(**changes))


def test_lut_preserves_endpoints_order_and_original_pixels():
    lut = comparison.make_lut([.24, 0, -.24])
    assert np.array_equal(lut[0], [0, 0, 0])
    assert np.array_equal(lut[-1], [255, 255, 255])
    assert np.all(np.diff(lut.astype(int), axis=0) >= 0)
    original = np.arange(256, dtype=np.uint8).reshape(1, 256, 1).repeat(3, axis=2)
    frozen = original.copy()
    out = comparison.compare_frame(original, lut, .5)
    assert np.array_equal(original, frozen)
    assert np.array_equal(out[:, :128], original[:, :128])
    assert np.array_equal(out[0, 128:], lut[128:])
    assert comparison.wipe_position(.5, [(0, 1), (1, 0)]) == .5
    assert comparison.wipe_position(-1, [(0, 1), (1, 0)]) == 1
    assert comparison.wipe_position(2, [(0, 1), (1, 0)]) == 0


@pytest.fixture
def source(tmp_path):
    # Lossless source with a moving marker and a strong frame-specific brightness.
    frames = []
    for index in range(48):
        frame = np.full((96, 192, 3), 30 + index * 4, np.uint8)
        frame[30:60, (index * 3) % 144:(index * 3) % 144 + 24] = 240
        frames.append(frame)
    source = tmp_path / "source.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                    "-s", "192x96", "-r", "24", "-i", "-", "-c:v", "ffv1", str(source)],
                   input=np.stack(frames).tobytes(), check=True)
    spec = tmp_path / "comparison.json"
    spec.write_text(json.dumps(config(fps=24)))
    return spec, np.stack(frames)


def decode(path, width=192, height=96):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-"])
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)


def test_encoded_halves_share_source_frame_crop_and_clock(source, tmp_path):
    spec, frames = source
    output = tmp_path / "comparison.mp4"
    report = comparison.render(spec, output)
    assert (report["frames"], report["fps"], report["duration"], report["audio"]) == (24, 24, 1, "none")
    result = decode(output)
    assert len(result) == 24
    # Matching clocks make exact correspondence independent of container timestamp
    # rounding at half-frame boundaries in a24-to12fps conversion.
    expected = frames[12:36].copy()
    lut = comparison.make_lut([.12, 0, -.06])
    for channel in range(3):
        expected[:, :, 96:, channel] = lut[expected[:, :, 96:, channel], channel]
    for index in range(24):
        for part in (slice(4, 90), slice(102, 188)):
            error = np.abs(result[index, 8:88, part].astype(float) - expected[index, 8:88, part]).mean()
            assert error < 3, (index, part, error)
    assert report["source_sha256"] == comparison.sha256(tmp_path / "source.mkv")
    assert not list(tmp_path.glob(".grade-*.mp4"))


def test_draft_preserves_aspect_ratio_and_existing_outputs(source, tmp_path):
    spec, _ = source
    output = tmp_path / "draft.mp4"
    result = comparison.render(spec, output, width=96)
    assert (result["width"], result["height"]) == (96, 48)
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        comparison.render(spec, output)
    assert output.read_bytes() == before
    original = (tmp_path / "source.mkv").read_bytes()
    with pytest.raises(ValueError, match="must not overwrite"):
        comparison.render(spec, tmp_path / "source.mkv", overwrite=True)
    alias = tmp_path / "hardlink.mp4"
    alias.hardlink_to(tmp_path / "source.mkv")
    with pytest.raises(ValueError, match="must not overwrite"):
        comparison.render(spec, alias, overwrite=True)
    assert (tmp_path / "source.mkv").read_bytes() == original


@pytest.mark.parametrize("changes, message", [
    ({"source_sha256": "0" * 64}, "SHA-256"),
    ({"source_start": 1.5}, "beyond"),
    ({"width": 96}, "aspect ratio"),
])
def test_failed_preflight_preserves_existing_artifact(source, tmp_path, changes, message):
    spec, _ = source
    spec.write_text(json.dumps(config(**changes)))
    output = tmp_path / "comparison.mp4"
    output.write_bytes(b"approved earlier output")
    with pytest.raises(ValueError, match=message):
        comparison.render(spec, output, overwrite=True)
    assert output.read_bytes() == b"approved earlier output"
    assert not list(tmp_path.glob(".grade-*"))


def test_failure_reaps_both_children_and_removes_partial_output(source, tmp_path, monkeypatch):
    spec, _ = source
    output = tmp_path / "comparison.mp4"
    output.write_bytes(b"approved earlier output")
    actual_popen = subprocess.Popen
    children = []

    def track(command, *args, **kwargs):
        process = actual_popen(command, *args, **kwargs)
        if command[0] == "ffmpeg":
            children.append(process)
        return process

    def fail(*_):
        raise RuntimeError("induced source interruption")

    monkeypatch.setattr(comparison.subprocess, "Popen", track)
    monkeypatch.setattr(comparison, "read_exact", fail)
    with pytest.raises(RuntimeError, match="source interruption"):
        comparison.render(spec, output, overwrite=True)
    assert len(children) == 2 and all(p.poll() is not None for p in children)
    assert output.read_bytes() == b"approved earlier output"
    assert not list(tmp_path.glob(".grade-*"))


def test_labels_must_fit_before_output_is_touched(source, tmp_path):
    spec, _ = source
    font = Path(__file__).resolve().parents[1] / "website/public/fonts/inter-regular.ttf"
    if not font.is_file():
        pytest.skip("Project font asset is not in this test snapshot")
    labels = {"font": str(font), "original": "A very long oversized comparison label", "corrected": "B", "font_size": 120}
    spec.write_text(json.dumps(config(labels=labels)))
    output = tmp_path / "comparison.mp4"
    with pytest.raises(ValueError, match="does not fit"):
        comparison.render(spec, output)
    assert not output.exists() and not list(tmp_path.glob(".grade-*"))
