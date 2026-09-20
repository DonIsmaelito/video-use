from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gui.codex_agent import AgentWorkspace, AgentWorkspaceFactory, FreshCodexSession
from gui.codex_catalog import CodexModelCatalog
from gui.server import (
    CONTEXT_POLICY,
    ApprovalManager,
    LaneBroker,
    ModalLaneRunner,
    RunRequest,
    app,
    broker as app_broker,
)
from gui.modal_app import _show_trace
from gui.run_store import RunStore


def test_root_and_lane_snapshot() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "video-use gui tool" in response.text
        assert "model-select" in response.text
        assert "reasoning-select" in response.text
        assert "fresh-context" in response.text
        assert "auto-approve" in response.text
        assert "lane-timer" in response.text
        assert "approval-shortcut" in response.text
        assert "trace-download" in response.text
        assert "task-context" in response.text
        assert "expand-button" in response.text
        assert "lane-detail-dialog" in response.text
        assert "history-grid" in response.text
        assert "history-dialog" in response.text
        assert response.text.count("history-player-shell") == 1

        lanes = client.get("/api/lanes").json()
        assert [lane["lane_id"] for lane in lanes] == [1, 2, 3, 4]
        assert all(lane["status"] == "idle" for lane in lanes)


def test_saved_trace_and_protocol_log_are_downloadable(tmp_path: Path) -> None:
    run_id = "lane-4-download-test"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "trace.json").write_text('{"run_id":"lane-4-download-test"}')
    (run_dir / "codex-protocol.jsonl").write_text(
        '{"direction":"server","message":{"method":"turn/started"}}\n'
    )
    (run_dir / "run_summary.md").write_text("# Run summary\n")
    (run_dir / "render.log").write_text("ffmpeg complete\n")
    app_broker.register_run_record(run_id, run_dir)

    with TestClient(app) as client:
        trace = client.get(f"/api/runs/{run_id}/trace.json")
        protocol = client.get(f"/api/runs/{run_id}/codex-protocol.jsonl")
        summary = client.get(f"/api/runs/{run_id}/run_summary.md")
        render_log = client.get(f"/api/runs/{run_id}/render.log")

    assert trace.status_code == 200
    assert trace.json()["run_id"] == run_id
    assert protocol.status_code == 200
    assert "turn/started" in protocol.text
    assert summary.status_code == 200
    assert "Run summary" in summary.text
    assert render_log.status_code == 200
    assert "ffmpeg complete" in render_log.text


def test_run_store_prunes_only_missing_directories(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "store")
    existing = tmp_path / "lane-1-existing"
    existing.mkdir()
    store.register("lane-1-existing", existing)
    store.register("lane-2-missing", tmp_path / "does-not-exist")

    assert store.prune_missing() == ["lane-2-missing"]
    assert [entry["run_id"] for entry in store.list_runs()] == ["lane-1-existing"]
    assert store.unregister("lane-1-existing") is True
    assert store.unregister("lane-1-existing") is False
    assert store.list_runs() == []


