"""Localhost server for the four-lane video-use GUI."""

from __future__ import annotations

import asyncio
import io
import json
import os
import queue
import re
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

import modal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gui.codex_agent import AgentWorkspace, AgentWorkspaceFactory, FreshCodexSession
from gui.codex_catalog import CodexModelCatalog
from gui.modal_app import APP_NAME, VOLUME_NAME, function_name
from gui.r2_storage import R2Storage
from gui.run_store import RunPinnedError, RunStore
from gui.task_context import task_context_from_edl, task_context_from_run, task_context_label
from helpers.edl import EDLValidationError, validate_edl


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
load_dotenv(ROOT.parent / ".env")
TRANSIENT_ROOT = Path(tempfile.gettempdir()) / "video-use-gui"
TRANSIENT_ROOT.mkdir(parents=True, exist_ok=True)
LANE_IDS = (1, 2, 3, 4)
CONTEXT_POLICY = "fresh_ephemeral"
TEXT_EVIDENCE_SUFFIXES = {
    ".ass",
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".py",
    ".srt",
    ".toml",
    ".tsv",
    ".txt",
    ".vtt",
    ".yaml",
    ".yml",
}
EXCLUDED_EVIDENCE_DIRECTORIES = {"runs", "clips", "clips_graded"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_run_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", value)
    if not cleaned:
        raise ValueError("invalid run id")
    return cleaned


def _copy_text_evidence(source: Path, destination: Path) -> None:
    """Copy only small, inspectable text files from an agent edit handoff."""

    if not source.is_dir():
        return
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in EXCLUDED_EVIDENCE_DIRECTORIES for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix.casefold() not in TEXT_EVIDENCE_SUFFIXES:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    project_path: str | None = Field(default=None, max_length=2_000)
    model: str = Field(default="gpt-5.6-sol", min_length=1, max_length=120)
    reasoning_effort: str = Field(default="low", min_length=1, max_length=32)
    auto_approve: bool = False


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["accept", "acceptForSession", "decline", "cancel"]


class PinRunRequest(BaseModel):
    pinned: bool = True


class LaneBroker:
    """Thread-safe lane state plus fan-out queues for browser SSE clients."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[int, set[queue.Queue[dict[str, Any]]]] = {
            lane_id: set() for lane_id in LANE_IDS
        }
        self._lanes: dict[int, dict[str, Any]] = {
            lane_id: {
                "lane_id": lane_id,
                "status": "idle",
                "run_id": None,
                "prompt": "",
                "model": None,
                "reasoning_effort": None,
                "auto_approve": False,
                "context_policy": CONTEXT_POLICY,
                "task_context": None,
                "approval": None,
                "started_at": None,
                "finished_at": None,
                "progress": 0.0,
                "video_url": None,
                "poster_url": None,
                "artifacts": [],
                "trace_url": None,
                "events": [],
            }
            for lane_id in LANE_IDS
        }
        self._artifacts: dict[str, Path] = {}
        self._run_records: dict[str, Path] = {}

    def snapshot(self, lane_id: int | None = None) -> Any:
        with self._lock:
            if lane_id is not None:
                self._require_lane(lane_id)
                return self._copy_lane(self._lanes[lane_id])
            return [self._copy_lane(self._lanes[item]) for item in LANE_IDS]

    def begin(
        self,
        lane_id: int,
        run_id: str,
        prompt: str,
        model: str = "gpt-5.6-sol",
        reasoning_effort: str = "low",
        auto_approve: bool = False,
        task_context: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._require_lane(lane_id)
            if self._lanes[lane_id]["status"] in {
                "queued",
                "uploading",
                "running",
                "waiting",
            }:
                raise RuntimeError(f"lane {lane_id} is busy")
            started_at = _utc_now()
            self._lanes[lane_id].update(
                {
                    "status": "queued",
                    "run_id": run_id,
                    "prompt": prompt,
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "auto_approve": auto_approve,
                    "context_policy": CONTEXT_POLICY,
                    "task_context": dict(task_context or {}),
                    "approval": None,
                    "started_at": started_at,
                    "finished_at": None,
                    "progress": 0.0,
                    "video_url": None,
                    "poster_url": None,
                    "artifacts": [],
                    "trace_url": None,
                    "events": [],
                }
            )

    def publish(self, event: dict[str, Any]) -> None:
        lane_id = int(event["lane_id"])
        event.setdefault("timestamp", _utc_now())
        stream_id = str(event.get("stream_id") or "")
        if stream_id:
            event.setdefault("event_id", f"{event.get('run_id', '')}:{stream_id}")
        else:
            event.setdefault("event_id", uuid.uuid4().hex)
        with self._lock:
            self._require_lane(lane_id)
            lane = self._lanes[lane_id]
            event_type = event.get("type")
            if event_type == "queued":
                lane["status"] = "queued"
            elif event_type == "uploading":
                lane["status"] = "uploading"
            elif event_type in {
                "agent_started",
                "agent_trace",
                "agent_decision",
                "agent_completed",
                "started",
                "trace",
                "decision",
                "approval_resolved",
            }:
                lane["status"] = "running"
            elif event_type == "approval_required":
                lane["status"] = "waiting"
            elif event_type == "completed":
                lane["status"] = "ready"
                lane["finished_at"] = event["timestamp"]
            elif event_type == "failed":
                lane["status"] = "failed"
                lane["finished_at"] = event["timestamp"]
            if "progress" in event:
                lane["progress"] = float(event["progress"])
            if event.get("video_url"):
                lane["video_url"] = event["video_url"]
            if event.get("poster_url"):
                lane["poster_url"] = event["poster_url"]
            if event.get("artifact_url"):
                artifact_id = str(event.get("artifact_id") or "preview")
                artifact = {
                    "id": artifact_id,
                    "label": str(event.get("artifact_label") or artifact_id),
                    "url": event["artifact_url"],
                    "primary": bool(event.get("primary")),
                }
                existing_artifact = next(
                    (
                        index
                        for index, item in enumerate(lane["artifacts"])
                        if item["id"] == artifact_id
                    ),
                    None,
                )
                if existing_artifact is None:
                    lane["artifacts"].append(artifact)
                else:
                    lane["artifacts"][existing_artifact] = artifact
            if event.get("trace_url"):
                lane["trace_url"] = event["trace_url"]
            if isinstance(event.get("task_context"), dict):
                lane["task_context"] = dict(event["task_context"])
            if event_type == "approval_required":
                lane["approval"] = event.get("approval")
            elif event_type in {"approval_resolved", "completed", "failed"}:
                lane["approval"] = None
            history = lane["events"]
            event_id = event["event_id"]
            existing = next(
                (
                    index
                    for index, history_event in enumerate(history)
                    if history_event.get("event_id") == event_id
                ),
                None,
            )
            if existing is None:
                history.append(dict(event))
            else:
                history[existing] = dict(event)
            for subscriber in tuple(self._subscribers[lane_id]):
                try:
                    subscriber.put_nowait(dict(event))
                except queue.Full:
                    pass

    def subscribe(self, lane_id: int) -> queue.Queue[dict[str, Any]]:
        self._require_lane(lane_id)
        subscriber: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers[lane_id].add(subscriber)
        return subscriber

    def unsubscribe(self, lane_id: int, subscriber: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers[lane_id].discard(subscriber)

    def register_artifact(
        self,
        run_id: str,
        path: Path,
        artifact_id: str | None = None,
    ) -> str:
        safe_id = _clean_run_id(run_id)
        if artifact_id:
            safe_artifact_id = _clean_run_id(artifact_id)
            safe_id = f"{safe_id}--{safe_artifact_id}"
        with self._lock:
            self._artifacts[safe_id] = path
        return f"/api/artifacts/{safe_id}"

    def artifact(self, run_id: str) -> Path:
        safe_id = _clean_run_id(run_id)
        with self._lock:
            path = self._artifacts.get(safe_id)
        if path is None or not path.exists():
            raise FileNotFoundError(safe_id)
        return path

    def register_run_record(self, run_id: str, directory: Path) -> str:
        safe_id = _clean_run_id(run_id)
        with self._lock:
            self._run_records[safe_id] = directory
        return f"/api/runs/{safe_id}/trace.json"

    def run_record_file(self, run_id: str, filename: str) -> Path:
        safe_id = _clean_run_id(run_id)
        if filename not in {
            "trace.json",
            "run_summary.md",
            "render.log",
            "codex-protocol.jsonl",
            "codex-app-server.stderr.log",
        }:
            raise FileNotFoundError(filename)
        with self._lock:
            directory = self._run_records.get(safe_id)
        path = directory / filename if directory is not None else None
        if path is None or not path.is_file():
            raise FileNotFoundError(f"{safe_id}/{filename}")
        return path

    def restore_completed_run(
        self,
        lane_id: int,
        directory: Path,
        history: dict[str, Any] | None = None,
    ) -> None:
        trace_path = directory / "trace.json"
        output_path = directory / "output.mp4"
        if not trace_path.is_file():
            raise FileNotFoundError(directory)
        record = json.loads(trace_path.read_text(encoding="utf-8"))
        artifacts = []
        artifact_source = history.get("artifacts") if history else record.get("artifacts")
        for index, item in enumerate(artifact_source or []):
            video_url = str(item.get("video_url") or item.get("url") or "")
            if not video_url:
                continue
            artifacts.append(
                {
                    "id": str(item.get("id") or f"output-{index + 1}"),
                    "label": str(item.get("label") or item.get("id") or "output"),
                    "url": video_url,
                    "primary": bool(item.get("primary", index == 0)),
                }
            )
        if not artifacts and output_path.is_file():
            artifacts = [
                {
                    "id": "preview",
                    "label": "preview",
                    "url": f"/api/artifacts/{directory.name}",
                    "primary": True,
                }
            ]
        if not artifacts:
            raise FileNotFoundError(directory)
        task_context = task_context_from_run(record, directory)
        run_id = _clean_run_id(str(record.get("run_id") or directory.name))
        raw_events = list(record.get("events") or [])
        events: list[dict[str, Any]] = []
        for index, raw_event in enumerate(raw_events):
            event = dict(raw_event)
            event.setdefault("event_id", f"{run_id}:restored:{index}")
            events.append(event)
        directory_stat = directory.stat()
        created_at = getattr(directory_stat, "st_birthtime", directory_stat.st_mtime)
        started_at = record.get("started_at") or datetime.fromtimestamp(
            created_at,
            tz=timezone.utc,
        ).isoformat()
        finished_at = record.get("finished_at") or next(
            (
                event.get("timestamp")
                for event in reversed(events)
                if event.get("type") == "completed"
            ),
            datetime.fromtimestamp(
                trace_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        )
        with self._lock:
            self._require_lane(lane_id)
            if output_path.is_file():
                self._artifacts[run_id] = output_path
            self._run_records[run_id] = directory
            primary = next(
                (item for item in artifacts if item["primary"]),
                artifacts[0],
            )
            self._lanes[lane_id].update(
                {
                    "status": "ready",
                    "run_id": run_id,
                    "prompt": str(record.get("prompt") or ""),
                    "model": record.get("model"),
                    "reasoning_effort": record.get("reasoning_effort"),
                    "auto_approve": bool(record.get("auto_approve", False)),
                    "context_policy": str(
                        record.get("context_policy") or CONTEXT_POLICY
                    ),
                    "task_context": task_context,
                    "approval": None,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "progress": 1.0,
                    "video_url": primary["url"],
                    "poster_url": (
                        history.get("poster_url") if history else record.get("poster_url")
                    ),
                    "artifacts": artifacts,
                    "trace_url": f"/api/runs/{run_id}/trace.json",
                    "events": events,
                }
            )

    def unregister_run(self, run_id: str) -> None:
        safe_id = _clean_run_id(run_id)
        with self._lock:
            self._run_records.pop(safe_id, None)
            for artifact_id in tuple(self._artifacts):
                if artifact_id == safe_id or artifact_id.startswith(f"{safe_id}--"):
                    self._artifacts.pop(artifact_id, None)
            for lane in self._lanes.values():
                if lane.get("run_id") != safe_id:
                    continue
                lane.update(
                    {
                        "status": "idle",
                        "run_id": None,
                        "prompt": "",
                        "model": None,
                        "reasoning_effort": None,
                        "task_context": None,
                        "approval": None,
                        "started_at": None,
                        "finished_at": None,
                        "progress": 0.0,
                        "video_url": None,
                        "poster_url": None,
                        "artifacts": [],
                        "trace_url": None,
                        "events": [],
                    }
                )

    @staticmethod
    def _copy_lane(lane: dict[str, Any]) -> dict[str, Any]:
        copied = dict(lane)
        copied["events"] = [dict(event) for event in lane["events"]]
        copied["artifacts"] = [dict(item) for item in lane["artifacts"]]
        if isinstance(lane.get("task_context"), dict):
            copied["task_context"] = dict(lane["task_context"])
        return copied

    @staticmethod
    def _require_lane(lane_id: int) -> None:
        if lane_id not in LANE_IDS:
            raise KeyError(lane_id)


def _restore_latest_runs(lane_broker: LaneBroker, store: RunStore) -> None:
    for lane_id in LANE_IDS:
        for entry in store.list_runs():
            if int(entry.get("lane_id") or 0) != lane_id:
                continue
            try:
                run_id = str(entry["run_id"])
                run_dir = store.resolve(run_id)
                trace_path = run_dir / "trace.json"
                record = json.loads(trace_path.read_text(encoding="utf-8"))
                try:
                    history = store.history_item(run_id)
                except FileNotFoundError:
                    history = None
                task_context = record.get("task_context")
                if history is None and (
                    not isinstance(task_context, dict)
                    or task_context.get("source") == "edl_inferred"
                ):
                    store.save_record(run_id, run_dir, record)
                lane_broker.restore_completed_run(
                    lane_id,
                    run_dir,
                    history,
                )
                break
            except (OSError, ValueError, json.JSONDecodeError):
                continue


run_store = RunStore()
run_store.prune_missing()
broker = LaneBroker()
if os.environ.get("VIDEO_USE_GUI_RESTORE_RUNS") == "1":
    _restore_latest_runs(broker, run_store)
model_catalog = CodexModelCatalog()


@dataclass
class PendingApproval:
    lane_id: int
    run_id: str
    public: dict[str, Any]
    resolved: threading.Event = field(default_factory=threading.Event)
    decision: str | None = None


class ApprovalManager:
    """Bridge blocking app-server requests to one lane's browser controls."""

    def __init__(self, lane_broker: LaneBroker, timeout: float = 7_200) -> None:
        self.broker = lane_broker
        self.timeout = timeout
        self._lock = threading.RLock()
        self._pending: dict[str, PendingApproval] = {}
        self._auto_approved_runs: set[tuple[int, str]] = set()

    def request(
        self,
        lane_id: int,
        run_id: str,
        method: str,
        params: dict[str, Any],
    ) -> str:
        approval_id = uuid.uuid4().hex
        public = self._public_approval(approval_id, method, params)
        with self._lock:
            auto_approved = (lane_id, run_id) in self._auto_approved_runs
        if auto_approved:
            self.broker.publish(
                {
                    "lane_id": lane_id,
                    "run_id": run_id,
                    "type": "approval_resolved",
                    "message": "approval automatically allowed for this lane",
                    "approval_id": approval_id,
                    "automatic": True,
                }
            )
            return "acceptForSession"
        pending = PendingApproval(lane_id=lane_id, run_id=run_id, public=public)
        with self._lock:
            self._pending[approval_id] = pending
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "approval_required",
                "message": public["summary"],
                "approval": public,
            }
        )
        if not pending.resolved.wait(self.timeout):
            pending.decision = "cancel"
        decision = pending.decision or "cancel"
        with self._lock:
            self._pending.pop(approval_id, None)
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "approval_resolved",
                "message": f"approval {self._decision_label(decision)}",
                "approval_id": approval_id,
            }
        )
        return decision

    def resolve(self, lane_id: int, approval_id: str, decision: str) -> None:
        with self._lock:
            pending = self._pending.get(approval_id)
            if pending is None or pending.lane_id != lane_id:
                raise KeyError(approval_id)
            if pending.resolved.is_set():
                raise RuntimeError("approval already resolved")
            pending.decision = decision
            if decision == "acceptForSession":
                self._auto_approved_runs.add((lane_id, pending.run_id))
            pending.resolved.set()

    def enable_for_run(self, lane_id: int, run_id: str) -> None:
        """Auto-approve subsequent requests for exactly one lane run."""
        with self._lock:
            self._auto_approved_runs.add((lane_id, run_id))

    def clear_run(self, lane_id: int, run_id: str) -> None:
        """Discard run-scoped approval state after the agent exits."""
        with self._lock:
            self._auto_approved_runs.discard((lane_id, run_id))

    @staticmethod
    def _public_approval(
        approval_id: str,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if method == "item/commandExecution/requestApproval":
            network = dict(params.get("networkApprovalContext") or {})
            if network:
                target = network.get("host") or "network access"
                summary = f"allow network access · {target}"
                kind = "network"
            else:
                command = str(params.get("command") or "command")
                summary = f"allow command · {command[:240]}"
                kind = "command"
        elif method == "item/fileChange/requestApproval":
            summary = f"allow file changes · {params.get('grantRoot') or 'project'}"
            kind = "files"
        else:
            summary = "allow additional agent permissions"
            kind = "permissions"
        return {
            "id": approval_id,
            "kind": kind,
            "summary": summary,
            "reason": str(params.get("reason") or ""),
            "command": str(params.get("command") or "")[:800],
            "cwd": str(params.get("cwd") or "")[:800],
        }

    @staticmethod
    def _decision_label(decision: str) -> str:
        return {
            "accept": "allowed once",
            "acceptForSession": "allowed for this lane",
            "decline": "denied",
            "cancel": "cancelled",
        }.get(decision, decision)


approvals = ApprovalManager(broker)
_r2_storage_factory = R2Storage.from_env


class ModalLaneRunner:
    """Run a fresh Codex edit, then render it in the lane's Modal pool."""

    def __init__(
        self,
        lane_broker: LaneBroker,
        approval_manager: ApprovalManager | None = None,
        workspace_factory: AgentWorkspaceFactory | None = None,
        durable_store: RunStore | None = None,
    ) -> None:
        self.broker = lane_broker
        self.approvals = approval_manager or ApprovalManager(lane_broker)
        self.workspaces = workspace_factory or AgentWorkspaceFactory(
            ROOT.parent,
            TRANSIENT_ROOT,
        )
        self.run_store = durable_store or run_store

    def start(self, lane_id: int, request: RunRequest) -> str:
        run_id = f"lane-{lane_id}-{uuid.uuid4().hex[:12]}"
        initial_task_context = {
            "operation": "edit" if request.project_path else "create",
            "source": "run_metadata",
        }
        self.broker.begin(
            lane_id,
            run_id,
            request.prompt,
            request.model,
            request.reasoning_effort,
            request.auto_approve,
            initial_task_context,
        )
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "queued",
                "message": (
                    f"fresh agent queued · {request.model} · {request.reasoning_effort}"
                ),
                "progress": 0.0,
                "model": request.model,
                "reasoning_effort": request.reasoning_effort,
                "auto_approve": request.auto_approve,
                "context_policy": CONTEXT_POLICY,
                "task_context": initial_task_context,
            }
        )
        if request.auto_approve:
            self.approvals.enable_for_run(lane_id, run_id)
            self.broker.publish(
                {
                    "lane_id": lane_id,
                    "run_id": run_id,
                    "type": "approval_mode",
                    "message": "automatic approvals enabled for this run",
                    "progress": 0.0,
                    "automatic": True,
                }
            )
        thread = threading.Thread(
            target=self._run,
            args=(lane_id, run_id, request),
            name=f"video-use-{run_id}",
            daemon=True,
        )
        thread.start()
        return run_id

    def _run(self, lane_id: int, run_id: str, request: RunRequest) -> None:
        original_project: Path | None = None
        workspace: AgentWorkspace | None = None
        try:
            if request.project_path:
                original_project = Path(request.project_path).expanduser().resolve()
                if not original_project.is_dir():
                    raise ValueError(f"project directory not found: {original_project}")

            workspace = self.workspaces.prepare(run_id, original_project)
            self._run_agent(
                lane_id,
                run_id,
                request,
                workspace,
            )
            edl_path = workspace.project / "edit" / "edl.json"
            if not edl_path.is_file():
                raise RuntimeError("fresh agent did not produce edit/edl.json")
            edl = json.loads(edl_path.read_text(encoding="utf-8"))
            task_context = task_context_from_edl(
                edl,
                has_project=original_project is not None,
            )
            self.broker.publish(
                {
                    "lane_id": lane_id,
                    "run_id": run_id,
                    "type": "task_context",
                    "message": task_context_label(task_context),
                    "progress": 0.405,
                    "task_context": task_context,
                }
            )
            self._stage_project(lane_id, run_id, workspace.project)

            function = modal.Function.from_name(APP_NAME, function_name(lane_id))
            job = {
                "lane_id": lane_id,
                "run_id": run_id,
                "has_project": True,
                "model": request.model,
                "reasoning_effort": request.reasoning_effort,
                "context_policy": CONTEXT_POLICY,
            }
            for event in function.remote_gen(job):
                payload = dict(event)
                if "progress" in payload:
                    payload["progress"] = 0.46 + float(payload["progress"]) * 0.54
                payload.pop("remote_path", None)
                self.broker.publish(payload)
            self._download_render_log(run_id, original_project)
            self._preserve_run_record(
                lane_id,
                run_id,
                request,
                workspace,
                original_project,
            )
        except Exception as exc:
            self.broker.publish(
                {
                    "lane_id": lane_id,
                    "run_id": run_id,
                    "type": "failed",
                    "message": str(exc),
                    "progress": 1.0,
                }
            )
            if workspace is not None:
                try:
                    self._download_render_log(run_id, original_project)
                    self._preserve_run_record(
                        lane_id,
                        run_id,
                        request,
                        workspace,
                        original_project,
                    )
                except Exception:
                    pass
        finally:
            self.approvals.clear_run(lane_id, run_id)

    def _run_agent(
        self,
        lane_id: int,
        run_id: str,
        request: RunRequest,
        workspace: AgentWorkspace,
    ) -> None:
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "agent_started",
                "message": "creating isolated project snapshot",
                "progress": 0.01,
            }
        )
        progress = 0.04

        def publish_agent_event(event: dict[str, Any]) -> None:
            nonlocal progress
            progress = min(0.39, progress + 0.008)
            kind = str(event.get("kind") or "trace")
            event_type = "agent_decision" if kind == "decision" else "agent_trace"
            payload = {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": event_type,
                "message": str(event.get("message") or ""),
                "progress": progress,
                "agent_event": kind,
            }
            for field_name in ("stream_id", "streaming"):
                if field_name in event:
                    payload[field_name] = event[field_name]
            self.broker.publish(payload)

        session = FreshCodexSession(workspace)
        session.run(
            prompt=request.prompt,
            model=request.model,
            reasoning_effort=request.reasoning_effort,
            on_event=publish_agent_event,
            on_approval=lambda method, params: self.approvals.request(
                lane_id,
                run_id,
                method,
                params,
            ),
        )
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "agent_completed",
                "message": "fresh agent handoff complete",
                "progress": 0.40,
            }
        )

    def _stage_project(self, lane_id: int, run_id: str, project_path: Path) -> None:
        edl_path = project_path / "edit" / "edl.json"
        if not edl_path.is_file():
            raise EDLValidationError("EDL is not renderable:\n- edit/edl.json is missing")
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
        # Validate on localhost before uploading a potentially large project or
        # starting paid compute. Modal validates the rewritten copy again.
        validate_edl(
            edl,
            edl_path.parent,
            require_caption_provenance=True,
        )
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "uploading",
                "message": "uploading agent edit to Modal",
                "progress": 0.42,
            }
        )
        volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
        volume_root = f"/{run_id}/input"
        container_root = f"/runs/{run_id}/input"
        with volume.batch_upload(force=True) as upload:
            upload.put_directory(str(project_path), volume_root)

        # Preserve the user's EDL locally, but rewrite source paths in the
        # uploaded copy so absolute paths from the Mac resolve in Modal.
        if edl_path.exists():
            external_sources: list[tuple[Path, str]] = []
            for source_id, source_value in (edl.get("sources") or {}).items():
                source_path = Path(str(source_value)).expanduser()
                if not source_path.is_absolute():
                    source_path = (edl_path.parent / source_path).resolve()
                else:
                    source_path = source_path.resolve()
                if not source_path.is_file():
                    raise ValueError(f"EDL source not found: {source_path}")
                try:
                    relative_source = source_path.relative_to(project_path)
                    container_source = (
                        f"{container_root}/{relative_source.as_posix()}"
                    )
                except ValueError:
                    safe_source_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(source_id))
                    relative_external = (
                        f"_external_sources/"
                        f"{safe_source_id}-{source_path.name}"
                    )
                    container_source = f"{container_root}/{relative_external}"
                    external_sources.append(
                        (source_path, f"{volume_root}/{relative_external}")
                    )
                edl["sources"][source_id] = container_source

            with volume.batch_upload(force=True) as upload:
                for source_path, remote_source in external_sources:
                    upload.put_file(str(source_path), remote_source)
                upload.put_file(
                    io.BytesIO(json.dumps(edl, indent=2).encode("utf-8")),
                    f"{volume_root}/edit/edl.json",
                )
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "trace",
                "message": "project snapshot uploaded",
                "progress": 0.45,
            }
        )

    def _download_render_log(
        self,
        run_id: str,
        project_path: Path | None,
    ) -> Path | None:
        local_dir = self._local_run_dir(run_id, project_path)
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / "render.log"
        partial_path = local_dir / ".render.log.partial"
        volume = modal.Volume.from_name(VOLUME_NAME)
        try:
            with partial_path.open("wb") as output:
                for chunk in volume.read_file(f"{run_id}/render.log"):
                    output.write(chunk)
            partial_path.replace(local_path)
            return local_path
        except Exception:
            partial_path.unlink(missing_ok=True)
            return None

    def _preserve_run_record(
        self,
        lane_id: int,
        run_id: str,
        request: RunRequest,
        workspace: AgentWorkspace,
        project_path: Path | None,
    ) -> None:
        local_dir = self._local_run_dir(run_id, project_path)
        local_dir.mkdir(parents=True, exist_ok=True)
        agent_edit = local_dir / "agent-edit"
        _copy_text_evidence(workspace.project / "edit", agent_edit)
        edl_path = agent_edit / "edl.json"
        if project_path is not None and edl_path.is_file():
            edl = json.loads(edl_path.read_text(encoding="utf-8"))
            for source_id, source_value in (edl.get("sources") or {}).items():
                source = Path(str(source_value)).expanduser()
                if not source.is_absolute():
                    source = (workspace.project / "edit" / source).resolve()
                try:
                    relative = source.resolve().relative_to(workspace.project)
                except (OSError, ValueError):
                    continue
                edl["sources"][source_id] = str(project_path / relative)
            edl_path.write_text(json.dumps(edl, indent=2), encoding="utf-8")
        protocol_log = workspace.root / "codex-protocol.jsonl"
        if protocol_log.is_file():
            shutil.copy2(protocol_log, local_dir / protocol_log.name)
        if workspace.stderr_log.is_file():
            shutil.copy2(
                workspace.stderr_log,
                local_dir / "codex-app-server.stderr.log",
            )
        lane_state = self.broker.snapshot(lane_id)
        record = {
            "log_format_version": 5,
            "run_id": run_id,
            "lane_id": lane_id,
            "status": lane_state["status"],
            "model": request.model,
            "reasoning_effort": request.reasoning_effort,
            "auto_approve": request.auto_approve,
            "context_policy": CONTEXT_POLICY,
            "has_project": project_path is not None,
            "task_context": lane_state["task_context"],
            "prompt": request.prompt,
            "query": request.prompt,
            "started_at": lane_state["started_at"],
            "finished_at": lane_state["finished_at"],
            "completed_at": (
                lane_state["finished_at"] if lane_state["status"] == "ready" else None
            ),
            "poster_url": lane_state["poster_url"],
            "artifact_storage": "r2" if lane_state["artifacts"] else None,
            "raw_protocol_log": "codex-protocol.jsonl",
            "stderr_log": "codex-app-server.stderr.log",
            "render_log": "render.log" if (local_dir / "render.log").is_file() else None,
            "summary": "run_summary.md",
            "artifacts": lane_state["artifacts"],
            "events": lane_state["events"],
        }
        self.run_store.save_record(run_id, local_dir, record)
        trace_url = self.broker.register_run_record(run_id, local_dir)
        self.broker.publish(
            {
                "lane_id": lane_id,
                "run_id": run_id,
                "type": "trace_saved",
                "message": "durable trace and run summary saved",
                "progress": lane_state["progress"],
                "trace_url": trace_url,
            }
        )
        if lane_state["status"] == "ready":
            history = self.run_store.history_item(run_id)
            self.broker.publish(
                {
                    "lane_id": lane_id,
                    "run_id": run_id,
                    "type": "history_added",
                    "message": "run added to history",
                    "progress": lane_state["progress"],
                    "history": history,
                }
            )

    def _local_run_dir(self, run_id: str, project_path: Path | None) -> Path:
        return self.run_store.ensure_run(run_id, project_path)


