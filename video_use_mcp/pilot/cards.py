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
            "revisions": [dict(r, video_url=link(uid, r["video"])) for r in revisions],
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

    async def step_result(uid, task_id):
        out = public_task(store.task(uid, task_id))
        content = [TextContent(type="text", text=json.dumps(out))]
        preview = (out.get("result") or {}).get("preview")
        if (
            out["status"] == "succeeded"
            and preview
            and preview["media_type"] == "image/png"
        ):
            obj = store.sql(
                "SELECT key FROM public.vp_objects WHERE id=$1 AND owner=$2",
                preview["object_id"],
                uid,
            )[0]
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "frame.png"
                await asyncio.to_thread(store.download, obj["key"], target)
                content.append(
                    Image(data=target.read_bytes(), format="png").to_image_content()
                )
        return CallToolResult(content=content, structuredContent=out)

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

    @mcp.tool(annotations=execute)
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
    ) -> CallToolResult:
        """Preferred editing tool: save several UTF-8 files, optionally execute a command, publish a PNG/JPEG or short video preview, and checkpoint in one call. Waits up to 25 seconds; unfinished tasks continue. Use stage=style then motion/draft for gradual previews. Supply brief and next_action for continuation. Commands run without network. Nonzero exit codes skip preview publication."""
        uid = muser(True)
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
            },
            request_id,
        )
        if task["status"] in ("queued", "running"):
            record_progress(
                store,
                project_id,
                "working",
                "Working on the next update.",
                next_action,
                brief,
            )
        await wait_for_task(manager, task["id"], 25)
        return await step_result(uid, task["id"])

    @mcp.tool(annotations=execute)
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
        state = record_progress(store, project_id, stage, note, next_action, brief)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(state))],
            structuredContent=state,
        )
