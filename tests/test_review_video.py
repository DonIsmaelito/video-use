import json
import shutil
import subprocess

import pytest
from PIL import Image

from helpers.review_video import review_video, sample_times


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
