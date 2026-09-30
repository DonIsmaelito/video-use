"""MCP request telemetry and durable progress, without host conversation capture."""

import asyncio
import contextlib
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP

from .store import ident

UI_URI = "ui://video-use/project-v1.html"
UI_META = {"ui": {"resourceUri": UI_URI}}


def uuid_or_none(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        return None


class TracedMCP(FastMCP):
    async def call_tool(self, name, arguments):
        started = time.monotonic()
        outcome = "ok"
        result = None
        try:
            result = await super().call_tool(name, arguments)
            if getattr(result, "isError", False):
                outcome = "error"
            return result
        except BaseException as exc:
            outcome = type(exc).__name__
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
                    payload = payload if isinstance(payload, dict) else {}
                    pid = uuid_or_none(
                        arguments.get("project_id")
                        or payload.get("project")
                        or payload.get("id")
                    )
                    tid = uuid_or_none(arguments.get("task_id"))
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
                        "surface": "card"
                        if name == "video_project_updates"
                        else "assistant",
                    }
                    await asyncio.to_thread(
                        self.trace_store.put, "trace", ident(), record, ttl=2592000
                    )
                    logging.getLogger(__name__).info(
                        "video_use_tool %s", json.dumps(record)
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