runner = ModalLaneRunner(broker, approvals, durable_store=run_store)
app = FastAPI(title="video-use gui tool", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/lanes")
def lanes() -> list[dict[str, Any]]:
    return broker.snapshot()


@app.get("/api/codex/models")
def codex_models() -> dict[str, Any]:
    return model_catalog.get()


@app.get("/api/runs")
def saved_runs() -> list[dict[str, Any]]:
    return run_store.list_runs()


@app.get("/api/history")
def history() -> list[dict[str, Any]]:
    return run_store.list_history()


@app.post("/api/lanes/{lane_id}/run", status_code=202)
def run_lane(lane_id: int, request: RunRequest) -> dict[str, Any]:
    if lane_id not in LANE_IDS:
        raise HTTPException(status_code=404, detail="lane not found")
    try:
        model_catalog.validate(request.model, request.reasoning_effort)
        run_id = runner.start(lane_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "run_id": run_id,
        "status": "queued",
        "model": request.model,
        "reasoning_effort": request.reasoning_effort,
        "auto_approve": request.auto_approve,
        "context_policy": CONTEXT_POLICY,
    }


@app.post("/api/lanes/{lane_id}/approvals/{approval_id}")
def resolve_approval(
    lane_id: int,
    approval_id: str,
    request: ApprovalDecisionRequest,
) -> dict[str, str]:
    if lane_id not in LANE_IDS:
        raise HTTPException(status_code=404, detail="lane not found")
    try:
        approvals.resolve(lane_id, approval_id, request.decision)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "resolved", "decision": request.decision}


