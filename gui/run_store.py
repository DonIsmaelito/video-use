"""Durable evidence storage for the experimental four-lane GUI harness."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gui.task_context import task_context_from_run, task_context_label


INDEX_VERSION = 2
RUN_ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")
RUN_RECORD_FILES = {
    "trace.json",
    "run_summary.md",
    "render.log",
    "codex-protocol.jsonl",
    "codex-app-server.stderr.log",
}


def _history_artifacts(value: object) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return artifacts
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        video_url = str(raw.get("video_url") or raw.get("url") or "").strip()
        if not video_url:
            continue
        artifact_id = str(raw.get("id") or f"output-{index + 1}")
        artifacts.append(
            {
                "id": artifact_id,
                "label": str(raw.get("label") or artifact_id.replace("_", " ")),
                "video_url": video_url,
                "primary": bool(raw.get("primary", index == 0)),
            }
        )
    if artifacts and not any(item["primary"] for item in artifacts):
        artifacts[0]["primary"] = True
    return artifacts


def _public_history_entry(run_id: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    artifacts = _history_artifacts(entry.get("artifacts"))
    if (
        str(entry.get("status") or "") != "ready"
        or str(entry.get("artifact_storage") or "") != "r2"
        or not artifacts
    ):
        return None
    return {
        "run_id": run_id,
        "query": str(entry.get("query") or ""),
        "completed_at": entry.get("completed_at") or entry.get("finished_at"),
        "poster_url": entry.get("poster_url"),
        "artifacts": artifacts,
    }


class RunStoreError(RuntimeError):
    """Raised when a durable run cannot be managed safely."""


class RunPinnedError(RunStoreError):
    """Raised when deletion is attempted on a pinned experiment."""


def default_run_store_root() -> Path:
    """Return a durable, user-local data directory for GUI experiments."""

    override = os.environ.get("VIDEO_USE_GUI_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "video-use-gui"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "video-use-gui"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "video-use-gui"


def _safe_run_id(run_id: str) -> str:
    value = str(run_id)
    if RUN_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid run id")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _single_line(value: object, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _unique_messages(events: list[dict[str, Any]], *, types: set[str]) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for event in events:
        if str(event.get("type") or "") not in types:
            continue
        message = _single_line(event.get("message"))
        if message and message not in seen:
            seen.add(message)
            messages.append(message)
    return messages


def _duration_label(started_at: object, finished_at: object) -> str | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finished = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    seconds = max(0, int((finished - started).total_seconds()))
    hours, remainder = divmod(seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def build_run_summary(record: dict[str, Any], run_dir: Path) -> str:
    """Compress a full GUI trace into a small, agent-readable handoff."""

    events = [dict(event) for event in record.get("events") or []]
    status = str(record.get("status") or "unknown")
    if status == "unknown":
        if any(event.get("type") == "failed" for event in events):
            status = "failed"
        elif any(event.get("type") == "completed" for event in events):
            status = "ready"

    agent_events = [event for event in events if str(event.get("type", "")).startswith("agent")]
    modal_events = [
        event
        for event in events
        if event.get("type") in {"started", "trace", "decision", "artifact", "completed", "failed"}
    ]
    tool_events = [event for event in agent_events if event.get("agent_event") == "tool"]
    failed_tools = [
        event
        for event in tool_events
        if "failed" in str(event.get("message") or "").lower()
    ]
    decisions = _unique_messages(events, types={"agent_decision", "decision"})[-12:]
    conclusions = [
        _single_line(event.get("message"), limit=1_000)
        for event in agent_events
        if event.get("agent_event") == "agent" and not event.get("streaming")
    ][-3:]
    errors: list[str] = []
    for event in events:
        message = _single_line(event.get("message"), limit=800)
        lowered = message.lower()
        if event.get("type") == "failed" or any(
            marker in lowered
            for marker in ("traceback", " error", "failed", "invalid")
        ):
            if message and message not in errors:
                errors.append(message)
    errors = errors[-10:]

    edl_summary: dict[str, Any] | None = None
    edl_path = run_dir / "agent-edit" / "edl.json"
    if edl_path.is_file():
        try:
            edl = json.loads(edl_path.read_text(encoding="utf-8"))
            edl_summary = {
                "status": edl.get("status", "renderable"),
                "sources": len(edl.get("sources") or {}),
                "ranges": len(edl.get("ranges") or []),
                "overlays": len(edl.get("overlays") or []),
                "deliverables": len(edl.get("deliverables") or []),
                "declared_duration": edl.get("total_duration_s"),
            }
        except (OSError, json.JSONDecodeError):
            edl_summary = None

    task_context = task_context_from_run(record, run_dir)
    duration = _duration_label(record.get("started_at"), record.get("finished_at"))
    output_names = [
        str(item.get("label") or item.get("id"))
        for item in _history_artifacts(record.get("artifacts"))
    ]
    lines = [
        "# Run summary",
        "",
        "This is a compact inspection handoff for the experimental GUI harness. "
        "Use `trace.json` and `codex-protocol.jsonl` only when deeper evidence is needed.",
        "",
        "## Run",
        "",
        f"- Run: `{record.get('run_id', run_dir.name)}`",
        f"- Lane: {record.get('lane_id', 'unknown')}",
        f"- Status: {status}",
        f"- Agent: `{record.get('model', 'unknown')}` at `{record.get('reasoning_effort', 'unknown')}` effort",
        f"- Started: {record.get('started_at') or 'unknown'}",
        f"- Finished: {record.get('finished_at') or 'unknown'}",
    ]
    if duration:
        lines.append(f"- Wall time: {duration}")
    lines.extend(
        [
            "",
            "## Task context",
            "",
            f"- Type: {task_context_label(task_context)}",
        ]
    )
    if task_context.get("media_origin"):
        lines.append(f"- Media: {task_context['media_origin']}")
    if task_context.get("summary"):
        lines.append(f"- Summary: {task_context['summary']}")
    lines.extend(
        [
            "",
            "## Prompt",
            "",
            _single_line(record.get("prompt"), limit=1_500) or "No prompt recorded.",
            "",
            "## Activity",
            "",
            f"- Agent events: {len(agent_events)}",
            f"- Modal render events: {len(modal_events)}",
            f"- Tool events: {len(tool_events)}",
            f"- Failed tool events: {len(failed_tools)}",
        ]
    )
    if edl_summary:
        lines.extend(
            [
                "",
                "## Agent edit",
                "",
                f"- EDL status: {edl_summary['status']}",
                f"- Sources: {edl_summary['sources']}",
                f"- Timeline ranges: {edl_summary['ranges']}",
                f"- Overlays: {edl_summary['overlays']}",
                f"- Deliverables: {edl_summary['deliverables']}",
                f"- Declared duration: {edl_summary['declared_duration'] or 'not recorded'}",
            ]
        )
    if output_names:
        lines.extend(["", "## Outputs", ""])
        lines.extend(f"- `{name}`" for name in output_names)
    if decisions:
        lines.extend(["", "## Decisions", ""])
        lines.extend(f"- {message}" for message in decisions)
    if conclusions:
        lines.extend(["", "## Agent conclusions", ""])
        lines.extend(f"- {message}" for message in conclusions)
    if errors:
        lines.extend(["", "## Errors and warnings", ""])
        lines.extend(f"- {message}" for message in errors)
    lines.extend(
        [
            "",
            "## Deeper evidence",
            "",
            "- `trace.json`: deduplicated agent and renderer event history",
            "- `codex-protocol.jsonl`: raw Codex app-server protocol when available",
            "- `render.log`: complete Modal renderer and FFmpeg output when available",
            "- `agent-edit/`: the generated EDL and supporting edit assets",
            "",
        ]
    )
    return "\n".join(lines)


class RunStore:
    """Index and manage GUI run evidence without coupling it to the renderer."""

    def __init__(self, root: Path | None = None, *, create: bool = True) -> None:
        self.root = (root or default_run_store_root()).expanduser().resolve()
        self.runs_root = self.root / "runs"
        self.exports_root = self.root / "exports"
        self.index_path = self.root / "index.json"
        self._lock = threading.RLock()
        if create:
            self.runs_root.mkdir(parents=True, exist_ok=True)
            self.exports_root.mkdir(parents=True, exist_ok=True)

    def ensure_run(self, run_id: str, project_path: Path | None = None) -> Path:
        safe_id = _safe_run_id(run_id)
        if project_path is None:
            run_dir = self.runs_root / safe_id
        else:
            run_dir = project_path.expanduser().resolve() / "edit" / "runs" / safe_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.register(safe_id, run_dir)
        return run_dir

    def register(
        self,
        run_id: str,
        run_dir: Path,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_id = _safe_run_id(run_id)
        resolved = run_dir.expanduser().resolve()
        with self._lock:
            index = self._read_index_locked()
            previous = dict(index["runs"].get(safe_id) or {})
            entry = {
                **previous,
                "path": str(resolved),
                "updated_at": _utc_now(),
                "pinned": bool(previous.get("pinned", False)),
            }
            if "created_at" not in entry:
                entry["created_at"] = entry["updated_at"]
            if metadata:
                entry.update(metadata)
            index["runs"][safe_id] = entry
            self._write_index_locked(index)

    def resolve(self, run_id: str) -> Path:
        safe_id = _safe_run_id(run_id)
        with self._lock:
            entry = self._read_index_locked()["runs"].get(safe_id)
        candidates = []
        if entry and entry.get("path"):
            candidates.append(Path(str(entry["path"])).expanduser())
        candidates.append(self.runs_root / safe_id)
        for candidate in candidates:
            if candidate.is_dir():
                return candidate.resolve()
        raise FileNotFoundError(safe_id)

    def record_file(self, run_id: str, filename: str) -> Path:
        if filename not in RUN_RECORD_FILES:
            raise FileNotFoundError(filename)
        path = self.resolve(run_id) / filename
        if not path.is_file():
            raise FileNotFoundError(f"{run_id}/{filename}")
        return path

    def save_record(self, run_id: str, run_dir: Path, record: dict[str, Any]) -> None:
        safe_id = _safe_run_id(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        record = {
            **record,
            "task_context": task_context_from_run(record, run_dir),
        }
        trace_path = run_dir / "trace.json"
        trace_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        (run_dir / "run_summary.md").write_text(
            build_run_summary(record, run_dir),
            encoding="utf-8",
        )
        artifacts = _history_artifacts(record.get("artifacts"))
        primary = next((item for item in artifacts if item["primary"]), None)
        metadata = {
            "lane_id": record.get("lane_id"),
            "status": record.get("status"),
            "model": record.get("model"),
            "reasoning_effort": record.get("reasoning_effort"),
            "task_context": record.get("task_context"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "query": str(record.get("query") or record.get("prompt") or ""),
            "completed_at": record.get("completed_at") or record.get("finished_at"),
            "poster_url": record.get("poster_url"),
            "artifacts": artifacts,
            "primary_output": primary["video_url"] if primary else None,
            "artifact_storage": record.get("artifact_storage"),
        }
        self.register(
            safe_id,
            run_dir,
            metadata=metadata,
        )

    def record_history(
        self,
        run_id: str,
        *,
        query: str,
        completed_at: str,
        poster_url: str | None,
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Atomically add verified remote outputs to an existing run entry."""

        safe_id = _safe_run_id(run_id)
        normalized = _history_artifacts(artifacts)
        if not normalized:
            raise RunStoreError("a history run requires at least one video artifact")
        primary = next(item for item in normalized if item["primary"])
        with self._lock:
            index = self._read_index_locked()
            existing = index["runs"].get(safe_id)
            if not isinstance(existing, dict):
                raise FileNotFoundError(safe_id)
            entry = {
                **existing,
                "status": "ready",
                "query": str(query),
                "completed_at": str(completed_at),
                "finished_at": existing.get("finished_at") or str(completed_at),
                "poster_url": poster_url,
                "artifacts": normalized,
                "primary_output": primary["video_url"],
                "artifact_storage": "r2",
                "updated_at": _utc_now(),
            }
            index["runs"][safe_id] = entry
            self._write_index_locked(index)
        history = _public_history_entry(safe_id, entry)
        assert history is not None
        return history

    def history_item(self, run_id: str) -> dict[str, Any]:
        safe_id = _safe_run_id(run_id)
        with self._lock:
            entry = self._read_index_locked()["runs"].get(safe_id)
        if not isinstance(entry, dict):
            raise FileNotFoundError(safe_id)
        history = _public_history_entry(safe_id, entry)
        if history is None:
            raise FileNotFoundError(safe_id)
        return history

    def list_history(self) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for entry in self.list_runs():
            run_id = str(entry.pop("run_id"))
            public = _public_history_entry(run_id, entry)
            if public is not None:
                history.append(public)
        return sorted(
            history,
            key=lambda item: str(item.get("completed_at") or ""),
            reverse=True,
        )

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            index = self._read_index_locked()
            entries = [
                {"run_id": run_id, **dict(entry)}
                for run_id, entry in index["runs"].items()
            ]
        return sorted(
            entries,
            key=lambda item: str(item.get("started_at") or item.get("created_at") or ""),
            reverse=True,
        )

    def prune_missing(self) -> list[str]:
        """Remove stale index entries whose run directories no longer exist."""
        removed: list[str] = []
        with self._lock:
            index = self._read_index_locked()
            for run_id, entry in tuple(index["runs"].items()):
                configured = Path(str(entry.get("path") or "")).expanduser()
                fallback = self.runs_root / run_id
                if configured.is_dir() or fallback.is_dir():
                    continue
                index["runs"].pop(run_id, None)
                removed.append(run_id)
            if removed:
                self._write_index_locked(index)
        return removed

    def unregister(self, run_id: str) -> bool:
        """Remove one index entry without deleting its run directory."""
        safe_id = _safe_run_id(run_id)
        with self._lock:
            index = self._read_index_locked()
            removed = index["runs"].pop(safe_id, None) is not None
            if removed:
                self._write_index_locked(index)
        return removed

    def set_pinned(self, run_id: str, pinned: bool) -> dict[str, Any]:
        safe_id = _safe_run_id(run_id)
        self.resolve(safe_id)
        with self._lock:
            index = self._read_index_locked()
            entry = dict(index["runs"].get(safe_id) or {})
            entry["pinned"] = bool(pinned)
            entry["updated_at"] = _utc_now()
            index["runs"][safe_id] = entry
            self._write_index_locked(index)
            return {"run_id": safe_id, **entry}

    def export(self, run_id: str) -> Path:
        safe_id = _safe_run_id(run_id)
        run_dir = self.resolve(safe_id)
        destination = self.exports_root / f"{safe_id}.zip"
        temporary = self.exports_root / f".{safe_id}.{uuid.uuid4().hex}.tmp"
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                for path in sorted(run_dir.rglob("*")):
                    if not path.is_file() or path.is_symlink():
                        continue
                    compression = (
                        zipfile.ZIP_STORED
                        if path.suffix.lower() in {".mp4", ".mov", ".webm", ".zip"}
                        else zipfile.ZIP_DEFLATED
                    )
                    archive.write(
                        path,
                        arcname=str(Path(safe_id) / path.relative_to(run_dir)),
                        compress_type=compression,
                    )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def delete(self, run_id: str) -> None:
        safe_id = _safe_run_id(run_id)
        run_dir = self.resolve(safe_id)
        with self._lock:
            index = self._read_index_locked()
            entry = dict(index["runs"].get(safe_id) or {})
            if entry.get("pinned"):
                raise RunPinnedError(f"run is pinned: {safe_id}")
            if run_dir.name != safe_id or run_dir.parent.name != "runs":
                raise RunStoreError(f"refusing to delete unsafe run path: {run_dir}")
            shutil.rmtree(run_dir)
            index["runs"].pop(safe_id, None)
            self._write_index_locked(index)
            (self.exports_root / f"{safe_id}.zip").unlink(missing_ok=True)

    def latest_for_lane(self, lane_id: int) -> Path | None:
        candidates = [
            entry
            for entry in self.list_runs()
            if int(entry.get("lane_id") or 0) == lane_id
        ]
        for entry in candidates:
            try:
                return self.resolve(str(entry["run_id"]))
            except FileNotFoundError:
                continue
        return None

    def _read_index_locked(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"version": INDEX_VERSION, "runs": {}}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RunStoreError(f"run index is unreadable: {self.index_path}") from exc
        if not isinstance(data.get("runs"), dict):
            raise RunStoreError(f"run index has invalid structure: {self.index_path}")
        return {"version": INDEX_VERSION, "runs": dict(data["runs"])}

    def _write_index_locked(self, index: dict[str, Any]) -> None:
        temporary = self.root / f".index.{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_text(json.dumps(index, indent=2), encoding="utf-8")
            temporary.replace(self.index_path)
        finally:
            temporary.unlink(missing_ok=True)
