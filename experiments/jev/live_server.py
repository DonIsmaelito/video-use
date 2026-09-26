#!/usr/bin/env python3
"""Live editing UI: record from the Mac camera and mic (or replay a file), watch the transcript and
Jev's calls arrive, and see finished vertical clips pop up while you are still talking.

  uv run --with fastapi --with 'uvicorn[standard]' python experiments/jev/live_server.py   # http://127.0.0.1:8791
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from helpers.live_session import LiveSession  # noqa: E402

ROOT = Path(os.environ.get("JEV_LIVE_OUT", "~/Movies/video-use-tests/live-sessions")).expanduser()
DEFAULT_REPLAY = str(Path("~/Movies/video-use-tests/harness-projects/jensen-iltb/iltb_jensen.mp4").expanduser())
app = FastAPI(title="Jev live editing")
state: dict = {"session": None, "id": None, "events": [], "subs": [], "lock": threading.Lock()}


class StartRequest(BaseModel):
    mode: str = Field(default="mic", pattern="^(mic|replay)$")
    source: str | None = None
    start: float = 776.0
    duration: float | None = 120.0
    frame: str = Field(default="crop", pattern="^(crop|contain)$")


def publish(ev: dict) -> None:
    with state["lock"]:
        state["events"].append(ev)
        for q in state["subs"]:
            q.put(ev)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (HERE / "live.html").read_text()


@app.post("/api/start")
def start(req: StartRequest) -> dict:
    if state["session"] is not None:
        raise HTTPException(409, "a session is already running; stop it first")
    sid = time.strftime("%Y%m%d-%H%M%S")
    state["events"] = []
    sess = LiveSession(ROOT / sid, mode=req.mode, source=req.source or DEFAULT_REPLAY, start_s=req.start, duration_s=req.duration if req.mode == "replay" else None, frame=req.frame, on_event=publish)
    state["session"], state["id"] = sess, sid
    sess.start()
    if req.mode == "replay" and req.duration:
        def auto_stop():
            time.sleep(req.duration + 1.5)
            if state["session"] is sess:
                stop()
        threading.Thread(target=auto_stop, daemon=True).start()
    return {"id": sid, "mode": req.mode}


@app.post("/api/stop")
def stop() -> dict:
    sess = state["session"]
    if sess is None:
        raise HTTPException(409, "no session running")
    state["session"] = None
    summary = sess.stop()
    return {"id": state["id"], **summary}


@app.get("/api/events")
def events():
    q: queue.Queue = queue.Queue()
    with state["lock"]:
        backlog = list(state["events"]); state["subs"].append(q)

    def gen():
        try:
            for ev in backlog:
                yield f"data: {json.dumps(ev)}\n\n"
            while True:
                try:
                    ev = q.get(timeout=20)
                except queue.Empty:
                    yield ": keepalive\n\n"; continue
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            with state["lock"]:
                if q in state["subs"]:
                    state["subs"].remove(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/state")
def get_state() -> dict:
    return {"running": state["session"] is not None, "id": state["id"], "events": len(state["events"])}


@app.get("/clips/{sid}/{name}")
def clip(sid: str, name: str):
    path = ROOT / sid / "clips" / name
    if not path.is_file() or ".." in name:
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "text/plain")


if __name__ == "__main__":
    import uvicorn
    ROOT.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("JEV_LIVE_PORT", "8791")), log_level="warning")
