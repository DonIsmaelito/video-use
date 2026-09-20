from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gui import server
from gui.codex_agent import AgentWorkspace
from gui.run_store import RunStore
from gui.server import LaneBroker, ModalLaneRunner, RunRequest, app


def _history_run(store: RunStore, run_id: str, completed_at: str) -> Path:
    run_dir = store.ensure_run(run_id)
    store.save_record(
        run_id,
        run_dir,
        {
            "run_id": run_id,
            "lane_id": 1,
            "status": "ready",
            "prompt": f"query for {run_id}",
            "started_at": completed_at,
            "finished_at": completed_at,
            "poster_url": f"https://media.example.test/runs/{run_id}/poster.jpg",
            "artifact_storage": "r2",
            "artifacts": [
                {
                    "id": "preview",
                    "label": "preview",
                    "url": f"https://media.example.test/runs/{run_id}/preview.mp4",
                    "primary": True,
                }
            ],
            "events": [],
        },
    )
    return run_dir


def test_history_api_is_newest_first_and_exposes_only_public_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = RunStore(tmp_path / "data")
    _history_run(store, "lane-1-older", "2026-09-01T10:00:00+00:00")
    _history_run(store, "lane-2-newer", "2026-09-01T11:00:00+00:00")
    failed_dir = store.ensure_run("lane-3-failed")
    store.save_record(
        "lane-3-failed",
        failed_dir,
        {"run_id": "lane-3-failed", "status": "failed", "events": []},
    )
    monkeypatch.setattr(server, "run_store", store)

    with TestClient(app) as client:
        response = client.get("/api/history")

    assert response.status_code == 200
    body = response.json()
    assert [item["run_id"] for item in body] == ["lane-2-newer", "lane-1-older"]
    assert set(body[0]) == {
        "run_id",
        "query",
        "completed_at",
        "poster_url",
        "artifacts",
    }
    assert set(body[0]["artifacts"][0]) == {
        "id",
        "label",
        "video_url",
        "primary",
    }
    assert "path" not in response.text
    assert "R2_" not in response.text


def test_history_delete_removes_both_remotes_before_local_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = RunStore(tmp_path / "data")
    run_dir = _history_run(store, "lane-1-delete", "2026-09-01T10:00:00+00:00")
    calls: list[str] = []

    class Storage:
        def delete_run(self, run_id: str) -> None:
            assert run_dir.is_dir()
            calls.append(f"r2:{run_id}")

    class Volume:
        def remove_file(self, run_id: str, recursive: bool = False) -> None:
            assert run_dir.is_dir()
            assert recursive is True
            calls.append(f"modal:{run_id}")

    monkeypatch.setattr(server, "run_store", store)
    monkeypatch.setattr(server, "_r2_storage_factory", lambda: Storage())
    monkeypatch.setattr(
        server.modal.Volume, "from_name", lambda *_args, **_kwargs: Volume()
    )

    with TestClient(app) as client:
        response = client.delete("/api/history/lane-1-delete")

    assert response.status_code == 200
    assert calls == ["modal:lane-1-delete", "r2:lane-1-delete"]
    assert not run_dir.exists()
    assert store.list_history() == []


def test_remote_delete_failure_keeps_history_and_local_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = RunStore(tmp_path / "data")
    run_dir = _history_run(store, "lane-2-keep", "2026-09-01T10:00:00+00:00")

    class Storage:
        def delete_run(self, _run_id: str) -> None:
            raise RuntimeError("remote unavailable")

    class Volume:
        def remove_file(self, _run_id: str, recursive: bool = False) -> None:
            assert recursive is True

    monkeypatch.setattr(server, "run_store", store)
    monkeypatch.setattr(server, "_r2_storage_factory", lambda: Storage())
    monkeypatch.setattr(
        server.modal.Volume, "from_name", lambda *_args, **_kwargs: Volume()
    )

    with TestClient(app) as client:
        response = client.delete("/api/history/lane-2-keep")

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "could not delete remote run data; history was kept"
    )
    assert run_dir.is_dir()
    assert store.history_item("lane-2-keep")["run_id"] == "lane-2-keep"


def test_ready_record_emits_history_only_after_text_evidence_is_durable(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    project = workspace_root / "project"
    edit = project / "edit"
    edit.mkdir(parents=True)
    (edit / "edl.json").write_text('{"sources": {}, "ranges": []}')
    (edit / "notes.md").write_text("editing decisions")
    for name in ("frame.png", "voice.wav", "preview.mp4", "bundle.zip"):
        (edit / name).write_bytes(b"binary")
    stderr_log = workspace_root / "stderr.log"
    stderr_log.write_text("diagnostic")
    workspace = AgentWorkspace(
        root=workspace_root,
        project=project,
        framework=workspace_root / "video-use",
        stderr_log=stderr_log,
    )
    broker = LaneBroker()
    broker.begin(1, "lane-1-durable", "full original query")
    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-durable",
            "type": "artifact",
            "message": "uploaded",
            "artifact_id": "preview",
            "artifact_label": "preview",
            "artifact_url": "https://media.example.test/runs/lane-1-durable/preview.mp4",
            "video_url": "https://media.example.test/runs/lane-1-durable/preview.mp4",
            "poster_url": "https://media.example.test/runs/lane-1-durable/poster.jpg",
            "primary": True,
        }
    )
    broker.publish(
        {
            "lane_id": 1,
            "run_id": "lane-1-durable",
            "type": "completed",
            "message": "complete",
            "progress": 1.0,
        }
    )
    store = RunStore(tmp_path / "data")
    runner = ModalLaneRunner(broker, durable_store=store)

    runner._preserve_run_record(
        1,
        "lane-1-durable",
        RunRequest(prompt="full original query"),
        workspace,
        None,
    )

    history = store.history_item("lane-1-durable")
    assert history["query"] == "full original query"
    assert history["poster_url"].endswith("poster.jpg")
    assert broker.snapshot(1)["events"][-1]["type"] == "history_added"
    run_dir = store.resolve("lane-1-durable")
    evidence_names = {
        path.name for path in (run_dir / "agent-edit").rglob("*") if path.is_file()
    }
    assert evidence_names == {"edl.json", "notes.md"}
