"""MCP request telemetry and durable progress, without host conversation capture."""

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP

from .store import ident

# Hosts may cache app documents by URI across conversations. Tie discovery to
# the actual built document so a CSS-only release cannot retain an old card.
_UI_DIGEST = hashlib.sha256(
    (Path(__file__).parent / "ui" / "card.html").read_bytes()
).hexdigest()[:16]
UI_URI = f"ui://video-use/media-{_UI_DIGEST}.html"
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
APP_TOOLS = {
    "video_project_updates",
    "video_preview_updates",
    "choose_video_style",
    "add_video_feedback",
    "save_video_widget",
    "submit_video_choice",
}


def creative_handoff(task, creative):
    """Describe current preferences without inventing approval or change evidence.

    Task results must use the latest stored creative state, including after speech
    and inspection tasks. Some older operations have no submitted revision; an
    unknown baseline is not evidence that preferences remained unchanged.
    """
    if not isinstance(creative, dict):
        return None
    current = creative.get("revision")
    if type(current) is not int or current < 1:
        return None
    payload = task.get("payload") or {}
    result = task.get("result") or {}
    submitted = next(
        (
            value
            for value in (
                task.get("submitted_creative_revision"),
                payload.get("creative_revision"),
                result.get("creative_revision"),
            )
            if type(value) is int and value > 0
        ),
        None,
    )
    changed = current != submitted if submitted is not None else None
    selected = creative.get("selected")
    # A default or a saved agent direction is a proposal, never evidence of a
    # user selecting it. Use the selection provenance recorded by the picker.
    selected_by_user = bool(
        selected and creative.get("selection_source") == "user_click"
    )
    next_action = (
        "Before the next render, use the current creative state returned here, "
        "including selected choices and latest_feedback. Distinguish the user's "
        "stated preferences from your proposed direction. A default is not approval. "
        "Continue within the saved intake and excerpt-review decisions; read get_video_project only if this "
        "state may be stale after a substantial authoring interval."
    )
    if changed:
        next_action = (
            "Creative preferences changed during or since this task. Adapt the "
            "affected work before the next render; retain compatible completed work. "
            + next_action
        )
    return {
        "current_revision": current,
        "submitted_revision": submitted,
        "preferences_changed": changed,
        "selected_by_user": selected_by_user,
        "next_action": next_action,
    }


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


def question_delivery(payload):
    """Record the question handoff, without claiming a host displayed controls.

    This descriptor asks the host to present a question. It is neither an MCP
    elicitation request nor evidence of a rendered form. Do not log question
    text, choices, answers, or the user's message.
    """
    question = payload.get("question")
    if not isinstance(question, dict):
        intake = payload.get("intake")
        question = intake.get("question") if isinstance(intake, dict) else None
    if not isinstance(question, dict) or question.get("presentation") not in (
        "native_question_tool_if_available_else_short_chat",
        "inline_choices",
    ):
        return None
    return {
        "question_id": uuid_or_none(question.get("id")),
        "status": question.get("status")
        if question.get("status") in ("answered", "awaiting_user")
        else "unknown",
        "mechanism": "mcp_app_choices"
        if question["presentation"] == "inline_choices"
        else "host_instruction",
        "server_form_requested": False,
        "host_presentation": "unobserved",
    }


