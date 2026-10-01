"""Regressions from the solar run: completed media must reach the host model."""

import json
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.interaction import task_identity
from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]
TID = "790d0a5a-eb6a-4115-99a2-1e63dbe03e9c"


def task_result(pilot, *, status="succeeded", result=None, payload=None):
    _, app = pilot
    task = dict(
        id=TID,
        project=PID,
        operation="step",
        status=status,
        result=result,
        payload=payload or {},
        error=None,
        created="",
        updated="",
    )
    app.state.store.task = Mock(return_value=task)
    app.state.manager.running = {}
    response = rpc(
        pilot, "tools/call", dict(name="get_video_task", arguments={"task_id": TID})
    )
    assert not response.get("isError"), response
    text = json.loads(response["content"][0]["text"])
    assert text == response["structuredContent"]
    assert "project_card" not in text
    return response, text


def test_completed_video_has_actual_link_and_display_action_in_text(pilot):
    _, text = task_result(
        pilot,
        result={
            "preview": {
                "object_id": "actual-clip",
                "media_type": "video/mp4",
                "draft": True,
            }
        },
    )
    assert text["media"]["object_id"] == "actual-clip"
    assert "/files/actual-clip?ticket=" in text["media"]["url"]
    assert text["media"]["download_url"].endswith("&download=true")
    assert "already open in THIS conversation" in text["next_action"]
    assert "instead of opening duplicate players" in text["next_action"]
    assert text["display_action"] == {
        "name": "show_video_preview",
        "arguments": {"project_id": PID},
    }
    assert "next_tool" not in text


def test_exported_video_has_display_action_without_legacy_workspace(pilot):
    _, text = task_result(pilot, result={"video_id": "final-video"})
    assert text["media"]["caption"] == "Finished video"
    assert text["display_action"]["name"] == "show_video_preview"
    assert "next_tool" not in text


def test_running_task_has_wait_action_and_no_fake_media(pilot):
    _, text = task_result(pilot, status="running")
    assert "media" not in text
    assert "display_action" not in text
    assert text["next_tool"] == {
        "name": "get_video_task",
        "arguments": {"task_id": TID},
    }


def test_failed_command_does_not_offer_stale_preview(pilot):
    _, text = task_result(
        pilot,
        result={
            "exit_code": 1,
            "stderr": "encode failed",
            "preview": {"object_id": "stale", "media_type": "video/mp4"},
        },
    )
    assert "media" not in text and "next_tool" not in text
    assert "correct only the failed work" in text["next_action"]


def test_missing_publication_preserves_authored_work_and_requests_small_followup(pilot):
    _, app = pilot
    task = dict(
        id=TID,
        project=PID,
        operation="step",
        status="succeeded",
        result={"saved": ["edit/scene.py"], "exit_code": 0},
        error=None,
        created="",
        updated="",
    )

    def submit(_uid, _pid, _operation, payload, _request_id):
        task["payload"] = payload
        return task

    app.state.manager.submit = Mock(side_effect=submit)
    app.state.manager.running = {}
    app.state.store.task = Mock(return_value=task)
    response = rpc(
        pilot,
        "tools/call",
        {
            "name": "run_video_step",
            "arguments": {
                "project_id": PID,
                "request_id": "authored-scene",
                "note": "Developing the solar mechanism",
                "stage": "draft",
                "files": [{"path": "edit/scene.py", "content": "# source\n" * 2000}],
                "command": "python edit/scene.py",
            },
        },
    )
    assert not response.get("isError"), response
    app.state.manager.submit.assert_called_once()
    assert task["payload"]["stage"] == "planning"
    assert task["payload"]["preview_pending"] is True
    assert task["payload"]["command"] == "python edit/scene.py"
    text = json.loads(response["content"][0]["text"])
    assert text == response["structuredContent"]
    assert text["preview_pending"] is True and "media" not in text
    assert "Do not resend" in text["next_action"]


def test_legacy_inspection_sheet_does_not_replace_playable_draft(pilot):
    _, app = pilot
    app.state.store.put(
        "progress",
        PID,
        {
            "updates": [
                {
                    "at": "2026-10-01T03:56:47Z",
                    "stage": "draft",
                    "note": "Solar motion draft",
                    "preview": {"object_id": "draft", "media_type": "video/mp4"},
                },
                {
                    "at": "2026-10-01T03:58:37Z",
                    "stage": "style",
                    "note": "Preview frame",
                    "preview": {"object_id": "qa-sheet", "media_type": "image/png"},
                },
            ]
        },
    )
    response = rpc(
        pilot,
        "tools/call",
        {"name": "show_video_preview", "arguments": {"project_id": PID}},
    )
    assert response["structuredContent"]["media"]["object_id"] == "draft"


def test_new_scene_render_trace_links_returned_task(pilot):
    _, app = pilot
    task = dict(
        id=TID,
        project=PID,
        operation="step",
        status="succeeded",
        result={"saved": []},
        error=None,
        created="",
        updated="",
    )
    app.state.manager.submit = Mock(return_value=task)
    app.state.manager.running = {}
    app.state.store.task = Mock(return_value=task)
    response = rpc(
        pilot,
        "tools/call",
        {
            "name": "run_video_step",
            "arguments": {
                "project_id": PID,
                "request_id": "source-save",
                "note": "Save project notes",
                "stage": "planning",
            },
        },
    )
    assert not response.get("isError"), response
    with app.state.store.db() as db:
        keys = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    traces = [app.state.store.get("trace", row["key"]) for row in keys]
    trace = next(t for t in traces if t["tool"] == "run_video_step")
    assert trace["task"] == TID and trace["project"] == PID
    assert "arguments" not in trace and "result" not in trace


@pytest.mark.parametrize(
    "payload",
    [
        {"id": PID, "title": "A project"},
        {"id": TID, "operation": "step", "status": "succeeded"},
        {"id": TID, "project": PID, "operation": "invented", "status": "succeeded"},
        {
            "id": "not-a-task-id",
            "project": PID,
            "operation": "step",
            "status": "succeeded",
        },
    ],
)
def test_project_and_invalid_result_shapes_do_not_become_tasks(payload):
    assert task_identity(payload) == (None, None)


def test_schema_describes_publication_before_large_payload_submission(pilot):
    tools = rpc(pilot, "tools/list", {})["tools"]
    properties = next(t for t in tools if t["name"] == "run_video_step")["inputSchema"][
        "properties"
    ]
    assert "actual output" in properties["stage"]["description"]
    assert "publish an existing file" in properties["preview_path"]["description"]
