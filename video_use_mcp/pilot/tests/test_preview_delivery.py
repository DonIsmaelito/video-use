"""Regressions from the solar run: completed media must reach the host model."""

import json
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.interaction import task_identity
from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]
TID = "790d0a5a-eb6a-4115-99a2-1e63dbe03e9c"


def task_result(
    pilot, *, status="succeeded", result=None, payload=None, operation="step"
):
    _, app = pilot
    task = dict(
        id=TID,
        project=PID,
        operation=operation,
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


def test_completed_video_has_actual_link_and_exact_object_delivery_in_text(pilot):
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
    assert "this exact clip once" in text["next_action"]
    assert "later final export needs a separate player" in text["next_action"]
    assert "display_action" not in text
    assert text["preview_delivery"]["reuse_existing_player"] is False
    assert "in this conversation" in text["preview_delivery"]["open_only_when"]
    assert text["preview_delivery"]["open"] == {
        "name": "show_video_preview",
        "arguments": {"project_id": PID, "object_id": "actual-clip"},
    }
    assert "next_tool" not in text


def test_exported_video_opens_new_player_after_chat_without_legacy_workspace(pilot):
    _, text = task_result(
        pilot,
        operation="export",
        result={
            "video_id": "final-video",
            "final_duration_check": {"video_seconds": 30.13},
        },
    )
    assert text["media"]["caption"] == "Finished video"
    assert "display_action" not in text
    assert text["preview_delivery"]["reuse_existing_player"] is False
    assert text["preview_delivery"]["stage"] == "final"
    assert text["media"]["final"] is True
    assert text["media"]["duration"] == 30.13
    assert text["preview_delivery"]["open"] == {
        "name": "show_video_preview",
        "arguments": {"project_id": PID, "object_id": "final-video"},
    }
    assert "one short chat sentence" in text["next_action"]
    assert "NEW player" in text["next_action"]
    assert "sample player unchanged" in text["next_action"]
    assert "next_tool" not in text


def test_running_task_has_wait_action_and_no_fake_media(pilot):
    _, text = task_result(pilot, status="running")
    assert "media" not in text
    assert "display_action" not in text
    assert "preview_delivery" not in text
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


def test_sample_and_final_are_separately_addressed_after_final_export(pilot):
    _, app = pilot
    app.state.store.put(
        "progress",
        PID,
        {
            "stage": "complete",
            "updates": [
                {
                    "at": "2026-10-04T01:00:00Z",
                    "stage": "draft",
                    "note": "Six second sample",
                    "preview": {
                        "object_id": "sample",
                        "media_type": "video/mp4",
                        "duration": 6,
                    },
                }
            ],
        },
    )
    revision = {
        "id": "revision",
        "video": "full-video",
        "metadata": {"final_duration_check": {"video_seconds": 30.13}},
        "created": "2026-10-04T01:10:00Z",
    }

    def sql(query, *args):
        if "vp_revisions" in query:
            return [revision] if len(args) == 1 or args[1] == "full-video" else []
        return []

    app.state.store.sql = Mock(side_effect=sql)

    def show(object_id):
        response = rpc(
            pilot,
            "tools/call",
            {
                "name": "show_video_preview",
                "arguments": {"project_id": PID, "object_id": object_id},
            },
        )
        assert not response.get("isError"), response
        return response["structuredContent"]

    sample = show("sample")
    final = show("full-video")
    assert sample["media"]["object_id"] == "sample"
    assert sample["media"]["duration"] == 6
    assert sample["media"]["final"] is False
    assert final["media"]["object_id"] == "full-video"
    assert final["media"]["final"] is True
    assert final["media"]["duration"] == 30.13
    assert sample["follow_project"] is final["follow_project"] is False
    assert "/files/full-video?ticket=" in final["media"]["download_url"]

    # A later editing session cannot turn a specifically requested saved export
    # back into a draft or redirect either player's identity.
    app.state.store.put("progress", PID, {"stage": "draft", "updates": []})
    assert show("full-video")["media"]["final"] is True


def test_exact_preview_rejects_other_project_object_instead_of_returning_latest(pilot):
    _, app = pilot
    app.state.store.put(
        "progress",
        PID,
        {
            "updates": [
                {
                    "at": "2026-10-04T01:00:00Z",
                    "stage": "draft",
                    "note": "Local draft",
                    "preview": {"object_id": "local", "media_type": "video/mp4"},
                }
            ],
        },
    )
    response = rpc(
        pilot,
        "tools/call",
        {
            "name": "show_video_preview",
            "arguments": {
                "project_id": PID,
                "object_id": "foreign",
            },
        },
    )
    assert response["isError"]
    assert "Video not found in this project" in response["content"][0]["text"]
    app.state.store.sql.assert_any_call(
        "SELECT id,created FROM public.vp_objects WHERE id=$1 AND owner=$2 AND project=$3 AND kind='video'",
        "foreign",
        "tester",
        PID,
    )


def test_historical_sample_can_be_reopened_without_selecting_newer_clip(pilot):
    _, app = pilot

    def sql(query, *args):
        if "vp_objects" in query:
            return [{"id": "old-sample", "created": "2026-10-04T01:00:00Z"}]
        return []

    app.state.store.sql = Mock(side_effect=sql)
    response = rpc(
        pilot,
        "tools/call",
        {
            "name": "show_video_preview",
            "arguments": {
                "project_id": PID,
                "object_id": "old-sample",
            },
        },
    )
    assert not response.get("isError"), response
    assert response["structuredContent"]["media"]["object_id"] == "old-sample"
    assert response["structuredContent"]["media"]["final"] is False
    assert response["structuredContent"]["follow_project"] is False


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