def test_run_endpoint_captures_selected_agent_config(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def validate(model: str, reasoning_effort: str) -> None:
        captured["validated"] = f"{model}:{reasoning_effort}"

    def start(_lane_id: int, request: RunRequest) -> str:
        captured["model"] = request.model
        captured["reasoning_effort"] = request.reasoning_effort
        return "lane-1-config-test"

    monkeypatch.setattr("gui.server.model_catalog.validate", validate)
    monkeypatch.setattr("gui.server.runner.start", start)

    with TestClient(app) as client:
        response = client.post(
            "/api/lanes/1/run",
            json={
                "prompt": "make the pacing tighter",
                "model": "gpt-5.6-terra",
                "reasoning_effort": "xhigh",
            },
        )

    assert response.status_code == 202
    assert response.json() == {
        "run_id": "lane-1-config-test",
        "status": "queued",
        "model": "gpt-5.6-terra",
        "reasoning_effort": "xhigh",
        "auto_approve": False,
        "context_policy": CONTEXT_POLICY,
    }
    assert captured == {
        "validated": "gpt-5.6-terra:xhigh",
        "model": "gpt-5.6-terra",
        "reasoning_effort": "xhigh",
    }


def test_broker_keeps_lane_events_isolated(tmp_path: Path) -> None:
    broker = LaneBroker()
    lane_one = broker.subscribe(1)
    lane_two = broker.subscribe(2)
    broker.begin(
        1,
        "lane-1-run",
        "first task",
        task_context={"operation": "edit"},
    )
    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-run",
            "type": "trace",
            "message": "only lane one",
            "progress": 0.5,
        }
    )

    assert lane_one.get_nowait()["message"] == "only lane one"
    assert lane_two.empty()
    assert broker.snapshot(1)["status"] == "running"
    assert broker.snapshot(2)["status"] == "idle"
    assert broker.snapshot(1)["model"] == "gpt-5.6-sol"
    assert broker.snapshot(1)["reasoning_effort"] == "low"
    assert broker.snapshot(1)["context_policy"] == CONTEXT_POLICY
    assert broker.snapshot(1)["task_context"] == {"operation": "edit"}
    assert broker.snapshot(1)["started_at"] is not None
    assert broker.snapshot(1)["finished_at"] is None

    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-run",
            "type": "completed",
            "message": "complete",
            "timestamp": "2026-08-31T22:00:00+00:00",
        }
    )
    assert broker.snapshot(1)["finished_at"] == "2026-08-31T22:00:00+00:00"

    artifact = tmp_path / "output.mp4"
    artifact.write_bytes(b"video")
    assert broker.register_artifact("lane-1-run", artifact) == "/api/artifacts/lane-1-run"
    assert broker.artifact("lane-1-run") == artifact


def test_broker_keeps_full_history_and_replaces_stream_updates() -> None:
    broker = LaneBroker()
    broker.begin(1, "lane-1-full-trace", "task")

    for index in range(125):
        broker.publish(
            {
                "lane_id": 1,
                "run_id": "lane-1-full-trace",
                "type": "agent_trace",
                "message": f"event {index}",
            }
        )

    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-full-trace",
            "type": "agent_trace",
            "message": "partial message",
            "stream_id": "agent:item-1",
            "streaming": True,
        }
    )
    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-full-trace",
            "type": "agent_trace",
            "message": "complete message",
            "stream_id": "agent:item-1",
            "streaming": False,
        }
    )

    events = broker.snapshot(1)["events"]
    assert len(events) == 126
    assert events[0]["message"] == "event 0"
    assert events[-1]["message"] == "complete message"
    assert events[-1]["streaming"] is False


def test_approval_pauses_only_its_lane_until_resolved() -> None:
    broker = LaneBroker()
    manager = ApprovalManager(broker, timeout=2)
    broker.begin(1, "lane-1-approval", "task")
    result: list[str] = []
    subscriber = broker.subscribe(1)

    thread = threading.Thread(
        target=lambda: result.append(
            manager.request(
                1,
                "lane-1-approval",
                "item/commandExecution/requestApproval",
                {"command": "ffmpeg -i source.mp4 output.mp4", "reason": "render"},
            )
        )
    )
    thread.start()
    event = subscriber.get(timeout=1)
    assert event["type"] == "approval_required"
    assert broker.snapshot(1)["status"] == "waiting"
    assert broker.snapshot(2)["status"] == "idle"

    manager.resolve(1, event["approval"]["id"], "accept")
    thread.join(timeout=1)
    assert result == ["accept"]
    assert broker.snapshot(1)["status"] == "running"
    assert broker.snapshot(1)["approval"] is None


