"""Compact scenes use the existing private task/preview flow without shell input."""

import json
import shlex
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.scenes import assembly_payload, scene_payload
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


def test_validation_only_returns_all_errors_without_submitting(pilot):
    _, app = pilot
    app.state.manager.submit = Mock()
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "render_video_scene",
            "arguments": {
                "project_id": PID,
                "request_id": "check",
                "scene_id": "idea",
                "scene": {
                    "duration": 3.8,
                    "marks": [
                        {"id": name, "kind": "ellipse", "keyframes": [{"time": -0.1}]}
                        for name in ("halo", "wire")
                    ],
                },
                "note": "Check timing",
                "creative_revision": 2,
                "validate_only": True,
            },
        },
    )
    report = result["structuredContent"]
    assert not report["valid"]
    assert len(report["errors"]) == 2
    assert "halo" in report["errors"][0] and "wire" in report["errors"][1]
    app.state.manager.submit.assert_not_called()


def test_assembly_keeps_drawing_and_audio_data_out_of_shell():
    text = "$(touch unsafe); '</script>"
    source = SCENE | {"marks": [{"id": "title", "kind": "text", "text": text}]}
    payload = assembly_payload(
        "assembly",
        ["saved", "new"],
        {"new": source},
        "Full idea",
        3,
        narration_path="audio/voice '; $(touch unsafe).mp3",
    )
    assert len(payload["files"]) == 2
    assert payload["files"][0]["path"] == "edit/scenes/new.json"
    assert text not in payload["command"]
    spec = json.loads(payload["files"][-1]["content"])
    assert spec["scene_ids"] == ["saved", "new"]
    assert spec["narration_path"] == "audio/voice '; $(touch unsafe).mp3"
    assert payload["preview_path"] == payload["review_path"]
    assert "quality=final" in payload["next_action"]
    assert payload["assembly_report"].endswith(".assembly.json")
    final = assembly_payload("final", ["saved"], {}, "Final", 3, quality="final")
    assert "then export" in final["next_action"]


def test_assembly_rejects_unlisted_or_invalid_scene_data_before_submission():
    with pytest.raises(ValueError, match="keys"):
        assembly_payload("r", ["saved"], {"other": SCENE}, "Draft", 2)
    with pytest.raises(ValueError, match="new:"):
        assembly_payload(
            "r", ["saved", "new"], {"new": SCENE | {"duration": 30}}, "Draft", 2
        )


def test_assembly_tool_is_discovered_with_quality_and_inline_scene_contract(pilot):
    tool = next(
        t
        for t in rpc(pilot, "tools/list", {})["tools"]
        if t["name"] == "assemble_video"
    )
    assert "ui" not in tool.get("_meta", {})
    args = tool["inputSchema"]["properties"]
    assert args["quality"]["enum"] == ["draft", "final"]
    assert "scenes" in args and "scene_ids" in args