@app.get("/api/lanes/{lane_id}/events")
async def lane_events(lane_id: int) -> StreamingResponse:
    if lane_id not in LANE_IDS:
        raise HTTPException(status_code=404, detail="lane not found")
    subscriber = broker.subscribe(lane_id)

    async def stream() -> Iterator[str]:
        initial = {
            "type": "snapshot",
            "lane_id": lane_id,
            "state": broker.snapshot(lane_id),
            "timestamp": _utc_now(),
        }
        yield f"data: {json.dumps(initial)}\n\n"
        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            broker.unsubscribe(lane_id, subscriber)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/artifacts/{run_id}")
def artifact(run_id: str) -> FileResponse:
    try:
        path = broker.artifact(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.get("/api/runs/{run_id}/trace.json")
def run_trace(run_id: str) -> FileResponse:
    try:
        path = _run_record_path(run_id, "trace.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="trace not found") from exc
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.get("/api/runs/{run_id}/run_summary.md")
def run_summary(run_id: str) -> FileResponse:
    try:
        path = _run_record_path(run_id, "run_summary.md")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="run summary not found") from exc
    return FileResponse(path, media_type="text/markdown", filename=path.name)


@app.get("/api/runs/{run_id}/render.log")
def run_render_log(run_id: str) -> FileResponse:
    try:
        path = _run_record_path(run_id, "render.log")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="render log not found") from exc
    return FileResponse(path, media_type="text/plain", filename=path.name)


