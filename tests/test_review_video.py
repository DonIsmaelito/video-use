import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from helpers.review_video import measure_audio_evidence, review_video, sample_times


def test_review_covers_each_solar_beat_and_end():
    durations = [5, 4, 4, 5.5, 6, 5.5]
    times = sample_times(30.07, 30, [{"seconds": d} for d in durations])
    assert len(times) == 12
    assert times[0] <= 0.2
    assert times[-1] > 29.9
    start = 0
    for duration in durations:
        # Hold sampling covers labels missed by the previous four-frame sheet.
        assert any(start + duration * 0.4 <= t <= start + duration * 0.8 for t in times)
        start += duration
    assert any(14 < t < 18 for t in times)


def test_stale_plan_falls_back_to_uniform_full_timeline():
    times = sample_times(30, 30, [{"seconds": 60}])
    assert times == sample_times(30, 30)
    assert max(b - a for a, b in zip(times, times[1:])) < 3


@pytest.mark.parametrize("duration,fps", [(0.01, 30), (0.1, 30), (1, 2), (30, 30)])
def test_short_clips_have_distinct_bounded_decodable_samples(duration, fps):
    times = sample_times(duration, fps)
    assert 1 <= len(times) <= 12
    assert times == sorted(set(times))
    assert all(0 <= t < duration for t in times)


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf")])
def test_bad_duration_rejected(duration):
    with pytest.raises(ValueError, match="duration"):
        sample_times(duration, 30)


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
@pytest.mark.parametrize("size", ["640x360", "360x640"])
def test_encoded_contact_sheet_preserves_visible_frames_and_shape(tmp_path, size):
    video = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate=12:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    output = tmp_path / "review" / "sheet.png"
    report = review_video(video, output)
    assert report["audio_evidence"]["status"] == "no_audio"
    assert report["audio_evidence"]["warnings"] == []
    assert len(report["sample_times"]) == 12
    with Image.open(output) as sheet:
        assert max(sheet.size) <= 1600
        assert sheet.width == report["width"]
        assert sheet.height == report["height"]
        # A successfully written but blank sheet would invalidate the review.
        assert len(sheet.getcolors(sheet.width * sheet.height)) > 100
    assert (
        json.loads(output.with_suffix(".json").read_text())["sample_times"]
        == report["sample_times"]
    )


def encoded_audio_fixture(tmp_path, source):
    path = tmp_path / "audio fixture's clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=purple:s=160x90:r=2:d=2",
            "-f",
            "lavfi",
            "-i",
            source,
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            str(path),
        ],
        check=True,
        timeout=10,
    )
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
    return path, metadata


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
@pytest.mark.parametrize("silent", [False, True])
def test_encoded_audio_measurements_are_reported_without_claiming_listening(
    tmp_path, silent
):
    source = (
        "anullsrc=r=48000:cl=mono" if silent else "sine=frequency=440:sample_rate=48000"
    )
    path, _ = encoded_audio_fixture(tmp_path, source)
    output = tmp_path / "review" / "sheet.png"
    result = review_video(path, output)
    audio = result["audio_evidence"]
    assert audio["status"] == "measured"
    assert audio["coverage"] == "complete_first_audio_track"
    assert audio["stream_duration_seconds"] == pytest.approx(2, abs=0.05)
    assert audio["measured_seconds"] == pytest.approx(2, abs=0.05)
    assert audio["audio_video_start_offset_seconds"] == pytest.approx(0, abs=0.05)
    assert audio["codec"] == "aac" and audio["audio_stream_count"] == 1
    assert "not listening" in audio["limitations"]
    assert "do not prove sync" in audio["limitations"]
    assert audio["digital_silence"] is silent
    if silent:
        assert audio["true_peak_dbtp"] is None
        assert audio["integrated_loudness_lufs"] is None
        assert any("silent" in warning for warning in audio["warnings"])
    else:
        assert -30 < audio["integrated_loudness_lufs"] < -10
        assert -30 < audio["true_peak_dbtp"] < -10
        assert -30 < audio["mean_volume_dbfs"] < -10
        assert audio["warnings"] == []
    persisted = json.loads(output.with_suffix(".json").read_text())
    assert persisted["audio_evidence"] == audio
    assert len(persisted["sample_times"]) == 4


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_bounded_audio_prefix_is_never_reported_as_complete(tmp_path):
    path, metadata = encoded_audio_fixture(
        tmp_path, "sine=frequency=440:sample_rate=48000"
    )
    audio = measure_audio_evidence(path, metadata, max_seconds=0.5)
    assert audio["status"] == "partial"
    assert audio["coverage"] == "audio_prefix_only"
    assert audio["measured_seconds"] == pytest.approx(0.5, abs=0.01)
    assert any("does not cover" in warning for warning in audio["warnings"])


@pytest.mark.parametrize("failure", ["timeout", "decoder", "no_measurement"])
def test_audio_measurement_errors_are_explicit_without_fabricating_a_pass(
    tmp_path, monkeypatch, failure
):
    metadata = {"streams": [{"codec_type": "audio", "index": 1, "duration": "2"}]}

    def analyze(command, **kwargs):
        assert kwargs["timeout"] <= 20
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert not kwargs.get("shell")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return SimpleNamespace(returncode=1 if failure == "decoder" else 0)

    monkeypatch.setattr(subprocess, "run", analyze)
    audio = measure_audio_evidence(tmp_path / "clip.mp4", metadata)
    assert audio["status"] == "unavailable"
    assert audio["error"]
    assert "integrated_loudness_lufs" not in audio
    assert "digital_silence" not in audio


def test_no_audio_stream_skips_audio_decoder(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A video without audio must not start an audio analysis process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    audio = measure_audio_evidence(
        tmp_path / "clip.mp4", {"streams": [{"codec_type": "video"}]}
    )
    assert audio["status"] == "no_audio"
    assert audio["warnings"] == []
