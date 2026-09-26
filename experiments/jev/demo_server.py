#!/usr/bin/env python3
"""Local demo: type a motion-design query, press Start, watch Jev decide and the piece render.

  uv run --with fastapi --with 'uvicorn[standard]' python experiments/jev/demo_server.py   # http://127.0.0.1:8790

The page streams every pipeline event (Jev's questions, choices and probabilities, render frames, the
delivery gate) over server-sent events, keeps a running timer, and pops the finished video up.
Runs are serialised because one Chrome render saturates the machine.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from helpers.fast_motion import run_pipeline  # noqa: E402

OUT = Path(os.environ.get("JEV_DEMO_OUT", "~/Movies/video-use-tests/jev-trace-study/fastmotion/demo")).expanduser()
PRESETS = [
    {"prompt": "Make the word MELT drop in and bounce, warm and playful", "note": "typography, spring, about 14 s"},
    {"prompt": "Launch title \"OPEN FIELD\" on a dark background, fast and confident", "note": "typography, decisive, about 11 s"},
    {"prompt": "Too many tabs open in my head, then one clear thought", "note": "kinetic type film, about 11 s"},
    {"prompt": "A checkerboard peels into a galloping zebra on a lime field", "note": "illustrated recipe, about 13 s"},
    {"prompt": "The word BREATHE settles slowly on ivory paper", "note": "typography, calm 8 s piece, about 18 s"},
    {"prompt": "A blue ink droplet becomes an octopus on old paper", "note": "heavy canvas recipe, about 22 s"},
]

app = FastAPI(title="Jev in action")
jobs: dict[str, dict] = {}
run_lock = threading.Lock()


class RunRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=400)


def _worker(job_id: str, prompt: str) -> None:
    job = jobs[job_id]
    q: queue.Queue = job["queue"]

    def on_event(ev: dict) -> None:
        q.put(ev)

    if run_lock.locked():
        q.put({"t": 0, "stage": "queue", "msg": "another render is running; waiting for it"})
    with run_lock:
        job["started"] = time.time()
        try:
            report = run_pipeline(prompt, OUT / job_id, on_event=on_event)
            job["report"] = report
            job["video"] = report["output"]
            job["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            job["status"] = "error"
            q.put({"t": 0, "stage": "error", "msg": str(exc)[:400]})
        finally:
            q.put(None)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (HERE / "demo.html").read_text()


@app.get("/api/presets")
def presets() -> list[dict]:
    return PRESETS


@app.post("/api/run")
def start(req: RunRequest) -> dict:
    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {"id": job_id, "prompt": req.prompt, "status": "running", "queue": queue.Queue(), "created": time.time()}
    threading.Thread(target=_worker, args=(job_id, req.prompt), daemon=True).start()
    return {"id": job_id}


@app.get("/api/jobs/{job_id}/events")
def events(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404)

    def gen():
        q: queue.Queue = job["queue"]
        while True:
            try:
                ev = q.get(timeout=25)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if ev is None:
                final = {"stage": "end", "status": job["status"], "video": f"/videos/{job_id}" if job.get("video") else None, "report": job.get("report")}
                yield f"data: {json.dumps(final)}\n\n"
                return
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/videos/{job_id}")
def video(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("video"):
        raise HTTPException(404)
    return FileResponse(job["video"], media_type="video/mp4")


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [{"id": j["id"], "prompt": j["prompt"], "status": j["status"], "total_s": (j.get("report") or {}).get("stages", {}).get("total_s"), "decisions": (j.get("report") or {}).get("decisions")} for j in sorted(jobs.values(), key=lambda j: -j["created"])]


if __name__ == "__main__":
    import uvicorn

    OUT.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("JEV_DEMO_PORT", "8790")), log_level="warning")
