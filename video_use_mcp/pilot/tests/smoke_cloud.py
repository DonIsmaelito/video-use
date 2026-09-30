"""Opt-in real render and speech smoke test. Uses isolated backend fixtures only.

Run from the worktree with PILOT_LIVE_TEST=1. Requires .env.pilot-test,
.pilot-test-users.json and a built Modal image ID in .pilot-image.
"""

import os
import tempfile

import json
import time
import base64
from pathlib import Path

from dotenv import load_dotenv
import modal
from fastapi.testclient import TestClient
from video_use_mcp.pilot.config import Config
from video_use_mcp.pilot.store import Store
from video_use_mcp.pilot.runtime import Manager
from video_use_mcp.pilot.server import create_app

if os.getenv("PILOT_LIVE_TEST") != "1":
    raise SystemExit("Set PILOT_LIVE_TEST=1 to authorize test rendering and speech")
artifacts = Path(tempfile.mkdtemp(prefix="video-pilot-smoke-"))
load_dotenv(".env.pilot-test", interpolate=False)
cfg = Config.env()
s = Store(cfg)
users = json.loads(Path(".pilot-test-users.json").read_text())
uid = users[0]["user"]["id"]
# Integration account was created only on the isolated test branch.
assert cfg.insforge_url.startswith("https://f7e2vbn5-") and cfg.insforge_url.endswith(
    ".us-west.insforge.app"
)
manager = Manager(s, cfg, modal.Image.from_id(Path(".pilot-image").read_text()))
app = create_app(cfg, s, manager)
grant = app.state.auth.issue(uid, "runtime-smoke", ["video:read", "video:write"])
headers = {
    "Authorization": "Bearer " + grant.access_token,
    "Accept": "application/json, text/event-stream",
}
seq = 0
with TestClient(app, base_url=cfg.public_url) as c:

    def call(name, args):
        global seq
        seq += 1
        response = c.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": seq,
                "method": "tools/call",
                "params": {"name": name, "arguments": args},
            },
        )
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        result = data["result"]
        if result.get("isError"):
            raise RuntimeError(result["content"][0]["text"])
        return result

    def value(result):
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])

    def wait(result):
        task = value(result)
        tid = task["id"]
        print("Task:", task["operation"], tid, flush=True)
        for _ in range(180):
            result = call("get_video_task", {"task_id": tid})
            t = value(result)
            if t["status"] in ("succeeded", "failed", "cancelled"):
                if t["status"] != "succeeded":
                    raise RuntimeError(t["error"])
                for block in result["content"]:
                    if block["type"] == "image":
                        (artifacts / "review.png").write_bytes(
                            base64.b64decode(block["data"])
                        )
                print("Completed:", task["operation"], flush=True)
                return t
            time.sleep(2)
        raise TimeoutError(tid)

    p = value(call("create_video_project", {"title": "Pilot render verification"}))
    pid = p["id"]

    def run(command, rid):
        return wait(
            call(
                "run_video_command",
                {
                    "project_id": pid,
                    "command": command,
                    "request_id": pid + rid,
                    "timeout": 300,
                },
            )
        )

    wait(
        call(
            "write_video_file",
            {
                "project_id": pid,
                "path": "edit/project.md",
                "content": "A four second pilot verification card. Render with ffmpeg; preserve this note for revisions.",
                "request_id": pid + "write",
            },
        )
    )
    command = "ffmpeg -v error -y -f lavfi -i color=c=0x243b2e:s=640x360:r=30:d=4 -vf \"drawtext=text='VIDEO USE':fontcolor=white:fontsize=48:x=(w-tw)/2:y=(h-th)/2\" -c:v libx264 -pix_fmt yuv420p -movflags +faststart edit/final.mp4"
    r = run(command, "render")
    assert r["result"]["exit_code"] == 0, r
    review = wait(
        call(
            "review_video",
            {
                "project_id": pid,
                "video_path": "edit/final.mp4",
                "request_id": pid + "review",
            },
        )
    )
    assert (artifacts / "review.png").exists()
    output = wait(
        call(
            "export_video",
            {
                "project_id": pid,
                "video_path": "edit/final.mp4",
                "summary": "Technical test card with centered white VIDEO USE text on a green background. Four encoded frames returned through MCP; creative quality requires human review.",
                "request_id": pid + "export",
            },
        )
    )
    url = output["video_url"]
    response = c.get(url)
    assert response.status_code == 200, response.text
    (artifacts / "video.mp4").write_bytes(response.content)
    response = c.get(url, headers={"Range": "bytes=0-99"})
    assert response.status_code == 206 and len(response.content) == 100
    call("close_video_workspace", {"project_id": pid})
    note = call("read_video_file", {"project_id": pid, "path": "edit/project.md"})
    assert "four second" in note["content"][0]["text"]
    r = run(command.replace("VIDEO USE", "REVISION TWO"), "revise")
    assert r["result"]["exit_code"] == 0
    wait(
        call(
            "review_video",
            {
                "project_id": pid,
                "video_path": "edit/final.mp4",
                "request_id": pid + "review2",
            },
        )
    )
    wait(
        call(
            "export_video",
            {
                "project_id": pid,
                "video_path": "edit/final.mp4",
                "summary": "Technical revision test: changed the card to REVISION TWO after restoring saved source.",
                "request_id": pid + "export2",
            },
        )
    )
    wait(
        call(
            "narrate_video",
            {
                "project_id": pid,
                "text": "Welcome to video use. Create, edit, and refine your next idea.",
                "output": "edit/voice.mp3",
                "request_id": pid + "voice",
            },
        )
    )
    wait(
        call(
            "transcribe_video",
            {
                "project_id": pid,
                "path": "edit/voice.mp3",
                "request_id": pid + "transcript",
            },
        )
    )
    print(
        "PASS: real rendering, review image transport, exports, byte ranges, source restoration, revision, narration, and transcription",
        flush=True,
    )
    Path(".pilot-smoke-result.json").write_text(
        json.dumps({"project_id": pid, "output": output}, indent=2)
    )

print("Smoke artifacts:", artifacts)