@app.get("/api/runs/{run_id}/codex-protocol.jsonl")
def run_protocol_log(run_id: str) -> FileResponse:
    try:
        path = _run_record_path(run_id, "codex-protocol.jsonl")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="protocol log not found") from exc
    return FileResponse(path, media_type="application/x-ndjson", filename=path.name)


@app.post("/api/runs/{run_id}/pin")
def pin_run(run_id: str, request: PinRunRequest) -> dict[str, Any]:
    try:
        return run_store.set_pinned(run_id, request.pinned)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.get("/api/runs/{run_id}/bundle.zip")
def export_run(run_id: str) -> FileResponse:
    try:
        path = run_store.export(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.delete("/api/history/{run_id}")
def delete_history(run_id: str) -> dict[str, str]:
    active = next(
        (
            lane
            for lane in broker.snapshot()
            if lane.get("run_id") == run_id
            and lane.get("status") in {"queued", "uploading", "running", "waiting"}
        ),
        None,
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="cannot delete an active run")
    entry = next(
        (item for item in run_store.list_runs() if item.get("run_id") == run_id),
        None,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="history run not found")
    if entry.get("pinned"):
        raise HTTPException(status_code=409, detail=f"run is pinned: {run_id}")
    try:
        run_store.history_item(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="history run not found") from exc

    try:
        storage = _r2_storage_factory()
        volume = modal.Volume.from_name(VOLUME_NAME)
        volume.remove_file(_clean_run_id(run_id), recursive=True)
        storage.delete_run(run_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="could not delete remote run data; history was kept",
        ) from exc

    try:
        run_store.delete(run_id)
    except RunPinnedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    broker.unregister_run(run_id)
    return {"run_id": run_id, "status": "deleted"}


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, str]:
    active = next(
        (
            lane
            for lane in broker.snapshot()
            if lane.get("run_id") == run_id
            and lane.get("status") in {"queued", "uploading", "running", "waiting"}
        ),
        None,
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="cannot delete an active run")
    try:
        run_store.history_item(run_id)
    except (FileNotFoundError, ValueError):
        pass
    else:
        raise HTTPException(
            status_code=409,
            detail="R2-backed runs must be deleted through /api/history",
        )
    try:
        run_store.delete(run_id)
    except RunPinnedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    broker.unregister_run(run_id)
    return {"run_id": run_id, "status": "deleted"}


def _run_record_path(run_id: str, filename: str) -> Path:
    try:
        return broker.run_record_file(run_id, filename)
    except FileNotFoundError:
        return run_store.record_file(run_id, filename)


def main() -> None:
    import uvicorn

    host = os.environ.get("VIDEO_USE_GUI_HOST", "127.0.0.1")
    port = int(os.environ.get("VIDEO_USE_GUI_PORT", "8765"))
    os.environ.setdefault("VIDEO_USE_GUI_RESTORE_RUNS", "1")
    uvicorn.run("gui.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
