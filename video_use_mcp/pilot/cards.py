"""Portable MCP Apps preview card and efficient editing tools."""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Literal

from mcp.types import CallToolResult, TextContent
from mcp.server.fastmcp import Image
from pydantic import BaseModel, Field

from .interaction import UI_URI, UI_META, record_progress, wait_for_task

Stage = Literal[
    "planning", "style", "motion", "draft", "review", "complete", "needs_attention"
]


class SourceFile(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=2000000)


def register_cards(
    mcp, store, manager, config, muser, link, workspace, public_task, read, execute
):
    def snapshot(uid, pid):
        project = store.project(uid, pid)
        state = store.get("progress", pid) or {"updates": []}
        # Build fresh expiring URLs only after verifying project ownership.
        updates = []
        for entry in state.get("updates", []):
            entry = dict(entry)
            preview = entry.get("preview")
            if preview:
                entry["preview"] = dict(preview, url=link(uid, preview["object_id"]))
            updates.append(entry)
        tasks = store.sql(
            "SELECT id,operation,status,created,updated,error FROM public.vp_tasks WHERE project=$1 ORDER BY created DESC LIMIT 6",
            pid,
        )
        revisions = store.sql(
            "SELECT id,video,summary,created FROM public.vp_revisions WHERE project=$1 ORDER BY created DESC LIMIT 3",
            pid,
        )
        return {
            "id": pid,
            "title": project["title"],
            "workspace_url": workspace(pid),
            "brief": state.get("brief", ""),
            "next_action": state.get("next_action", ""),
            "stage": state.get("stage", "planning"),
            "updates": updates,
            "tasks": tasks,
            "revisions": [
                dict(
                    r,
                    video_url=link(uid, r["video"]),
                    download_url=link(uid, r["video"]) + "&download=true",
                )
                for r in revisions
            ],
        }

    def card_result(uid, pid):
        data = snapshot(uid, pid)
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "project_id": pid,
                            "workspace_url": workspace(pid),
                            "stage": data["stage"],
                            "brief": data["brief"],
                            "next_action": data["next_action"],
                            "latest_update": (data["updates"] or [None])[-1],
                            "tasks": data["tasks"],
                        }
                    ),
                )
            ],
            structuredContent=data,
        )

    async def step_result(uid, task_id, include_logs=False):
        out = public_task(store.task(uid, task_id))
        result = out.get("result") or {}
        out["result"] = {
            k: v[-2000:] if k in ("stdout", "stderr") and not include_logs else v
            for k, v in result.items()
        }
        for kind in ("video", "source"):
            if result.get(kind + "_id"):
                out[kind + "_url"] = link(uid, result[kind + "_id"])
        if out.get("video_url"):
            out["download_url"] = out["video_url"] + "&download=true"
        preview = result.get("preview") or {}
        image_object = result.get("review_object") or (
            preview.get("object_id")
            if preview.get("media_type") == "image/png"
            else None
        )
        content = []
        if out["status"] == "succeeded" and image_object:
            obj = store.sql(
                "SELECT key FROM public.vp_objects WHERE id=$1 AND owner=$2",
                image_object,
                uid,
            )[0]
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "frame.png"
                await asyncio.to_thread(store.download, obj["key"], target)
                content.append(
                    Image(data=target.read_bytes(), format="png").to_image_content()
                )
            if result.get("review_object"):
                store.put("reviewed", out["project"], result["sha256"], ttl=86400)
        content.insert(0, TextContent(type="text", text=json.dumps(out)))
        return CallToolResult(
            content=content,
            structuredContent=out | {"project_card": snapshot(uid, out["project"])},
        )

    @mcp.resource(
        UI_URI,
        mime_type="text/html;profile=mcp-app",
        meta={
            "ui": {
                "prefersBorder": True,
                "csp": {"resourceDomains": [config.public_url], "connectDomains": []},
            },
        },
    )
    def project_card() -> str:
        return (Path(__file__).parent / "ui" / "card.html").read_text()

    @mcp.tool(annotations=read, meta=UI_META)
    def show_video_project(project_id: str) -> CallToolResult:
        """Show the live in-chat project card with style frames, draft clips, progress, final videos and saved continuation context. Open once near the start; it updates itself."""
        return card_result(muser(), project_id)

    @mcp.tool(
        annotations=read, meta={"ui": {"resourceUri": UI_URI, "visibility": ["app"]}}
    )
    def video_project_updates(project_id: str) -> dict:
        """Refresh the project card without consuming a model-driven status check."""
        return snapshot(muser(), project_id)

    @mcp.tool(annotations=execute, meta=UI_META)
    async def run_video_step(
        project_id: str,
        request_id: str,
        note: str,
        stage: Stage,
        files: list[SourceFile] = [],
        command: str = "",
        preview_path: str = "",
        next_action: str = "",
        brief: str = "",
        timeout: int = 300,
        review_path: str = "",
    ) -> CallToolResult:
        """PRIMARY editing tool. Batch source files + command + visible preview in ONE call. The user sees an in-chat image/player. First stage=style with a representative PNG, then motion/draft with a short MP4. Always provide preview_path for those stages. For final rendering set review_path to the final MP4 to return encoded review frames in this same call, then export after inspection. Keep brief/next_action for continuation. Waits 25s; only poll if still running. No network. Reuse rendered scenes for audio-only changes."""
        uid = muser(True)
        if stage in ("style", "motion", "draft") and not preview_path:
            raise ValueError(
                "This visual milestone needs preview_path: a PNG/JPEG for style or a short MP4 for motion/draft. Generate it in the same command."
            )
        if (
            len(files) > 20
            or len(command) > 30000
            or len(note) > 1200
            or len(brief) > 4000
            or len(next_action) > 2000
        ):
            raise ValueError("Step exceeds file, command or context limits")
        task = manager.submit(
            uid,
            project_id,
            "step",
            {
                "files": [f.model_dump() for f in files],
                "command": command,
                "preview_path": preview_path,
                "stage": stage,
                "note": note,
                "next_action": next_action,
                "brief": brief,
                "timeout": timeout,
                "review_path": review_path,
            },
            request_id,
        )
        if task["status"] in ("queued", "running"):
            record_progress(
                store,
                project_id,
                "working",
                note,
                next_action,
                brief,
            )
        await wait_for_task(manager, task["id"], 25)
        return await step_result(uid, task["id"])

    @mcp.tool(annotations=execute, meta=UI_META)
    async def update_video_progress(
        project_id: str,
        stage: Stage,
        note: str,
        next_action: str = "",
        brief: str = "",
        preview_path: str = "",
        request_id: str = "",
    ) -> CallToolResult:
        """Save a concise progress update and next action for the live chat card and future turns. Optionally publish an existing PNG/JPEG frame or up-to-20-second draft clip (requires a unique request_id). Draft publication does not replace final review. Do not wait for approval unless the user requested it."""
        uid = muser(True)
        store.project(uid, project_id)
        if len(note) > 1200 or len(brief) > 4000 or len(next_action) > 2000:
            raise ValueError("Progress context exceeds limits")
        if preview_path:
            task = manager.submit(
                uid,
                project_id,
                "preview",
                {
                    "path": preview_path,
                    "stage": stage,
                    "note": note,
                    "next_action": next_action,
                    "brief": brief,
                    "timeout": 180,
                },
                request_id,
            )
            await wait_for_task(manager, task["id"], 25)
            return await step_result(uid, task["id"])
        if manager.lock(project_id).locked():
            raise ValueError(
                "A step is active; its saved progress will update when it finishes"
            )
        record_progress(store, project_id, stage, note, next_action, brief)
        return card_result(uid, project_id)

    return {
        "snapshot": snapshot,
        "card_result": card_result,
        "task_result": step_result,
    }
