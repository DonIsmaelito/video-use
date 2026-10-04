"""The inclusive last timeline sample is an actual frame, never an empty JPEG."""
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image
import pytest

from helpers.timeline_view import extract_frames


pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")


def source(path, origin=0, vfr=False):
    filters = "drawbox=color=blue:t=fill:enable='eq(n,5)'"
    if vfr:
        filters += ",setpts='if(lt(N,5),N*0.04/TB,0.4/TB)'"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=red:s=160x90:r=30:d=0.2", "-vf", filters,
                    "-c:v", "ffv1", "-fps_mode", "passthrough", "-output_ts_offset", str(origin), str(path)],
                   check=True, capture_output=True)
    data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(path)]))
    return float(data["format"]["duration"]) - float(data["format"].get("start_time", 0))


@pytest.mark.parametrize("origin", [0, 2])
@pytest.mark.parametrize("vfr", [False, True])
def test_actual_final_frame_at_inclusive_endpoint(tmp_path, origin, vfr):
    video = tmp_path / "source.mkv"
    duration = source(video, origin, vfr)
    folder = tmp_path / "frames"
    folder.mkdir()
    (folder / "f_002.jpg").write_bytes(b"stale JPEG must not be reused")
    frames = extract_frames(video, 0, duration, 3, folder)
    first, last = (np.asarray(Image.open(frames[i])).mean(axis=(0, 1)) for i in (0, -1))
    assert first[0] > 230 and first[2] < 20
    assert last[2] > 230 and last[0] < 20
    assert all(p.is_file() and p.stat().st_size > 0 for p in frames)


def test_out_of_range_is_rejected_instead_of_inventing_a_hold(tmp_path):
    video = tmp_path / "source.mkv"
    duration = source(video)
    with pytest.raises(ValueError, match="No video frame"):
        extract_frames(video, 0, duration + .1, 2, tmp_path / "frames")


@pytest.mark.parametrize("start,end,n", [(float('nan'),1,2), (0,float('inf'),2), (2,1,2),(-1,1,2),(0,1,300)])
def test_invalid_ranges_fail_before_decoding(tmp_path, start, end, n):
    with pytest.raises(ValueError):
        extract_frames(tmp_path / "absent.mp4", start, end, n, tmp_path / "frames")
