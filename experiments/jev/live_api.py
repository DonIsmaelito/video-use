"""The live-session HTTP/WebSocket API shared by the local server and the Modal app.

  build_app(sessions_root, page_path) -> FastAPI

  POST /api/session {frame, language, clip_threshold, container}   -> {id}
  WS   /ws/{id}/audio            binary frames of 16 kHz mono int16 PCM; text "stop" ends the audio
  POST /api/session/{id}/video?offset=N   raw bytes appended to the recording (webm or mp4 as the browser records)
  GET  /api/session/{id}/events?since=N&wait=S   server-sent events (backlog from N, closes after S seconds with type "more")
  POST /api/session/{id}/stop    -> summary (blocks until the remaining clips are rendered)
  GET  /api/session/{id}         -> state
  GET  /clips/{id}/{name}        -> clip file (.mp4/.srt/.json)
  GET  /                         -> the page
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    frame: str = Field(default="crop", pattern="^(crop|contain)$")
    language: str = "en"
    clip_threshold: float = 0.35
    container: str = Field(default="webm", pattern="^(webm|mp4)$")


def build_app(sessions_root: Path, page_path: Path | None = None, on_stop=None) -> FastAPI:
    from helpers.live_session import LiveSession

    api = FastAPI(title="jev-live")
    api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    sessions: dict[str, dict] = {}
    lock = threading.Lock()

    def get(sid: str) -> dict:
        s = sessions.get(sid)
        if not s:
            raise HTTPException(404, "unknown session")
        return s

    @api.get("/", response_class=HTMLResponse)
    def index() -> str:
        if page_path and page_path.is_file():
            return page_path.read_text()
        rows = "".join(f"<li>{sid}: {s['status']} · {len(s['events'])} events · {len(s['session'].clips)} clips</li>" for sid, s in sessions.items())
        return f"<html><body style='font-family:sans-serif'><h2>jev-live</h2><ul>{rows}</ul></body></html>"

    @api.get("/api/health")
    def health() -> dict:
        return {"ok": True, "sessions": len(sessions), "t": time.time()}

    @api.post("/api/session")
    def start(req: StartRequest) -> dict:
        sid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        entry = {"id": sid, "status": "running", "events": [], "created": time.time()}

        def on_event(ev: dict) -> None:
            with lock:
                entry["events"].append(ev)

        sess = LiveSession(sessions_root / sid, mode="remote", frame=req.frame, language=req.language, clip_threshold=req.clip_threshold, container=req.container, on_event=on_event)
        entry["session"] = sess
        with lock:
            sessions[sid] = entry
        sess.start()
        return {"id": sid}

    @api.websocket("/ws/{sid}/audio")
    async def audio(ws: WebSocket, sid: str):
        entry = get(sid)
        sess = entry["session"]
        await ws.accept()
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    sess.feed_audio(msg["bytes"])
                elif msg.get("text") == "stop":
                    break
        except WebSocketDisconnect:
            pass

    @api.post("/api/session/{sid}/video")
    async def video(sid: str, request: Request, offset: int | None = None) -> dict:
        entry = get(sid)
        data = await request.body()
        return {"bytes": entry["session"].append_video(data, offset)}

    @api.post("/api/session/{sid}/stop")
    def stop(sid: str) -> dict:
        entry = get(sid)
        if entry["status"] == "running":
            entry["status"] = "stopping"
            summary = entry["session"].stop()
            entry["status"] = "done"
            entry["summary"] = summary
            if on_stop:
                on_stop()
        return {"id": sid, "status": entry["status"], **{k: v for k, v in (entry.get("summary") or {}).items() if k != "clips"}, "clips": [c["clip"] for c in entry["session"].clips]}

    @api.get("/api/session/{sid}/events")
    def events(sid: str, since: int = 0, wait: float = 60.0):
        entry = get(sid)

        def gen():
            i = since; t0 = time.time()
            while True:
                with lock:
                    batch = entry["events"][i:]
                for ev in batch:
                    yield f"data: {json.dumps({**ev, 'i': i})}\n\n"; i += 1
                if entry["status"] == "done" and i >= len(entry["events"]):
                    yield f"data: {json.dumps({'type': 'end', 'i': i})}\n\n"; return
                if time.time() - t0 > wait:
                    yield f"data: {json.dumps({'type': 'more', 'i': i})}\n\n"; return
                time.sleep(0.2)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @api.get("/api/session/{sid}")
    def state(sid: str) -> dict:
        entry = get(sid)
        return {"id": sid, "status": entry["status"], "events": len(entry["events"]), "clips": [{k: v for k, v in c.items() if k in ("clip", "duration_s", "render_s", "hook_line", "scores", "encoder", "captions")} for c in entry["session"].clips]}

    @api.get("/clips/{sid}/{name}")
    def clip(sid: str, name: str):
        get(sid)
        path = sessions_root / sid / "clips" / name
        if ".." in name or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "application/octet-stream")

    return api
