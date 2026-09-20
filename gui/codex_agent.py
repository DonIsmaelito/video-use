"""Fresh Codex app-server sessions for one isolated video task at a time."""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO


EventHandler = Callable[[dict[str, Any]], None]
ApprovalHandler = Callable[[str, dict[str, Any]], str]


class CodexAgentError(RuntimeError):
    """Raised when a fresh Codex turn cannot finish correctly."""


@dataclass(frozen=True)
class AgentWorkspace:
    root: Path
    project: Path
    framework: Path
    stderr_log: Path


class AgentWorkspaceFactory:
    """Clone only the current branch and requested project into one run root."""

    def __init__(self, repo_root: Path, runtime_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.runtime_root = runtime_root.resolve()

    def prepare(self, run_id: str, project_path: Path | None) -> AgentWorkspace:
        safe_run_id = re.sub(r"[^a-zA-Z0-9_-]", "", run_id)
        if not safe_run_id:
            raise ValueError("invalid run id")
        root = self.runtime_root / safe_run_id / "agent"
        if root.exists():
            raise FileExistsError(f"agent workspace already exists: {safe_run_id}")
        root.mkdir(parents=True, mode=0o700)

        framework = root / "video-use"
        project = root / "project"
        self._clone_tree(self.repo_root, framework)
        self._scrub_framework(framework)

        if project_path is None:
            (project / "edit").mkdir(parents=True)
        else:
            self._clone_tree(project_path.resolve(), project)
            self._scrub_project(project)

        (project / "AGENTS.md").write_text(
            self._agent_instructions(project, framework),
            encoding="utf-8",
        )
        return AgentWorkspace(
            root=root,
            project=project,
            framework=framework,
            stderr_log=root / "codex-app-server.stderr.log",
        )

    @staticmethod
    def _clone_tree(source: Path, destination: Path) -> None:
        destination.mkdir(parents=True)
        if sys.platform == "darwin":
            # APFS clone-on-write keeps large source videos isolated without a
            # second physical copy. -L materializes symlinks inside the clone.
            subprocess.run(
                ["cp", "-cRL", f"{source}/.", str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)

    @staticmethod
    def _remove(root: Path, relative: str) -> None:
        target = root / relative
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)

    @classmethod
    def _scrub_framework(cls, framework: Path) -> None:
        for relative in (".git", ".venv", ".env", "gui/.runtime"):
            cls._remove(framework, relative)
        cls._remove_named_secrets_and_caches(framework)

    @classmethod
    def _scrub_project(cls, project: Path) -> None:
        for relative in (
            ".git",
            ".codex",
            ".claude",
            ".env",
            "edit/runs",
        ):
            cls._remove(project, relative)
        cls._remove_named_secrets_and_caches(project)
        (project / "edit").mkdir(parents=True, exist_ok=True)

    @classmethod
    def _remove_named_secrets_and_caches(cls, root: Path) -> None:
        for current_root, directories, files in os.walk(root, topdown=True):
            current = Path(current_root)
            for directory in tuple(directories):
                if directory in {"__pycache__", ".pytest_cache", ".mypy_cache"}:
                    cls._remove(current, directory)
                    directories.remove(directory)
            for filename in files:
                if filename == ".env" or filename.startswith(".env."):
                    cls._remove(current, filename)

    @staticmethod
    def _agent_instructions(project: Path, framework: Path) -> str:
        return f"""# Isolated video task

You are a fresh video-use agent for exactly one task. No prior conversation,
attempt, benchmark, or evaluator context is part of this run.

- Treat the user's submitted task as the only creative brief.
- Never inspect Codex session stores, chat histories, credential files, other
  run directories, or the original source project.
- Work only inside `{project}`. Read the video-use framework from
  `{framework}`, but do not modify that framework copy.
- Follow `{framework / 'SKILL.md'}` completely and prioritize final video
  quality over speed or cost.
- Make reasonable creative assumptions instead of asking follow-up questions.
- Produce `{project / 'edit' / 'edl.json'}` plus every local asset it references.
- Captions may only transcribe audible human or generated speech. If the final
  audio has no spoken words, omit `subtitles` and `captions`, and do not bake a
  caption rail into the picture. Treat marketing copy as designed scene text.
- Captioned EDLs must use version 2 and declare `captions.provenance.kind` plus
  `captions.provenance.files` containing timestamped transcript/alignment JSON.
- For generated UI, typography, or illustrations, measure element bounds and
  inspect full-resolution entry, busiest, and settled frames. Any unintended
  text, button, marker, or decoration collision fails the handoff.
- Add `task_context` to the EDL with `operation` (`create` or `edit`), a short
  reusable `workflow` label such as `social ad` or `talking head`, optional
  `media_origin`, and a one-sentence `summary`. Describe the actual handoff,
  not the benchmark or evaluator.
- You may render local previews for inspection, but the final handoff is the
  complete EDL and supporting edit assets for the remote renderer.
"""


class FreshCodexSession:
    """One subprocess, one new ephemeral thread, and one user turn."""

    def __init__(self, workspace: AgentWorkspace, timeout: float = 7_200) -> None:
        self.workspace = workspace
        self.timeout = timeout
        self._request_id = 0
        self._process: subprocess.Popen[str] | None = None
        self._stderr_handle = None
        self._messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._event_handler: EventHandler | None = None
        self._approval_handler: ApprovalHandler | None = None
        self._delta_buffers: dict[str, str] = {}
        self._delta_kinds: dict[str, str] = {}
        self._delta_emitted_lengths: dict[str, int] = {}
        self._protocol_log_handle: TextIO | None = None
        self._protocol_log_lock = threading.Lock()

    def run(
        self,
        *,
        prompt: str,
        model: str,
        reasoning_effort: str,
        on_event: EventHandler,
        on_approval: ApprovalHandler,
    ) -> dict[str, Any]:
        self._event_handler = on_event
        self._approval_handler = on_approval
        self._start()
        try:
            self._request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "video_use_gui",
                        "title": "video-use gui tool",
                        "version": "0.2.0",
                    }
                },
            )
            self._send({"method": "initialized", "params": {}})
            thread_result = self._request(
                "thread/start",
                {
                    "model": model,
                    "cwd": str(self.workspace.project),
                    "approvalPolicy": "on-request",
                    "sandbox": "workspace-write",
                    "ephemeral": True,
                    "serviceName": "video-use-gui",
                    "developerInstructions": self._developer_instructions(),
                },
            )
            thread = dict(thread_result.get("thread") or {})
            thread_id = str(thread.get("id") or "")
            if not thread_id:
                raise CodexAgentError("Codex did not return a thread id")
            if thread.get("ephemeral") is not True:
                raise CodexAgentError("Codex did not create an ephemeral thread")

            self._emit(
                {
                    "kind": "decision",
                    "message": f"fresh ephemeral agent started · {model} · {reasoning_effort}",
                    "thread_id": thread_id,
                }
            )
            turn_result = self._request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [
                        {"type": "text", "text": self._task_prompt(prompt)},
                        {
                            "type": "skill",
                            "name": "video-use-isma-branch1",
                            "path": str(self.workspace.framework / "SKILL.md"),
                        },
                    ],
                    "cwd": str(self.workspace.project),
                    "approvalPolicy": "on-request",
                    "sandboxPolicy": {
                        "type": "workspaceWrite",
                        "writableRoots": [str(self.workspace.project)],
                        "networkAccess": False,
                    },
                    "model": model,
                    "effort": reasoning_effort,
                    "summary": "concise",
                },
            )
            turn_id = str((turn_result.get("turn") or {}).get("id") or "")
            if not turn_id:
                raise CodexAgentError("Codex did not return a turn id")
            return self._wait_for_turn(thread_id, turn_id)
        finally:
            self._close()

    def _start(self) -> None:
        self.workspace.stderr_log.parent.mkdir(parents=True, exist_ok=True)
        self._stderr_handle = self.workspace.stderr_log.open("w", encoding="utf-8")
        self._protocol_log_handle = self.protocol_log.open(
            "w",
            encoding="utf-8",
            buffering=1,
        )
        self._process = subprocess.Popen(
            self._app_server_command(),
            cwd=self.workspace.project,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr_handle,
            text=True,
            bufsize=1,
        )
        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            name=f"codex-events-{self.workspace.root.name}",
            daemon=True,
        )
        self._reader_thread.start()

    def _read_stdout(self) -> None:
        process = self._require_process()
        if process.stdout is None:
            self._messages.put(None)
            return
        for line in process.stdout:
            try:
                message = dict(json.loads(line))
                self._log_protocol("server", message)
                self._messages.put(message)
            except json.JSONDecodeError:
                message = {
                    "method": "error",
                    "params": {"error": f"invalid Codex event: {line.rstrip()}"},
                }
                self._log_protocol("server", {"raw": line.rstrip("\n")})
                self._messages.put(message)
        self._messages.put(None)

    @staticmethod
    def _app_server_command() -> list[str]:
        # A zero instruction-file budget prevents both global and project
        # AGENTS files from entering model context. The lane supplies its
        # clean-room policy through developerInstructions and its sole skill as
        # an explicit turn input instead.
        command = [
            "codex",
            "app-server",
            "--stdio",
            "-c",
            "project_doc_max_bytes=0",
        ]
        for feature in ("apps", "plugins", "memories", "hooks", "multi_agent"):
            command.extend(["--disable", feature])
        command.extend(["--disable", "skill_search"])
        command.extend(["--enable", "skip_host_skill_discovery"])
        mcp_names: set[str] = set()
        config_path = Path.home() / ".codex" / "config.toml"
        if config_path.is_file():
            try:
                with config_path.open("rb") as config_file:
                    config = tomllib.load(config_file)
                mcp_names.update((config.get("mcp_servers") or {}).keys())
            except (OSError, tomllib.TOMLDecodeError):
                pass
        for name in sorted(mcp_names):
            safe_name = str(name)
            if re.fullmatch(r"[a-zA-Z0-9_-]+", safe_name):
                command.extend(
                    ["-c", f"mcp_servers.{safe_name}.enabled=false"]
                )
        return command

    def _close(self) -> None:
        process = self._process
        if process is not None:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        if self._stderr_handle is not None:
            self._stderr_handle.close()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1)
        if self._protocol_log_handle is not None:
            self._protocol_log_handle.close()
            self._protocol_log_handle = None

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._send({"method": method, "id": request_id, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            message = self._read(deadline)
            if message.get("id") == request_id and "method" not in message:
                if message.get("error"):
                    detail = message["error"].get("message") or str(message["error"])
                    raise CodexAgentError(f"{method}: {detail}")
                return dict(message.get("result") or {})
            self._handle_message(message)

    def _wait_for_turn(self, thread_id: str, turn_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while True:
            message = self._read(deadline)
            method = message.get("method")
            params = dict(message.get("params") or {})
            self._handle_message(message)
            if method != "turn/completed" or params.get("threadId") != thread_id:
                continue
            turn = dict(params.get("turn") or {})
            if turn.get("id") != turn_id:
                continue
            self._flush_deltas()
            status = str(turn.get("status") or "")
            if status != "completed":
                error = dict(turn.get("error") or {})
                raise CodexAgentError(str(error.get("message") or f"turn {status}"))
            return turn

    def _read(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CodexAgentError("Codex agent timed out")
        try:
            message = self._messages.get(timeout=remaining)
        except queue.Empty as exc:
            raise CodexAgentError("Codex agent timed out") from exc
        if message is None:
            detail = ""
            if self.workspace.stderr_log.exists():
                detail = self.workspace.stderr_log.read_text(errors="replace").strip()
            raise CodexAgentError(detail[-600:] or "Codex app-server exited early")
        if not isinstance(message, dict):
            raise CodexAgentError("Codex agent timed out")
        return message

    def _send(self, message: dict[str, Any]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise CodexAgentError("Codex app-server stdin is unavailable")
        self._log_protocol("client", message)
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    @property
    def protocol_log(self) -> Path:
        return self.workspace.root / "codex-protocol.jsonl"

    def _log_protocol(self, direction: str, message: dict[str, Any]) -> None:
        handle = self._protocol_log_handle
        if handle is None:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "message": message,
        }
        with self._protocol_log_lock:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise CodexAgentError("Codex app-server is not running")
        return self._process

    def _handle_message(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        if not method:
            return
        if "id" in message:
            self._handle_server_request(message)
            return
        for event in self._notification_events(method, dict(message.get("params") or {})):
            self._emit(event)

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        params = dict(message.get("params") or {})
        request_id = message.get("id")
        if method not in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
        }:
            self._send(
                {
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"unsupported agent request: {method}",
                    },
                }
            )
            return
        if self._approval_handler is None:
            raise CodexAgentError("approval handler is unavailable")
        decision = self._approval_handler(method, params)
        self._send(
            {
                "id": request_id,
                "result": self._approval_result(method, params, decision),
            }
        )

    @staticmethod
    def _approval_result(
        method: str,
        params: dict[str, Any],
        decision: str,
    ) -> dict[str, Any]:
        if method == "item/permissions/requestApproval":
            accepted = decision in {"accept", "acceptForSession"}
            return {
                "permissions": params.get("permissions") if accepted else {},
                "scope": "session" if decision == "acceptForSession" else "turn",
            }
        return {"decision": decision}

    def _notification_events(
        self,
        method: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        item = dict(params.get("item") or {})
        item_type = str(item.get("type") or "")
        if method in {
            "item/reasoning/summaryTextDelta",
            "item/agentMessage/delta",
        }:
            key = "reasoning" if "reasoning" in method else "agent"
            stream_id = self._stream_id(key, params)
            delta = str(params.get("delta") or "")
            buffered = self._delta_buffers.get(stream_id, "") + delta
            self._delta_buffers[stream_id] = buffered
            self._delta_kinds[stream_id] = key
            emitted_length = self._delta_emitted_lengths.get(stream_id, 0)
            if "\n" not in delta and len(buffered) - emitted_length < 80:
                return []
            self._delta_emitted_lengths[stream_id] = len(buffered)
            return [
                {
                    "kind": key,
                    "message": buffered,
                    "stream_id": stream_id,
                    "streaming": True,
                }
            ]
        if method == "item/started" and item_type == "commandExecution":
            return [
                {
                    "kind": "tool",
                    "message": f"command · {str(item.get('command') or '')}",
                }
            ]
        if method == "item/started" and item_type == "fileChange":
            return [{"kind": "tool", "message": "preparing file changes"}]
        if method == "item/started" and item_type in {"webSearch", "mcpToolCall"}:
            label = item.get("query") or item.get("tool") or item_type
            return [{"kind": "tool", "message": str(label)}]
        if method == "item/completed" and item_type == "commandExecution":
            status = str(item.get("status") or "complete")
            return [{"kind": "tool", "message": f"command {status}"}]
        if method == "item/completed" and item_type == "fileChange":
            changes = item.get("changes") or []
            return [
                {
                    "kind": "tool",
                    "message": f"file changes complete · {len(changes)} path(s)",
                }
            ]
        if method == "item/completed" and item_type == "agentMessage":
            stream_id = self._stream_id("agent", {"itemId": item.get("id")})
            buffered = self._delta_buffers.pop(stream_id, "")
            self._delta_kinds.pop(stream_id, None)
            self._delta_emitted_lengths.pop(stream_id, None)
            text = str(item.get("text") or buffered)
            return [
                {
                    "kind": "agent",
                    "message": text,
                    "stream_id": stream_id,
                    "streaming": False,
                }
            ] if text else []
        if method == "turn/started":
            return [{"kind": "trace", "message": "agent turn started"}]
        if method == "turn/completed":
            return [{"kind": "trace", "message": "agent turn completed"}]
        if method == "error":
            error = params.get("error") or params
            return [{"kind": "error", "message": str(error)}]
        return []

    def _flush_deltas(self) -> None:
        for stream_id, value in tuple(self._delta_buffers.items()):
            if value.strip():
                self._emit(
                    {
                        "kind": self._delta_kinds.get(stream_id, "trace"),
                        "message": value,
                        "stream_id": stream_id,
                        "streaming": False,
                    }
                )
        self._delta_buffers.clear()
        self._delta_kinds.clear()
        self._delta_emitted_lengths.clear()

    def _emit(self, event: dict[str, Any]) -> None:
        if self._event_handler is not None and event.get("message"):
            self._event_handler(event)

    def _developer_instructions(self) -> str:
        return (
            "This is a clean-room video task. Start from only the current user input, "
            "the attached video-use-isma-branch1 skill, and files inside the isolated "
            "project. Use helpers only from the supplied framework path; never use a "
            "globally installed video-use skill. "
            "Never read, search for, list, resume, fork, or infer any prior Codex or "
            "chat session. Do not inspect credential or session-store paths. Work only "
            f"in {self.workspace.project}. Finish the requested edit and produce "
            "edit/edl.json without asking follow-up questions. Captions may only "
            "transcribe audible speech backed by timestamped transcript or alignment "
            "JSON. A music-only or silent video must omit subtitles, caption metadata, "
            "and any baked caption rail; marketing copy is scene typography instead. "
            "Captioned handoffs must use EDL version 2 and declare "
            "captions.provenance.kind and captions.provenance.files. For generated UI, "
            "typography, or illustration scenes, measure layout bounds and reject any "
            "unintended collision at full-resolution critical frames. Include concise "
            "task_context metadata describing whether this is creation or editing "
            "and the actual video workflow."
        )

    def _task_prompt(self, prompt: str) -> str:
        return (
            "Complete this video task from a fresh context:\n\n"
            f"{prompt.strip()}\n\n"
            f"Project: {self.workspace.project}\n"
            f"Video-use framework: {self.workspace.framework}\n"
            "Use only the SKILL.md and helpers inside that framework path. The final "
            "required handoff is project/edit/edl.json and all referenced assets. "
            "Use EDL version 2 for new handoffs. "
            "In the EDL, include task_context with operation, workflow, optional "
            "media_origin, and a one-sentence summary for later run inspection."
        )

    @staticmethod
    def _stream_id(kind: str, params: dict[str, Any]) -> str:
        item_id = str(params.get("itemId") or "current")
        if kind == "reasoning":
            return f"{kind}:{item_id}:{params.get('summaryIndex', 0)}"
        return f"{kind}:{item_id}"
