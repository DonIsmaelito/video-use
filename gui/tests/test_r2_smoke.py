from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest
import requests

from gui.r2_storage import R2Storage, video_object_key


@pytest.mark.skipif(
    os.environ.get("VIDEO_USE_R2_SMOKE") != "1",
    reason="set VIDEO_USE_R2_SMOKE=1 with R2 credentials to run",
)
def test_real_r2_public_range_playback_and_delete(tmp_path: Path) -> None:
    storage = R2Storage.from_env()
    run_id = f"smoke-{uuid.uuid4().hex}"
    key = video_object_key(run_id, "range-test")
    source = tmp_path / "range-test.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=1:r=24",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    payload = source.read_bytes()
    try:
        url = storage.upload_file(source, key, content_type="video/mp4")
        playback = requests.get(url, timeout=30)
        assert playback.status_code == 200
        assert b"ftyp" in playback.content[:32]
        response = requests.get(url, headers={"Range": "bytes=128-255"}, timeout=30)
        assert response.status_code == 206
        assert response.content == payload[128:256]
        assert response.headers["Accept-Ranges"].casefold() == "bytes"
    finally:
        storage.delete_run(run_id)