def test_allow_lane_auto_approves_future_commands_in_the_same_run() -> None:
    broker = LaneBroker()
    manager = ApprovalManager(broker, timeout=2)
    run_id = "lane-2-auto-approval"
    broker.begin(2, run_id, "task")
    subscriber = broker.subscribe(2)
    result: list[str] = []
    thread = threading.Thread(
        target=lambda: result.append(
            manager.request(
                2,
                run_id,
                "item/commandExecution/requestApproval",
                {"command": "first command"},
            )
        )
    )
    thread.start()
    request = subscriber.get(timeout=1)
    manager.resolve(2, request["approval"]["id"], "acceptForSession")
    thread.join(timeout=1)

    second = manager.request(
        2,
        run_id,
        "item/commandExecution/requestApproval",
        {"command": "second command"},
    )

    assert result == ["acceptForSession"]
    assert second == "acceptForSession"
    events = broker.snapshot(2)["events"]
    assert len([event for event in events if event["type"] == "approval_required"]) == 1
    assert events[-1]["automatic"] is True


def test_run_can_auto_approve_before_the_first_request() -> None:
    broker = LaneBroker()
    manager = ApprovalManager(broker, timeout=2)
    run_id = "lane-3-preapproved"
    broker.begin(3, run_id, "task", auto_approve=True)
    manager.enable_for_run(3, run_id)

    decision = manager.request(
        3,
        run_id,
        "item/commandExecution/requestApproval",
        {"command": "python helpers/web_source.py search"},
    )

    assert decision == "acceptForSession"
    events = broker.snapshot(3)["events"]
    assert not [event for event in events if event["type"] == "approval_required"]
    assert events[-1]["type"] == "approval_resolved"
    assert events[-1]["automatic"] is True

    manager.clear_run(3, run_id)
    assert (3, run_id) not in manager._auto_approved_runs


def test_project_staging_rewrites_edl_without_touching_local_copy(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    edit_dir = project / "edit"
    source = project / "source.mp4"
    edit_dir.mkdir(parents=True)
    source.write_bytes(b"video")
    edl_path = edit_dir / "edl.json"
    original = {
        "version": 1,
        "sources": {"source": str(source)},
        "ranges": [{"source": "source", "start": 0, "end": 1}],
    }
    edl_path.write_text(__import__("json").dumps(original))

    uploads: list[tuple[str, object, str]] = []

    class Batch:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def put_directory(self, local: str, remote: str) -> None:
            uploads.append(("directory", local, remote))

        def put_file(self, local, remote: str) -> None:
            value = local.getvalue() if hasattr(local, "getvalue") else local
            uploads.append(("file", value, remote))

    class Volume:
        def batch_upload(self, force: bool = False):
            assert force is True
            return Batch()

    monkeypatch.setattr(
        "gui.server.modal.Volume.from_name",
        lambda *_args, **_kwargs: Volume(),
    )

    runner = ModalLaneRunner(LaneBroker())
    runner._stage_project(1, "lane-1-test", project)

    rewritten_bytes = next(
        value
        for kind, value, remote in uploads
        if kind == "file" and remote.endswith("/edit/edl.json")
    )
    rewritten = __import__("json").loads(rewritten_bytes)
    assert rewritten["sources"]["source"] == "/runs/lane-1-test/input/source.mp4"
    assert __import__("json").loads(edl_path.read_text()) == original


def test_run_record_preserves_agent_edl_and_trace(tmp_path: Path) -> None:
    original = tmp_path / "original"
    source = original / "source.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")
    workspace_root = tmp_path / "workspace"
    workspace_project = workspace_root / "project"
    workspace_source = workspace_project / "source.mp4"
    workspace_edit = workspace_project / "edit"
    workspace_edit.mkdir(parents=True)
    workspace_source.write_bytes(b"video")
    (workspace_edit / "edl.json").write_text(
        __import__("json").dumps(
            {
                "version": 1,
                "sources": {"source": "../source.mp4"},
                "ranges": [{"source": "source", "start": 0, "end": 1}],
            }
        )
    )
    workspace = AgentWorkspace(
        root=workspace_root,
        project=workspace_project,
        framework=workspace_root / "video-use",
        stderr_log=workspace_root / "stderr.log",
    )
    (workspace_root / "codex-protocol.jsonl").write_text(
        '{"direction":"server","message":{"method":"turn/started"}}\n'
    )
    workspace.stderr_log.write_text("diagnostic")
    broker = LaneBroker()
    broker.begin(1, "lane-1-record", "task")
    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-record",
            "type": "agent_trace",
            "message": "inspected source",
        }
    )
    runner = ModalLaneRunner(
        broker,
        durable_store=RunStore(tmp_path / "run-store"),
    )

    runner._preserve_run_record(
        1,
        "lane-1-record",
        RunRequest(prompt="task"),
        workspace,
        original,
    )

    run_dir = original / "edit" / "runs" / "lane-1-record"
    saved_edl = __import__("json").loads(
        (run_dir / "agent-edit" / "edl.json").read_text()
    )
    saved_trace = __import__("json").loads((run_dir / "trace.json").read_text())
    assert saved_edl["sources"]["source"] == str(source)
    assert saved_trace["context_policy"] == CONTEXT_POLICY
    assert saved_trace["events"][-1]["message"] == "inspected source"
    assert saved_trace["log_format_version"] == 5
    assert saved_trace["task_context"] == {
        "operation": "edit",
        "workflow": "general video",
        "source": "edl_inferred",
    }
    assert saved_trace["auto_approve"] is False
    assert saved_trace["raw_protocol_log"] == "codex-protocol.jsonl"
    assert (run_dir / "codex-protocol.jsonl").is_file()
    assert (run_dir / "codex-app-server.stderr.log").read_text() == "diagnostic"
    summary = (run_dir / "run_summary.md").read_text()
    assert "Timeline ranges: 1" in summary
    assert "task" in summary
    assert broker.snapshot(1)["trace_url"] == (
        "/api/runs/lane-1-record/trace.json"
    )