class TracedMCP(FastMCP):
    async def list_tools(self):
        # Old handlers remain callable by existing chats; new discovery presents
        # the concise conversational workflow instead of a terminal toolbox.
        return [
            t
            for t in await super().list_tools()
            if t.name not in getattr(self, "legacy_tools", set())
        ]

    async def read_resource(self, uri):
        """Observe reference-card cache requests without retaining resource bodies."""
        requested = str(uri)
        if not re.fullmatch(r"ui://video-use/reference-[0-9a-f]{16}\.html", requested):
            return await super().read_resource(uri)
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        outcome = "ok"
        try:
            return await super().read_resource(uri)
        except BaseException as exc:
            outcome = type(exc).__name__
            raise
        finally:
            # Resource reads have no project identifier. Never guess a project
            # from adjacent calls, inspect the HTML, or change read semantics.
            with contextlib.suppress(Exception):
                token = get_access_token()
                if token and token.subject:
                    from .reference_playback import REFERENCE_UI_URI

                    record = {
                        "started_at": started_at,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "tool": "resources/read",
                        "surface": "card",
                        "owner": token.subject,
                        "client": hashlib.sha256(token.client_id.encode()).hexdigest()[
                            :12
                        ],
                        "project": None,
                        "task": None,
                        "requested_uri": requested,
                        "current_resource_uri": REFERENCE_UI_URI,
                        "current_resource_digest": REFERENCE_UI_URI.removeprefix(
                            "ui://video-use/reference-"
                        ).removesuffix(".html"),
                        "harness_version": os.getenv(
                            "PILOT_HARNESS_VERSION", "development"
                        ),
                        "outcome": outcome,
                        "elapsed_ms": round((time.monotonic() - started) * 1000),
                    }
                    logger = logging.getLogger(__name__)
                    with contextlib.suppress(Exception):
                        logger.info("video_use_resource %s", json.dumps(record))
                    try:
                        await asyncio.to_thread(
                            self.trace_store.put, "trace", ident(), record, ttl=2592000
                        )
                    except Exception as exc:
                        with contextlib.suppress(Exception):
                            logger.warning(
                                "video_use_trace_persist_failed %s", type(exc).__name__
                            )

    async def call_tool(self, name, arguments):
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        inputs = arguments if isinstance(arguments, dict) else {}
        outcome = "ok"
        result = None
        error = None
        try:
            result = await super().call_tool(name, arguments)
            if getattr(result, "isError", False):
                outcome = "error"
                error = safe_error(
                    " ".join(
                        block.text
                        for block in result.content
                        if getattr(block, "type", "") == "text"
                    ),
                    self.trace_config,
                )
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
                        inputs.get("project_id")
                        or payload.get("project_id")
                        or payload.get("project")
                        or payload.get("id")
                    )
                    tid = uuid_or_none(inputs.get("task_id"))
                    result_tid, result_pid = task_identity(payload)
                    task_status = payload.get("status") if result_tid else None
                    if task_status in ("failed", "cancelled"):
                        outcome = "task_" + task_status
                        error = safe_error(
                            payload.get("error") or "Backend task " + task_status,
                            self.trace_config,
                        )
                    if not tid and result_tid and (not pid or pid == result_pid):
                        tid, pid = result_tid, result_pid
                    if not pid and tid:
                        # Failed/foreign task lookups are precisely the calls we
                        # need to retain. Do not lose the trace while enriching it.
                        with contextlib.suppress(Exception):
                            pid = self.trace_store.task(token.subject, tid)["project"]
                    record = {
                        "started_at": started_at,
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
                        "harness_version": os.getenv(
                            "PILOT_HARNESS_VERSION", "development"
                        ),
                    }
                    delivery = question_delivery(payload)
                    if delivery:
                        record["question_delivery"] = delivery
                    # Known guide names help distinguish setup/reading from
                    # production without retaining prompts, code or source paths.
                    topic = inputs.get("topic", "overview")
                    if (
                        name == "video_use_guidance"
                        and isinstance(topic, str)
                        and topic
                        in {
                            "overview",
                            "scenes",
                            "motion",
                            "motion-design",
                            "manim",
                            "manim-video",
                            "workflows",
                        }
                    ):
                        record["topic"] = topic
                    if error:
                        record["error"] = error
                    if task_status:
                        record["task_status"] = task_status
                    # Log non-content metadata even if trace persistence fails;
                    # observability must not disappear together with a DB outage.
                    logger = logging.getLogger(__name__)
                    logger.info(
                        "video_use_tool %s",
                        json.dumps({k: v for k, v in record.items() if k != "error"}),
                    )
                    try:
                        await asyncio.to_thread(
                            self.trace_store.put, "trace", ident(), record, ttl=2592000
                        )
                    except Exception as exc:
                        logger.warning(
                            "video_use_trace_persist_failed %s", type(exc).__name__
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
