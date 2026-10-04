"""Completed speech hands the host usable inputs for its next visible draft."""

import copy
import json
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]
TID = "790d0a5a-eb6a-4115-99a2-1e63dbe03e9c"


def narration_result():
    return {
        "audio_path": "edit/narration.mp3",
        "timing_path": "edit/narration.mp3.json",
        "duration": 31.7649,
        "speech_end": 31.61,
        "sentence_timings": [
            {"text": "Sunlight reaches a panel.", "start": 0, "end": 4}
        ],
        "word_timings": [{"text": "Sunlight", "start": 0, "end": 0.6}],
    }


def read_task(pilot, *, status="succeeded", result=None, operation="narrate"):
    _, app = pilot
    task = {
        "id": TID,
        "project": PID,
        "operation": operation,
        "status": status,
        "result": result,
        "payload": {},
        "error": "Speech failed" if status == "failed" else None,
        "created": "",
        "updated": "",
    }
    before = copy.deepcopy(task)
    app.state.store.task = Mock(return_value=task)
    app.state.manager.running = {}
    response = rpc(
        pilot, "tools/call", {"name": "get_video_task", "arguments": {"task_id": TID}}
    )
    assert not response.get("isError"), response
    data = response["structuredContent"]
    assert json.loads(response["content"][0]["text"]) == data
    assert task == before, "A read must not mutate the persisted task"
    return response, data


@pytest.mark.parametrize("cached", [False, True])
def test_saved_narration_advances_to_real_excerpt_without_resynthesis(pilot, cached):
    result = narration_result() | {"cached": cached}
    response, data = read_task(pilot, result=result)
    assert data["result"] == result
    assert data["narration_continuation"] == {
        "audio_path": "edit/narration.mp3",
        "timing_path": "edit/narration.mp3.json",
        "duration": 31.7649,
        "speech_end": 31.61,
    }
    instruction = data["next_action"]
    assert "Reuse result.audio_path" in instruction
    assert "inline sentence_timings/word_timings" in instruction
    assert "at most 20 seconds" in instruction
    assert "render_video_scene" in instruction and "run_video_step" in instruction
    assert "If no meaningful draft exists yet" in instruction
    assert "After a meaningful new render succeeds" in instruction
    assert "preview_delivery" in instruction
    assert "Preserve hands-on sample approval" in instruction
    assert "final export must open in a separate player" in instruction
    assert "poll this completed task" in instruction
    assert "rerun completed speech merely to resume" in instruction
    assert "never silently trim" in instruction
    assert "exact limit" in instruction
    # No renderer arguments, fabricated visual, or player for speech alone.
    for key in ("next_tool", "display_action", "media", "project_card"):
        assert key not in data
    assert [item["type"] for item in response["content"]] == ["text"]


def test_rereading_narration_uses_current_revision_without_rewriting_progress(pilot):
    _, app = pilot
    store = app.state.store
    creative = {"revision": 4, "direction": "Keep the latest blue diagram style"}
    progress = {"stage": "draft", "next_action": "Inspect current film", "updates": []}
    store.put("creative", PID, creative)
    store.put("progress", PID, progress)
    store.put("task_context", TID, {"submitted_creative_revision": 1})
    store.put = Mock(wraps=store.put)

    _, first = read_task(pilot, result=narration_result())
    _, second = read_task(pilot, result=narration_result())
    assert first == second
    assert first["narration_continuation"]["creative_revision"] == 4
    assert first["creative_handoff"]["preferences_changed"] is True
    assert "preferences changed" in first["next_action"]
    assert "If a draft or finished video already exists" in first["next_action"]
    assert (
        "rereading this narration is not a reason to restart work"
        in first["next_action"]
    )
    assert store.get("progress", PID) == progress
    assert store.get("creative", PID) == creative
    assert all(
        call.args[0] not in {"progress", "creative"}
        for call in store.put.call_args_list
    )


@pytest.mark.parametrize("status", ["queued", "running", "failed", "cancelled"])
def test_unfinished_or_failed_speech_does_not_offer_success_continuation(pilot, status):
    _, data = read_task(pilot, status=status, result=narration_result())
    assert "narration_continuation" not in data
    assert "display_action" not in data
    if status in {"queued", "running"}:
        assert data["next_tool"] == {
            "name": "get_video_task",
            "arguments": {"task_id": TID},
        }
    else:
        assert "next_tool" not in data
        assert "correct only the failed work" in data["next_action"]


@pytest.mark.parametrize(
    ("operation", "result"),
    [
        ("narrate", {"saved": "edit/legacy.mp3"}),
        ("narrate", narration_result() | {"exit_code": 1}),
        ("transcribe", narration_result()),
        ("step", narration_result()),
    ],
)
def test_continuation_requires_successful_narration_and_saved_audio(
    pilot, operation, result
):
    _, data = read_task(pilot, operation=operation, result=result)
    assert "narration_continuation" not in data


def test_partial_legacy_metadata_does_not_invent_duration_or_creative_revision(pilot):
    _, data = read_task(pilot, result={"audio_path": "edit/old.mp3"})
    assert data["narration_continuation"] == {"audio_path": "edit/old.mp3"}
    assert "any returned inline" in data["next_action"]
    assert "when supplied" in data["next_action"]


def test_narration_allowance_reports_the_actual_blocker_without_retry_loop(pilot):
    _, app = pilot
    task = {
        "id": TID,
        "project": PID,
        "operation": "narrate",
        "status": "failed",
        "payload": {},
        "result": {},
        "created": "",
        "updated": "",
        "error": "Storage/database request failed (500): narrate allowance reached",
    }
    app.state.store.task = Mock(return_value=task)
    app.state.manager.running = {}
    result = rpc(
        pilot, "tools/call", {"name": "get_video_task", "arguments": {"task_id": TID}}
    )
    data = result["structuredContent"]
    assert json.loads(result["content"][0]["text"]) == data
    assert data["blocker"]["kind"] == "service_allowance"
    assert data["blocker"]["automatic_retry"] is False
    assert "500" not in data["error"]
    assert "not their Claude/ChatGPT subscription" in data["next_action"]
    assert "new request_id" in data["next_action"]
    assert "Do not present a silent draft as complete" in data["next_action"]
    assert "display_action" not in data and "narration_continuation" not in data
    with app.state.store.db() as db:
        rows = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    trace = app.state.store.get("trace", rows[-1]["key"])
    assert trace["task_status"] == "failed" and trace["outcome"] == "task_failed"
