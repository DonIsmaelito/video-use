#!/usr/bin/env python3
"""Local live editing server: the same API and page as the Modal app, on this Mac.

  uv run --with fastapi --with 'uvicorn[standard]' --with websocket-client python experiments/jev/live_server.py   # http://127.0.0.1:8791
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from live_api import build_app  # noqa: E402

ROOT = Path(os.environ.get("JEV_LIVE_OUT", "~/Movies/video-use-tests/live-sessions")).expanduser()
app = build_app(ROOT, HERE / "live.html")

if __name__ == "__main__":
    import uvicorn
    ROOT.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("JEV_LIVE_PORT", "8791")), log_level="warning")
