"""MCP request telemetry and durable progress, without host conversation capture."""

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP

from .store import ident

UI_URI = "ui://video-use/media-v7.html"
UI_META = {"ui": {"resourceUri": UI_URI}}

TASK_OPERATIONS = {
    "step",
    "run",
    "command",
    "write",
    "patch",
    "preview",
    "narrate",
    "transcribe",
    "review",
    "export",
}
TASK_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
APP_TOOLS = {"video_project_updates", "video_preview_updates", "choose_video_style"}


def task_identity(payload):
    """Recognize a task result without confusing project IDs with task IDs."""
    if (
        not isinstance(payload, dict)
        or payload.get("operation") not in TASK_OPERATIONS
        or payload.get("status") not in TASK_STATUSES
    ):
        return None, None
    task = uuid_or_none(payload.get("id"))
    project = uuid_or_none(payload.get("project"))
    return (task, project) if task and project else (None, None)


def safe_error(exc, config):
    message = str(exc)
    for field in ("api_key", "speech_key", "encryption_key", "invite_code"):
        secret = getattr(config, field, "")
        if isinstance(secret, str) and secret:
            message = message.replace(secret, "[redacted]")
    message = re.sub(r"https?://\S+", "[url]", message)
    message = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", message)
    return message[:600]


def uuid_or_none(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        return None


class TracedMCP(FastMCP):
    async def list_tools(self):
        # Old handlers remain callable by existing chats; new discovery presents
        # the concise conversational workflow instead of a terminal toolbox.
        return [
            t
            for t in await super().list_tools()
            if t.name not in getattr(self, "legacy_tools", set())
        ]

    async def call_tool(self, name, arguments):
        started = time.monotonic()
        outcome = "ok"
        result = None
        error = None
        try:
            result = await super().call_tool(name, arguments)
            if getattr(result, "isError", False):
                outcome = "error"
            return result
        except BaseException as exc:
            outcome = type(exc).__name__
            error = safe_error(exc, self.trace_config)
            raise
        finally:
            # Instrumentation must never change tool success or replay work.
            with contextlib.suppress(Exception):
                token = get_access_token()
                if token and token.subject:
                    payload = (
                        result.structuredContent
                        if hasattr(result, "structuredContent")
                        else result
                    )
                    if isinstance(payload, tuple):
                        payload = payload[1]
                    if isinstance(payload, list):
                        for block in payload:
                            if getattr(block, "type", "") == "text":
                                with contextlib.suppress(ValueError):
                                    payload = json.loads(block.text)
                                    break
                    payload = payload if isinstance(payload, dict) else {}
                    pid = uuid_or_none(
                        arguments.get("project_id")
                        or payload.get("project_id")
                        or payload.get("project")
                        or payload.get("id")
                    )
                    tid = uuid_or_none(arguments.get("task_id"))
                    result_tid, result_pid = task_identity(payload)
                    if not tid and result_tid and (not pid or pid == result_pid):
                        tid, pid = result_tid, result_pid
                    if not pid and tid:
                        pid = self.trace_store.task(token.subject, tid)["project"]
                    record = {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "tool": name,
                        "owner": token.subject,
                        "project": pid,
                        "task": tid,
                        "outcome": outcome,
                        "elapsed_ms": round((time.monotonic() - started) * 1000),
                        "input_bytes": len(json.dumps(arguments).encode()),
                        "output_bytes": len(str(result).encode()),
                        "client": hashlib.sha256(token.client_id.encode()).hexdigest()[
                            :12
                        ],
                        "surface": "card" if name in APP_TOOLS else "assistant",
                    }
                    if error:
                        record["error"] = error
                    await asyncio.to_thread(
                        self.trace_store.put, "trace", ident(), record, ttl=2592000
                    )
                    logging.getLogger(__name__).info(
                        "video_use_tool %s",
                        json.dumps({k: v for k, v in record.items() if k != "error"}),
                    )


def record_progress(store, pid, stage, note, next_action="", brief="", preview=None):
    state = store.get("progress", pid) or {"updates": []}
    update = {
        "id": ident(),
        "at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "note": note[:1200],
    }
    if preview:
        update["preview"] = preview
    # Keep the most recent actual draft independently of the bounded event log.
    # A long render can emit many nonvisual updates before another draft exists.
    authored = [
        entry
        for entry in state.get("updates", []) + [update]
        if entry.get("preview")
        and entry.get("stage") != "review"
        and entry.get("note") != "Preview frame"
    ]
    if authored:
        state["latest_preview"] = authored[-1]
    state["updates"] = (state.get("updates", []) + [update])[-20:]
    state["stage"] = stage
    state["next_action"] = next_action[:2000]
    if brief:
        state["brief"] = brief[:4000]
    state["updated_at"] = update["at"]
    store.put("progress", pid, state)
    return state


async def wait_for_task(manager, task_id, seconds):
    """Wait without cancelling the durable task when a request times out/disconnects."""
    future = manager.running.get(task_id)
    if future is not None and seconds > 0:
        try:
            await asyncio.wait_for(asyncio.shield(future), min(seconds, 25))
        except asyncio.TimeoutError:
            pass
