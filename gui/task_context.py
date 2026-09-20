"""Small, durable task labels for GUI run inspection."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_OPERATION_ALIASES = {
    "create": "create",
    "creation": "create",
    "create from scratch": "create",
    "generated": "create",
    "edit": "edit",
    "editing": "edit",
    "edit existing": "edit",
}


def _short_text(value: object, *, limit: int) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return None
    return text[:limit].rstrip()


def _normalized_operation(value: object, *, has_project: bool) -> str:
    text = re.sub(r"[_-]+", " ", str(value or "")).strip().casefold()
    return _OPERATION_ALIASES.get(text, "edit" if has_project else "create")


def _normalized_workflow(value: object) -> str | None:
    text = _short_text(value, limit=48)
    if not text:
        return None
    return re.sub(r"[_-]+", " ", text).casefold()


def _edl_evidence(edl: dict[str, Any]) -> str:
    """Return descriptive EDL fields without using the submitted prompt."""

    evidence: list[object] = []
    for key in ("intent", "title", "description"):
        evidence.append(edl.get(key))
    for item in edl.get("ranges") or []:
        if isinstance(item, dict):
            evidence.extend(item.get(key) for key in ("beat", "reason", "label"))
    raw_deliverables = edl.get("deliverables") or []
    if isinstance(raw_deliverables, dict):
        evidence.extend(raw_deliverables.keys())
        deliverables = raw_deliverables.values()
    else:
        deliverables = raw_deliverables
    for item in deliverables:
        if isinstance(item, dict):
            evidence.extend(item.get(key) for key in ("id", "name", "file"))
    return " ".join(str(value) for value in evidence if value).casefold()


def _infer_workflow(edl: dict[str, Any]) -> str:
    evidence = _edl_evidence(edl)
    if "social" in evidence and any(word in evidence for word in (" ad", "cta", "call to action")):
        return "social ad"
    ranked_beats = [
        str(item.get("beat") or "").casefold()
        for item in edl.get("ranges") or []
        if isinstance(item, dict)
    ]
    if sum("goal " in beat for beat in ranked_beats) >= 3:
        return "montage"
    candidates = (
        ("talking head", ("talking head", "talking-head")),
        ("animated explainer", ("animated explainer", "concept explainer", "explainer")),
        ("product demo", ("product demo", "demo")),
        ("tutorial", ("tutorial", "walkthrough", "how to")),
        ("documentary", ("documentary",)),
        ("montage", ("montage",)),
        ("interview", ("interview",)),
        ("social video", ("social", "vertical")),
    )
    for label, markers in candidates:
        if any(marker in evidence for marker in markers):
            return label
    if edl.get("animations") or edl.get("illustrations"):
        return "animated video"
    return "general video"


def task_context_from_edl(
    edl: dict[str, Any],
    *,
    has_project: bool,
) -> dict[str, Any]:
    """Normalize agent-authored context, with an EDL-evidence fallback."""

    raw = edl.get("task_context")
    authored = raw if isinstance(raw, dict) else {}
    workflow = _normalized_workflow(authored.get("workflow") or authored.get("type"))
    context = {
        "operation": _normalized_operation(
            authored.get("operation"),
            has_project=has_project,
        ),
        "workflow": workflow or _infer_workflow(edl),
        "source": "agent_authored" if workflow else "edl_inferred",
    }
    media_origin = _normalized_workflow(authored.get("media_origin"))
    summary = _short_text(authored.get("summary"), limit=180)
    if media_origin:
        context["media_origin"] = media_origin
    if summary:
        context["summary"] = summary
    return context


def task_context_from_run(
    record: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    """Read persisted context or reconstruct it from the saved agent handoff."""

    persisted = record.get("task_context")
    if (
        isinstance(persisted, dict)
        and persisted.get("operation")
        and persisted.get("source") != "edl_inferred"
    ):
        return dict(persisted)
    edl_path = run_dir / "agent-edit" / "edl.json"
    if edl_path.is_file():
        try:
            edl = json.loads(edl_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            edl = None
        if isinstance(edl, dict):
            return task_context_from_edl(
                edl,
                has_project=bool(record.get("has_project")),
            )
    return {
        "operation": "edit" if record.get("has_project") else "create",
        "workflow": "general video",
        "source": "run_metadata",
    }


def task_context_label(context: dict[str, Any] | None) -> str:
    """Format a task context for the lane header and compact summaries."""

    if not context:
        return ""
    operation = _normalized_workflow(context.get("operation"))
    workflow = _normalized_workflow(context.get("workflow"))
    return " · ".join(value for value in (operation, workflow) if value)