def test_modal_trace_filter_keeps_only_actionable_lines() -> None:
    assert _show_trace("extracting 3 segment(s)")
    assert _show_trace("  [00] source 0.10-1.90")
    assert _show_trace("reframing → vertical.mp4 (1080x1920@30/1, track)")
    assert _show_trace("loudness normalization → social-ready")
    assert _show_trace("Traceback (most recent call last):")
    assert not _show_trace("configuration: --enable-libx264 --enable-libass")
    assert not _show_trace("Stream #0:0 -> #0:0 (copy)")


def test_modal_render_log_downloads_into_the_durable_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class Volume:
        @staticmethod
        def read_file(remote_path: str):
            assert remote_path == "lane-2-render-log/render.log"
            yield b"complete ffmpeg output\n"

    monkeypatch.setattr(
        "gui.server.modal.Volume.from_name",
        lambda *_args, **_kwargs: Volume(),
    )
    runner = ModalLaneRunner(
        LaneBroker(),
        durable_store=RunStore(tmp_path / "run-store"),
    )

    render_log = runner._download_render_log("lane-2-render-log", None)

    assert render_log == (
        tmp_path / "run-store" / "runs" / "lane-2-render-log" / "render.log"
    )
    assert render_log.read_text() == "complete ffmpeg output\n"


def test_named_artifacts_are_kept_separately(tmp_path: Path) -> None:
    broker = LaneBroker()
    vertical = tmp_path / "vertical.mp4"
    square = tmp_path / "square.mp4"
    vertical.write_bytes(b"vertical")
    square.write_bytes(b"square")

    vertical_url = broker.register_artifact(
        "lane-4-run", vertical, artifact_id="social_9x16"
    )
    square_url = broker.register_artifact(
        "lane-4-run", square, artifact_id="social_1x1"
    )

    assert vertical_url == "/api/artifacts/lane-4-run--social_9x16"
    assert square_url == "/api/artifacts/lane-4-run--social_1x1"
    assert broker.artifact("lane-4-run--social_9x16") == vertical
    assert broker.artifact("lane-4-run--social_1x1") == square


