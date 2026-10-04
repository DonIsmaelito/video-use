"""Encoded evidence that adjacent overlay intervals never share an end frame."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from helpers.render import build_final_composite


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is required"
)


def run(*args):
    return subprocess.run(args, check=True, capture_output=True)


@pytest.mark.parametrize("kind", ["image", "video"])
@pytest.mark.parametrize("start,duration,next_start,active,next_active", [
    (0, .1, .1, [0, 1, 2], [3, 4, 5]),
    (1 / 30, 1 / 30, 2 / 30, [1], [2]),
    (.1001, .1, .2001, [4, 5, 6], [7, 8, 9]),
])
def test_adjacent_overlays_use_output_clock_half_open_intervals(
    tmp_path: Path, kind, start, duration, next_start, active, next_active,
):
    base = tmp_path / "base.mp4"
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x96:r=30",
        "-frames:v", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(base))
    overlays = []
    for name, color, box, begins in (
        ("red", (255, 0, 0, 255), (0, 0, 80, 96), start),
        ("green", (0, 255, 0, 255), (80, 0, 160, 96), next_start),
    ):
        image = Image.new("RGBA", (160, 96), (0, 0, 0, 0))
        image.paste(color, box)
        path = tmp_path / f"{name}.png"
        image.save(path)
        if kind == "video":
            video = path.with_suffix(".mkv")
            run("ffmpeg", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(path),
                "-frames:v", "12", "-c:v", "ffv1", "-pix_fmt", "bgra", str(video))
            path = video
        overlays.append({"file": str(path), "kind": kind,
                         "start_in_output": begins, "duration": duration})
    final = tmp_path / "final.mp4"
    build_final_composite(base, overlays, None, final, tmp_path)
    decoded = run("ffmpeg", "-v", "error", "-i", str(final), "-f", "rawvideo",
                  "-pix_fmt", "rgb24", "-").stdout
    stride = 160 * 96 * 3
    assert len(decoded) == 12 * stride
    for index in range(12):
        frame = Image.frombytes("RGB", (160, 96), decoded[index * stride:(index + 1) * stride])
        left, right = frame.getpixel((30, 48)), frame.getpixel((130, 48))
        assert left[0 if index in active else 2] > 220, (index, "left", left)
        assert right[1 if index in next_active else 2] > 220, (index, "right", right)
        assert left[2 if index in active else 0] < 25, (index, "left", left)
        assert right[2 if index in next_active else 1] < 25, (index, "right", right)
    metadata = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(final)).stdout)
    assert len(metadata["streams"]) == 1
    assert metadata["streams"][0]["nb_frames"] == "12"
