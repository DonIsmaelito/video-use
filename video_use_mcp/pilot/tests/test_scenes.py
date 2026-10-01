"""Compact scenes use the existing private task/preview flow without shell input."""

import json
import shlex
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.scenes import scene_payload
from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]

SCENE = {"duration": 3, "marks": [{"id": "title", "kind": "text", "text": "An idea"}]}


def test_scene_description_is_data_and_audio_path_is_one_argument():
    text = "</script> $(touch /tmp/unsafe)"
    scene = SCENE | {"marks": [{"id": "title", "kind": "text", "text": text}]}
    payload = scene_payload("one", scene, "A short idea", 2, "sources/a b';x.mp3", 1)
    assert text not in payload["command"]
    assert json.loads(payload["files"][0]["content"])["marks"][0]["text"] == text
    assert shlex.split(payload["command"])[-4:] == [
        "--audio",
        "sources/a b';x.mp3",
        "--audio-start",
        "1",
    ]
    assert payload["preview_path"] == "edit/scenes/one.mp4"
    assert payload["creative_revision"] == 2


@pytest.mark.parametrize("scene_id", ["../escape", "a/b", "bad;id", "", "a" * 61])
def test_scene_id_cannot_escape_generated_paths(scene_id):
    with pytest.raises(ValueError, match="scene_id"):
        scene_payload(scene_id, SCENE, "Idea", 1, "", 0)


def test_scene_tool_returns_editable_source_and_does_not_open_empty_ui(pilot):
    _, app = pilot
    tool = next(
        t
        for t in rpc(pilot, "tools/list", {})["tools"]
        if t["name"] == "render_video_scene"
    )
    assert "ui" not in tool.get("_meta", {})
    captured = {}

    def submit(uid, project, operation, payload, request):
        captured.update(
            uid=uid,
            project=project,
            operation=operation,
            payload=payload,
            request=request,
        )
        return {
            "id": "task",
            "project": PID,
            "operation": "step",
            "status": "succeeded",
            "payload": payload,
            "result": {},
            "error": None,
            "created": "",
            "updated": "",
        }

    manager = app.state.manager
    manager.running = {}
    manager.submit = Mock(side_effect=submit)
    app.state.store.task = Mock(side_effect=lambda *args: manager.submit.return_value)

    # Return the task produced by submit without making a second submission.
    def save_task(*args):
        task = submit(*args)
        app.state.store.task.return_value = task
        return task

    app.state.store.task.side_effect = None
    manager.submit.side_effect = save_task
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "render_video_scene",
            "arguments": {
                "project_id": PID,
                "request_id": "first",
                "scene_id": "idea",
                "scene": SCENE,
                "note": "The key relationship",
                "creative_revision": 2,
            },
        },
    )
    assert not result.get("isError"), result
    assert captured["operation"] == "step" and captured["request"] == "scene:first"
    assert (
        result["structuredContent"]["scene_source"]["path"] == "edit/scenes/idea.json"
    )
    assert captured["uid"] == "tester"


def test_invalid_scene_is_rejected_before_task_submission(pilot):
    _, app = pilot
    app.state.manager.submit = Mock()
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "render_video_scene",
            "arguments": {
                "project_id": PID,
                "request_id": "first",
                "scene_id": "idea",
                "scene": SCENE | {"duration": 90},
                "note": "The key relationship",
                "creative_revision": 2,
            },
        },
    )
    assert result.get("isError")
    app.state.manager.submit.assert_not_called()