def test_blocked_edl_never_starts_project_upload(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    edit_dir = project / "edit"
    edit_dir.mkdir(parents=True)
    (edit_dir / "edl.json").write_text(
        __import__("json").dumps(
            {
                "status": "blocked_missing_source_media",
                "sources": {},
                "ranges": [],
                "handoff": {
                    "render_ready": False,
                    "blocking_reason": "stage a source video",
                },
            }
        )
    )
    volume = Mock()
    monkeypatch.setattr(
        "gui.server.modal.Volume.from_name",
        lambda *_args, **_kwargs: volume,
    )

    with pytest.raises(ValueError, match="stage a source video"):
        ModalLaneRunner(LaneBroker())._stage_project(4, "lane-4-blocked", project)

    volume.batch_upload.assert_not_called()


def test_model_catalog_preserves_model_specific_reasoning_options() -> None:
    models = CodexModelCatalog._normalize_models(
        [
            {
                "id": "model-a",
                "model": "model-a",
                "displayName": "Model A",
                "defaultReasoningEffort": "high",
                "supportedReasoningEfforts": [
                    {"reasoningEffort": "low", "description": "fast"},
                    {"reasoningEffort": "high", "description": "deep"},
                ],
                "isDefault": True,
            }
        ]
    )

    assert models[0]["id"] == "model-a"
    assert models[0]["default_reasoning_effort"] == "high"
    assert [item["id"] for item in models[0]["reasoning_efforts"]] == [
        "low",
        "high",
    ]


def test_run_request_captures_model_and_reasoning() -> None:
    request = RunRequest(
        prompt="make the pacing tighter",
        model="gpt-5.6-terra",
        reasoning_effort="xhigh",
        auto_approve=True,
    )

    assert request.model == "gpt-5.6-terra"
    assert request.reasoning_effort == "xhigh"
    assert request.auto_approve is True

    try:
        RunRequest(prompt="task", model="", reasoning_effort="high")
    except ValidationError:
        pass
    else:
        raise AssertionError("empty models must be rejected")


def test_workspace_is_a_clean_copy_without_prior_runs(tmp_path: Path) -> None:
    framework = tmp_path / "framework"
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    (framework / "helpers").mkdir(parents=True)
    (framework / "SKILL.md").write_text("current branch skill")
    (framework / ".env").write_text("secret")
    (project / "edit" / "runs" / "old-run").mkdir(parents=True)
    (project / "edit" / "runs" / "old-run" / "notes.txt").write_text("prior")
    (project / ".codex" / "sessions").mkdir(parents=True)
    (project / ".codex" / "sessions" / "history.jsonl").write_text("history")
    (project / "source.txt").write_text("source")

    workspace = AgentWorkspaceFactory(framework, runtime).prepare(
        "lane-1-clean",
        project,
    )

    assert (workspace.framework / "SKILL.md").read_text() == "current branch skill"
    assert not (workspace.framework / ".env").exists()
    assert (workspace.project / "source.txt").read_text() == "source"
    assert not (workspace.project / "edit" / "runs").exists()
    assert not (workspace.project / ".codex").exists()
    instructions = (workspace.project / "AGENTS.md").read_text()
    assert "No prior conversation" in instructions
    assert "edit/edl.json" in instructions


def test_fresh_session_uses_new_ephemeral_thread_and_selected_model(tmp_path: Path) -> None:
    workspace = AgentWorkspace(
        root=tmp_path,
        project=tmp_path / "project",
        framework=tmp_path / "video-use",
        stderr_log=tmp_path / "stderr.log",
    )
    workspace.project.mkdir()
    workspace.framework.mkdir()
    (workspace.framework / "SKILL.md").write_text("skill")
    session = FreshCodexSession(workspace)
    calls: list[tuple[str, dict]] = []

    session._start = lambda: None
    session._close = lambda: None
    session._send = lambda _message: None

    def request(method: str, params: dict) -> dict:
        calls.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "fresh-thread", "ephemeral": True}}
        if method == "turn/start":
            return {"turn": {"id": "fresh-turn"}}
        return {}

    session._request = request
    session._wait_for_turn = lambda _thread_id, _turn_id: {"status": "completed"}

    result = session.run(
        prompt="make a clean cut",
        model="gpt-5.6-terra",
        reasoning_effort="high",
        on_event=lambda _event: None,
        on_approval=lambda _method, _params: "accept",
    )

    thread_params = next(params for method, params in calls if method == "thread/start")
    turn_params = next(params for method, params in calls if method == "turn/start")
    assert result["status"] == "completed"
    assert thread_params["ephemeral"] is True
    assert thread_params["model"] == "gpt-5.6-terra"
    assert turn_params["effort"] == "high"
    assert all(method not in {"thread/resume", "thread/fork"} for method, _ in calls)


