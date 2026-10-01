"""Acknowledged defects survive retries and rerenders until explicitly resolved."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from video_use_mcp.pilot.runtime import Manager
from video_use_mcp.pilot.tests.test_cards import PID, rpc
from video_use_mcp.pilot.tests.test_preview_delivery import TID, task_result
from video_use_mcp.store import Store


pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]

DEFECT = {
    "kind": "meaning",
    "description": "Arrow labels claim electric field but arrows depict force on electrons.",
    "severity": "minor",
    "resolved": False,
}


def export_fixture(tmp_path):
    store = Store(tmp_path)
    store.sql = Mock(return_value=[])
    store.put("reviewed", PID, "encoded-sha")
    manager = Manager(store, SimpleNamespace())
    manager.save_object = AsyncMock(return_value={"id": "video-object"})
    manager.checkpoint = AsyncMock(return_value={"id": "source-object"})
    sandbox = SimpleNamespace(
        safe_path=AsyncMock(return_value="/workspace/edit/final.mp4"),
        run=AsyncMock(
            return_value={"exit_code": 0, "stdout": "encoded-sha  final.mp4"}
        ),
        inspect_video=AsyncMock(return_value={"duration": 30}),
        download=AsyncMock(),
    )
    task = {
        "id": TID,
        "owner": "tester",
        "project": PID,
        "operation": "export",
        "payload": {
            "video_path": "edit/final.mp4",
            "summary": "Inspected the actual encoded frames.",
        },
    }
    return store, manager, sandbox, task


def assert_unpublished(manager, sandbox):
    sandbox.inspect_video.assert_not_awaited()
    sandbox.download.assert_not_awaited()
    manager.save_object.assert_not_awaited()
    manager.checkpoint.assert_not_awaited()


def test_export_records_even_minor_acknowledged_defects_before_any_upload(tmp_path):
    store, manager, sandbox, task = export_fixture(tmp_path)
    task["payload"]["findings"] = [DEFECT]
    with pytest.raises(ValueError, match="Export blocked"):
        asyncio.run(manager.perform(task, sandbox))
    assert store.get("review_findings", PID) == [DEFECT]
    assert_unpublished(manager, sandbox)


@pytest.mark.parametrize("supplied", [None, []])
def test_changed_encode_and_omitted_findings_do_not_clear_reported_defect(
    tmp_path, supplied
):
    store, manager, sandbox, task = export_fixture(tmp_path)
    store.put("review_findings", PID, [DEFECT])
    store.put("reviewed", PID, "newly-encoded-sha")
    sandbox.run.return_value["stdout"] = "newly-encoded-sha  final.mp4"
    if supplied is not None:
        task["payload"]["findings"] = supplied
    with pytest.raises(ValueError, match="Export blocked"):
        asyncio.run(manager.perform(task, sandbox))
    assert store.get("review_findings", PID) == [DEFECT]
    assert_unpublished(manager, sandbox)


def test_explicit_resolution_exports_with_optional_style_preferences(tmp_path):
    store, manager, sandbox, task = export_fixture(tmp_path)
    store.put("review_findings", PID, [DEFECT])
    style = {
        "kind": "style",
        "description": "An alternative palette could be softer.",
        "resolved": False,
    }
    task["payload"]["findings"] = [DEFECT | {"resolved": True}, style]
    result = asyncio.run(manager.perform(task, sandbox))
    assert result["video_id"] == "video-object"
    assert result["source_id"] == "source-object"
    assert store.get("review_findings", PID) == [DEFECT | {"resolved": True}, style]
    sandbox.inspect_video.assert_awaited_once()
    manager.save_object.assert_awaited_once()
    assert any(
        "INSERT INTO public.vp_revisions" in call.args[0]
        for call in store.sql.call_args_list
    )


def test_claimed_resolution_does_not_replace_exact_encoded_video_inspection(tmp_path):
    store, manager, sandbox, task = export_fixture(tmp_path)
    store.put("reviewed", PID, "different-encoded-sha")
    task["payload"]["findings"] = [DEFECT | {"resolved": True}]
    with pytest.raises(ValueError, match="inspect the current encoded output"):
        asyncio.run(manager.perform(task, sandbox))
    assert_unpublished(manager, sandbox)


def prepare_export_tool(pilot):
    _, app = pilot
    task = dict(
        id=TID,
        project=PID,
        operation="export",
        status="succeeded",
        result={},
        payload={},
        error=None,
        created="",
        updated="",
    )
    app.state.manager.submit = Mock(return_value=task)
    app.state.manager.running = {}
    app.state.store.task = Mock(return_value=task)
    return app, {
        "project_id": PID,
        "video_path": "edit/final.mp4",
        "summary": "Inspected the encoded result.",
        "request_id": "export-with-review",
    }


def test_export_tool_submits_normalized_structured_findings(pilot):
    app, arguments = prepare_export_tool(pilot)
    arguments["findings"] = [{"kind": "style", "description": "  Alternate color  "}]
    response = rpc(
        pilot, "tools/call", {"name": "export_video", "arguments": arguments}
    )
    assert not response.get("isError"), response
    assert app.state.manager.submit.call_args.args[3]["findings"] == [
        {"kind": "style", "description": "Alternate color", "resolved": False}
    ]


def test_export_tool_rejects_ambiguous_resolution_before_submission(pilot):
    app, arguments = prepare_export_tool(pilot)
    arguments["findings"] = [DEFECT | {"resolved": "false"}]
    response = rpc(
        pilot, "tools/call", {"name": "export_video", "arguments": arguments}
    )
    assert response.get("isError"), response
    app.state.manager.submit.assert_not_called()


def test_export_tool_remains_callable_without_findings(pilot):
    app, arguments = prepare_export_tool(pilot)
    response = rpc(
        pilot, "tools/call", {"name": "export_video", "arguments": arguments}
    )
    assert not response.get("isError"), response
    app.state.manager.submit.assert_called_once()


def test_project_and_task_context_expose_findings_for_later_resolution(pilot):
    _, app = pilot
    app.state.store.put("review_findings", PID, [DEFECT])
    project = rpc(
        pilot,
        "tools/call",
        {"name": "get_video_project", "arguments": {"project_id": PID}},
    )
    assert not project.get("isError"), project
    project_data = project.get("structuredContent") or json.loads(
        project["content"][0]["text"]
    )
    assert project_data["review_findings"] == [DEFECT]
    _, task = task_result(pilot)
    assert task["review_findings"] == [DEFECT]
