"""Jev live editing on Modal: the session API and page behind HTTPS, with a T4 for encoding.

  uv run --with modal python -m modal deploy experiments/jev/modal_live.py     # prints the URL
Compute: one container (sessions live in-process), T4 GPU for h264_nvenc, 8 CPUs, 16 GB, warm for
ten minutes after the last request; JEV_LIVE_MIN_CONTAINERS=1 at deploy time keeps one warm always.
Secrets: video-use-elevenlabs (ELEVENLABS_API_KEY) and video-use-jev (TYPESAFE_API_KEY).
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

APP_NAME = "jev-live"
SESSIONS = "/sessions"
# image definitions execute at import both locally and in the container (where this file is /root/modal_live.py)
LOCAL_REPO = Path(__file__).resolve().parents[2] if modal.is_local() else Path("/root")
LOCAL_DIR = Path(__file__).resolve().parent if modal.is_local() else Path("/root")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "fonts-liberation", "fonts-dejavu-core")
    .pip_install("fastapi[standard]", "websocket-client", "requests", "pillow")
    .add_local_dir(LOCAL_REPO / "helpers", "/root/helpers", ignore=["__pycache__", "*.pyc"])
    .add_local_file(LOCAL_DIR / "live_api.py", "/root/live_api.py")
    .add_local_file(LOCAL_DIR / "live.html", "/root/live.html")
)
app = modal.App(APP_NAME)
volume = modal.Volume.from_name("jev-live-sessions", create_if_missing=True)
secrets = [modal.Secret.from_name("video-use-elevenlabs"), modal.Secret.from_name("video-use-jev")]


@app.function(image=image, gpu="T4", cpu=8, memory=16384, timeout=3600, scaledown_window=600, max_containers=1,
              min_containers=int(os.environ.get("JEV_LIVE_MIN_CONTAINERS", "0")), secrets=secrets, volumes={SESSIONS: volume})
@modal.concurrent(max_inputs=64)
@modal.asgi_app()
def web():
    import sys
    sys.path.insert(0, "/root")
    from live_api import build_app
    return build_app(Path(SESSIONS), Path("/root/live.html"), on_stop=volume.commit)
