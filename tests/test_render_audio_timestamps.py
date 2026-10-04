"""Encoded regression checks for AAC priming across lossless video cuts."""

from __future__ import annotations

import json
from fractions import Fraction
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from helpers import render


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required for encoded timing checks",
)


def _run(*arguments: str) -> bytes:
    return subprocess.run(
        list(arguments), check=True, capture_output=True, timeout=60,
    ).stdout


def _probe(path: Path) -> dict:
    return json.loads(_run(
        "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ))


def _pulse_clip(path: Path, sample_rate: int, pulse_frame: int, audio_delay: float = 0) -> None:
    """An exact 24-frame clip, with a three-frame flash and matching tone."""
    start = pulse_frame / 30
    end = (pulse_frame + 3) / 30
    _run(
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=black:s=160x90:r=30:d=0.8",
        "-itsoffset", str(audio_delay),
        "-f", "lavfi", "-i",
        f"aevalsrc='0.6*sin(2*PI*1000*t)*gte(t,{start})*lt(t,{end})':s={sample_rate}:d=0.8",
        "-vf", f"drawbox=color=white:t=fill:enable='gte(n,{pulse_frame})*lt(n,{pulse_frame + 3})'",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-t", "0.8", str(path),
    )


def _event_times(path: Path, sample_rate: int, expected_centers: list[float]) -> tuple[list[int], list[float]]:
    video = np.frombuffer(_run(
        "ffmpeg", "-v", "error", "-i", str(path), "-an", "-vf", "scale=1:1",
        "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1",
    ), dtype=np.uint8)
    flashes = np.flatnonzero(video > 128).tolist()
    # Respect packet presentation times while decoding to a continuous PCM
    # clock. Raw PCM alone discards packet gaps at AAC concatenation seams.
    audio = np.frombuffer(_run(
        "ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
        "-ar", str(sample_rate), "-af", "aresample=async=1:first_pts=0",
        "-f", "f32le", "pipe:1",
    ), dtype="<f4").astype(np.float64)
    centers = []
    for expected in expected_centers:
        low = round((expected - 0.16) * sample_rate)
        high = round((expected + 0.16) * sample_rate)
        energy = audio[low:high] ** 2
        assert energy.sum() > 0.01, "Expected synchronized tone is missing"
        times = np.arange(low, low + len(energy)) / sample_rate
        centers.append(float(np.sum(times * energy) / np.sum(energy)))
    return flashes, centers


@pytest.mark.parametrize("sample_rate", [44100, 48000])
def test_aac_concat_and_composite_keep_frames_and_three_events_aligned(
    tmp_path: Path, sample_rate: int,
) -> None:
    clips = [tmp_path / f"segment-{index}.mp4" for index in range(3)]
    pulse_frames = [9, 12, 9]
    for path, frame in zip(clips, pulse_frames):
        _pulse_clip(path, sample_rate, frame)
    expected_flashes = [9, 10, 11, 36, 37, 38, 57, 58, 59]
    expected_centers = [0.35, 1.25, 1.95]
    base = tmp_path / "base.mp4"
    final = tmp_path / "final.mp4"
    render.concat_segments(clips, base, tmp_path)
    render.build_final_composite(
        base, [], None, final, tmp_path,
        treatment={"canvas": {"width": 160, "height": 90, "fit": "cover"}},
    )
    for path in (base, final):
        metadata = _probe(path)
        video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        audio = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        assert int(video["nb_read_frames"]) == 72
        assert float(video["start_time"]) == pytest.approx(0, abs=1e-6)
        assert float(audio["start_time"]) == pytest.approx(0, abs=1e-6)
        assert float(metadata["format"]["duration"]) == pytest.approx(2.4, abs=0.001)
        assert int(audio["sample_rate"]) == sample_rate
        flashes, centers = _event_times(path, sample_rate, expected_centers)
        assert flashes == expected_flashes
        # A fixed 21-ms trim cannot pass both sample rates and all three cuts.
        assert centers == pytest.approx(expected_centers, abs=0.008)


@pytest.mark.parametrize("audio_delay", [-0.1, 0.1])
def test_concat_preserves_measured_source_audio_offsets(tmp_path: Path, audio_delay: float) -> None:
    clips = [tmp_path / f"offset-{index}.mp4" for index in range(3)]
    expected = []
    for index, path in enumerate(clips):
        _pulse_clip(path, 48000, 9, audio_delay=audio_delay)
        _, centers = _event_times(path, 48000, [0.35 + audio_delay])
        expected.append(centers[0] + index * 0.8)
    output = tmp_path / "joined.mp4"
    render.concat_segments(clips, output, tmp_path)
    flashes, centers = _event_times(output, 48000, expected)
    assert flashes == [9, 10, 11, 33, 34, 35, 57, 58, 59]
    assert centers == pytest.approx(expected, abs=0.008)


def test_concat_keeps_a_missing_audio_segment_silent(tmp_path: Path) -> None:
    source = tmp_path / "pulse.mp4"
    silent = tmp_path / "silent.mp4"
    _pulse_clip(source, 48000, 9)
    _run("ffmpeg", "-y", "-v", "error", "-i", str(source), "-c:v", "copy", "-an", str(silent))
    output = tmp_path / "joined.mp4"
    render.concat_segments([source, silent, source], output, tmp_path)
    _, centers = _event_times(output, 48000, [0.35, 1.95])
    assert centers == pytest.approx([0.35, 1.95], abs=0.008)
    middle = np.frombuffer(_run(
        "ffmpeg", "-v", "error", "-i", str(output), "-vn", "-ac", "1",
        "-af", "atrim=start=0.85:end=1.55", "-f", "f32le", "pipe:1",
    ), dtype="<f4")
    assert np.max(np.abs(middle)) < 1e-4


def test_concat_preserves_a_video_only_edit_without_an_audio_stream(tmp_path: Path) -> None:
    source = tmp_path / "pulse.mp4"
    silent = tmp_path / "silent.mp4"
    _pulse_clip(source, 48000, 9)
    _run("ffmpeg", "-y", "-v", "error", "-i", str(source), "-c:v", "copy", "-an", str(silent))
    output = tmp_path / "joined.mp4"
    render.concat_segments([silent, silent, silent], output, tmp_path)
    streams = _probe(output)["streams"]
    assert len(streams) == 1
    assert streams[0]["codec_type"] == "video"
    assert int(streams[0]["nb_read_frames"]) == 72
    assert float(streams[0]["start_time"]) == pytest.approx(0, abs=1e-6)


def test_real_extraction_concat_and_composite_keep_exact_timing(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    _pulse_clip(source, 44100, 9)
    clips = []
    for index, (start, duration) in enumerate([(0, 0.6), (0.1, 0.5), (0.2, 0.4)]):
        path = tmp_path / f"cut-{index}.mp4"
        render.extract_segment(source, start, duration, "", path, rate="30")
        clips.append(path)
    base = tmp_path / "base.mp4"
    final = tmp_path / "final.mp4"
    render.concat_segments(clips, base, tmp_path)
    render.build_final_composite(
        base, [], None, final, tmp_path,
        treatment={"canvas": {"width": 160, "height": 90, "fit": "cover"}},
    )
    streams = _probe(final)["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert int(video["nb_read_frames"]) == 45
    assert float(video["duration"]) == pytest.approx(1.5)
    flashes, centers = _event_times(final, 48000, [0.35, 0.85, 1.25])
    assert flashes == [9, 10, 11, 24, 25, 26, 36, 37, 38]
    assert centers == pytest.approx([0.35, 0.85, 1.25], abs=0.008)


@pytest.mark.parametrize("source_rate", ["24", "24000/1001"])
@pytest.mark.parametrize("with_audio", [False, True])
def test_mixed_rate_cuts_fill_the_first_frame_without_moving_audio(tmp_path: Path, source_rate: str, with_audio: bool) -> None:
    source = tmp_path / "source.mp4"
    rate = float(Fraction(source_rate))
    pulse_start, pulse_end = 42 / rate, 45 / rate
    _run(
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        f"color=c=black:s=160x90:r={source_rate}:d=4",
        *(["-f", "lavfi", "-i", f"aevalsrc='0.6*sin(2*PI*1000*t)*gte(t,{pulse_start})*lt(t,{pulse_end})':s=48000:d=4"] if with_audio else []),
        "-vf", "drawbox=color=white:t=fill:enable='gte(n,42)*lt(n,45)'",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    )
    clips = []
    expected = []
    for index, start in enumerate([1.3, 0.7, 1.5]):
        path = tmp_path / f"cut-{index}.mp4"
        render.extract_segment(source, start, 1.4, "", path, rate="30")
        stream = next(s for s in _probe(path)["streams"] if s["codec_type"] == "video")
        assert int(stream["nb_read_frames"]) == 42
        assert float(stream["start_time"]) == pytest.approx(0, abs=1e-6)
        clips.append(path)
        expected.append((pulse_start + pulse_end) / 2 - start + index * 1.4)
    output = tmp_path / "joined.mp4"
    render.concat_segments(clips, output, tmp_path)
    if with_audio:
        flashes, centers = _event_times(output, 48000, expected)
        assert centers == pytest.approx(expected, abs=0.008)
    else:
        pixels = np.frombuffer(_run("ffmpeg", "-v", "error", "-i", str(output), "-vf", "scale=1:1", "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"), dtype=np.uint8)
        flashes, centers = np.flatnonzero(pixels > 128).tolist(), expected
    for index, center in enumerate(centers):
        visible = [frame for frame in flashes if index * 42 <= frame < (index + 1) * 42]
        assert visible
        visible_center = (visible[0] + visible[-1] + 1) / 60
        assert visible_center == pytest.approx(center, abs=1 / 30)
    video = next(s for s in _probe(output)["streams"] if s["codec_type"] == "video")
    assert int(video["nb_read_frames"]) == 126
    assert float(video["duration"]) == pytest.approx(4.2, abs=0.001)