def test_agent_stream_updates_are_full_and_share_one_event_id(tmp_path: Path) -> None:
    workspace = AgentWorkspace(
        root=tmp_path,
        project=tmp_path,
        framework=tmp_path,
        stderr_log=tmp_path / "stderr.log",
    )
    session = FreshCodexSession(workspace)
    item_id = "agent-message-1"
    first = session._notification_events(
        "item/agentMessage/delta",
        {"itemId": item_id, "delta": "a" * 90},
    )
    second = session._notification_events(
        "item/agentMessage/delta",
        {"itemId": item_id, "delta": "b" * 600},
    )
    completed = session._notification_events(
        "item/completed",
        {
            "item": {
                "id": item_id,
                "type": "agentMessage",
                "text": "a" * 90 + "b" * 600,
            }
        },
    )

    assert first[0]["stream_id"] == f"agent:{item_id}"
    assert first[0]["streaming"] is True
    assert second[0]["message"] == "a" * 90 + "b" * 600
    assert completed[0]["stream_id"] == first[0]["stream_id"]
    assert completed[0]["streaming"] is False
    assert len(completed[0]["message"]) == 690
    assert "…" not in completed[0]["message"]


def test_protocol_log_keeps_unabridged_json_messages(tmp_path: Path) -> None:
    workspace = AgentWorkspace(
        root=tmp_path,
        project=tmp_path,
        framework=tmp_path,
        stderr_log=tmp_path / "stderr.log",
    )
    session = FreshCodexSession(workspace)
    long_text = "full trace " * 200
    session._protocol_log_handle = session.protocol_log.open("w", encoding="utf-8")
    session._log_protocol(
        "server",
        {
            "method": "item/agentMessage/delta",
            "params": {"itemId": "item-1", "delta": long_text},
        },
    )
    session._protocol_log_handle.close()
    session._protocol_log_handle = None

    saved = __import__("json").loads(session.protocol_log.read_text())
    assert saved["direction"] == "server"
    assert saved["message"]["params"]["delta"] == long_text


def test_fresh_session_disables_instruction_files_and_mcp_servers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_root = tmp_path / "profile"
    config_dir = config_root / ".codex"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[mcp_servers.example]\ncommand = "example"\n'
    )
    monkeypatch.setattr("gui.codex_agent.Path.home", lambda: config_root)

    command = FreshCodexSession._app_server_command()

    assert "project_doc_max_bytes=0" in command
    assert "mcp_servers.example.enabled=false" in command
    assert "apps" in command
    assert "plugins" in command
    assert "memories" in command
    assert "skill_search" in command
    assert "skip_host_skill_discovery" in command


def test_permission_approval_returns_only_requested_permissions(tmp_path: Path) -> None:
    workspace = AgentWorkspace(
        root=tmp_path,
        project=tmp_path,
        framework=tmp_path,
        stderr_log=tmp_path / "stderr.log",
    )
    session = FreshCodexSession(workspace)
    requested = {"network": {"enabled": True}, "fileSystem": None}

    accepted = session._approval_result(
        "item/permissions/requestApproval",
        {"permissions": requested},
        "acceptForSession",
    )
    denied = session._approval_result(
        "item/permissions/requestApproval",
        {"permissions": requested},
        "decline",
    )

    assert accepted == {"permissions": requested, "scope": "session"}
    assert denied == {"permissions": {}, "scope": "turn"}
