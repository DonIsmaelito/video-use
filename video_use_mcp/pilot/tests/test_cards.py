"""Preview protocol, owner isolation, bounded waits and safe pipeline behavior."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from video_use_mcp.pilot.interaction import UI_URI, wait_for_task
from video_use_mcp.pilot.runtime import Manager
from video_use_mcp.tests.test_service import mcp_call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]

PID = "1691c5fc-be06-4465-9ade-b8d29d9517ba"


def rpc(pilot, method, args):
    client, app = pilot
    grant = app.state.auth.issue("tester", "card-test", ["video:read", "video:write"])
    response = mcp_call(client, grant.access_token, method, args)
    assert response.status_code == 200
    return response.json()["result"]


def test_ui_discovery_and_resource_security_metadata(pilot):
    tools = rpc(pilot, "tools/list", {})["tools"]
    by_name = {t["name"]: t for t in tools}
    assert "create_video_project" not in by_name and "run_video_command" not in by_name
    assert by_name["show_video_choices"]["_meta"]["ui"]["resourceUri"] == UI_URI
    assert by_name["show_video_preview"]["_meta"]["ui"]["resourceUri"] == UI_URI
    for name in (
        "run_video_step",
        "get_video_task",
        "review_video",
        "export_video",
        "view_video_frame",
    ):
        assert "ui" not in by_name[name].get(
            "_meta", {}
        ), "background work must not create empty cards"
    assert "video_project_updates" not in by_name
    resource = rpc(pilot, "resources/read", {"uri": UI_URI})["contents"][0]
    assert resource["mimeType"] == "text/html;profile=mcp-app"
    assert resource["_meta"]["ui"]["csp"]["resourceDomains"] == [
        "http://localhost:8787",
        "https://f7e2vbn5.us-west.insforge.app",
        "https://cdn.insforge.dev",
    ]
    assert "/* APP_BUNDLE */" not in resource["text"]
    assert "video_project_updates" not in resource["text"]
    assert resource["_meta"]["ui"]["prefersBorder"] is False


def test_card_requires_project_ownership_and_returns_saved_context(pilot):
    _, app = pilot
    app.state.store.put(
        "progress",
        PID,
        {"brief": "Cream and green", "next_action": "Render motion", "updates": []},
    )
    result = rpc(
        pilot,
        "tools/call",
        {"name": "show_video_project", "arguments": {"project_id": PID}},
    )
    assert not result.get("isError"), result
    assert result["structuredContent"]["next_action"] == "Render motion"
    app.state.store.project.assert_called_with("tester", PID)
    app.state.store.project.side_effect = PermissionError("Project not found")
    denied = rpc(
        pilot,
        "tools/call",
        {"name": "video_project_updates", "arguments": {"project_id": PID}},
    )
    assert denied["isError"]


def test_tool_trace_records_metadata_without_source_or_output(pilot):
    _, app = pilot
    rpc(
        pilot,
        "tools/call",
        {"name": "get_video_project", "arguments": {"project_id": PID}},
    )
    with app.state.store.db() as db:
        rows = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    assert rows
    trace = app.state.store.get("trace", rows[-1]["key"])
    assert trace["project"] == PID and trace["tool"] == "get_video_project"
    assert trace["surface"] == "assistant"
    assert "arguments" not in trace and "result" not in trace and "token" not in trace


def test_wait_timeout_does_not_cancel_work():
    async def scenario():
        finished = asyncio.Event()

        async def work():
            await asyncio.sleep(0.03)
            finished.set()

        task = asyncio.create_task(work())
        await wait_for_task(SimpleNamespace(running={"task": task}), "task", 0.001)
        assert not task.cancelled() and not finished.is_set()
        await task
        assert finished.is_set()

    asyncio.run(scenario())


def test_disconnect_during_wait_does_not_cancel_work():
    async def scenario():
        task = asyncio.create_task(asyncio.sleep(0.03))
        waiter = asyncio.create_task(
            wait_for_task(SimpleNamespace(running={"task": task}), "task", 25)
        )
        await asyncio.sleep(0.001)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert not task.cancelled()
        await task

    asyncio.run(scenario())


def test_batch_failure_skips_preview_but_records_next_action():
    store = Mock()
    store.get.return_value = None
    manager = Manager(store, SimpleNamespace())
    manager.publish_preview = AsyncMock()
    sb = SimpleNamespace(
        write=AsyncMock(),
        run=AsyncMock(
            return_value={"exit_code": 1, "stdout": "", "stderr": "bad render"}
        ),
    )
    task = {
        "id": "task",
        "owner": "tester",
        "project": PID,
        "operation": "step",
        "payload": {
            "files": [{"path": "edit/render.py", "content": "render"}],
            "command": "python edit/render.py",
            "preview_path": "edit/style.png",
            "note": "Style frame",
            "stage": "style",
            "next_action": "Fix renderer",
        },
    }
    result = asyncio.run(manager.perform(task, sb))
    assert result["exit_code"] == 1
    manager.publish_preview.assert_not_awaited()
    sb.write.assert_awaited_once()
    state = store.put.call_args.args[2]
    assert (
        state["stage"] == "needs_attention" and state["next_action"] == "Fix renderer"
    )


def test_preview_does_not_set_final_review_gate():
    store = Mock()
    store.get.return_value = None
    manager = Manager(store, SimpleNamespace())
    manager.publish_preview = AsyncMock(
        return_value={"object_id": "preview", "media_type": "image/png"}
    )
    result = asyncio.run(
        manager.perform(
            {
                "id": "t",
                "owner": "u",
                "project": PID,
                "operation": "preview",
                "payload": {
                    "path": "edit/style.png",
                    "note": "First frame",
                    "stage": "style",
                },
            },
            object(),
        )
    )
    assert result["preview"]["object_id"] == "preview"
    assert all(c.args[0] != "reviewed" for c in store.put.call_args_list)
    assert json.dumps(store.put.call_args.args[2])


def test_late_preview_poll_returns_image_without_unlocking_final_export(pilot):
    from PIL import Image

    _, app = pilot
    store = app.state.store
    tid = "790d0a5a-eb6a-4115-99a2-1e63dbe03e9c"
    store.task = Mock(
        return_value={
            "id": tid,
            "project": PID,
            "operation": "step",
            "status": "succeeded",
            "result": {
                "preview": {"object_id": "preview-id", "media_type": "image/png"}
            },
            "error": None,
            "created": "",
            "updated": "",
        }
    )
    store.sql.side_effect = (
        lambda query, *args: [{"key": "private-preview"}]
        if "SELECT key" in query
        else []
    )
    store.download = Mock(
        side_effect=lambda key, path: Image.new("RGB", (2, 2)).save(path)
    )
    app.state.manager.running = {}
    result = rpc(
        pilot, "tools/call", {"name": "get_video_task", "arguments": {"task_id": tid}}
    )
    assert not result.get("isError"), result
    assert any(c["type"] == "image" for c in result["content"])
    assert store.get("reviewed", PID) is None


def test_completed_review_returns_image_and_unlocks_export_without_poll(pilot):
    from PIL import Image

    _, app = pilot
    store = app.state.store
    task = {
        "id": "t",
        "project": PID,
        "operation": "review",
        "status": "succeeded",
        "result": {"review_object": "review", "sha256": "exact-hash"},
        "error": None,
        "created": "",
        "updated": "",
    }
    app.state.manager.running = {}
    app.state.manager.submit = Mock(return_value=task)
    store.task = Mock(return_value=task)
    store.sql.side_effect = (
        lambda q, *a: [{"key": "review-key"}] if "SELECT key" in q else []
    )
    store.download = Mock(
        side_effect=lambda key, path: Image.new("RGB", (2, 2)).save(path)
    )
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "review_video",
            "arguments": {
                "project_id": PID,
                "video_path": "edit/final.mp4",
                "request_id": "review-1",
            },
        },
    )
    assert not result.get("isError"), result
    assert any(c["type"] == "image" for c in result["content"])
    assert "project_card" not in result["structuredContent"]
    assert store.get("reviewed", PID) == "exact-hash"


def test_errors_are_retained_privately_and_redacted(pilot):
    _, app = pilot
    app.state.mcp.trace_config.api_key = "secret-admin-key"
    app.state.store.project.side_effect = ValueError(
        "secret-admin-key https://private.test/?ticket=secret failed"
    )
    rpc(
        pilot,
        "tools/call",
        {"name": "get_video_project", "arguments": {"project_id": PID}},
    )
    with app.state.store.db() as db:
        rows = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    trace = app.state.store.get("trace", rows[-1]["key"])
    assert "failed" in trace["error"]
    assert "secret-admin-key" not in trace["error"] and "ticket=" not in trace["error"]
