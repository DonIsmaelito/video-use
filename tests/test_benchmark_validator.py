from __future__ import annotations

import shutil
import subprocess

import pytest

from benchmarks.validator import validate_task_outputs


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required for synthetic media validation",
)


def test_synthetic_vertical_h264_aac_media_and_caption_validation(tmp_path) -> None:
    deliverables = tmp_path / "deliverables"
    deliverables.mkdir()
    video = deliverables / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=180x320:r=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(video),
    ], check=True, timeout=60)
    video.with_suffix(".srt").write_text(
        "1\n00:00:00,000 --> 00:00:00,900\nSynthetic caption\n",
        encoding="utf-8",
    )
    task = {
        "outputs": {
            "glob": "deliverables/*.mp4",
            "min_count": 1,
            "validation": {
                "min_duration_s": 0.5,
                "max_duration_s": 2.0,
                "width": 180,
                "height": 320,
                "aspect_ratio": "9:16",
                "fps": 30,
                "video_codec": "h264",
                "audio_codec": "aac",
                "require_audio": True,
                "require_audible_audio": True,
                "require_caption_sidecar": True,
            },
        }
    }

    valid = validate_task_outputs(tmp_path, task)
    assert valid["passed"] is True
    assert valid["clip_count"] == 1
    assert 0.9 <= valid["total_duration_s"] <= 1.1

    video.with_suffix(".srt").unlink()
    invalid = validate_task_outputs(tmp_path, task)
    assert invalid["passed"] is False
    assert any("missing caption sidecar" in error for error in invalid["errors"])
