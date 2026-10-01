"""Current preferences and actual media must reach both host response surfaces."""

import json
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from video_use_mcp.pilot.interaction import creative_handoff
from video_use_mcp.pilot.runtime import Manager
from video_use_mcp.pilot.tests.test_cards import PID, rpc
from video_use_mcp.pilot.tests.test_preview_delivery import TID, task_result
from video_use_mcp.pilot.tests.test_preview_updates import progress
from video_use_mcp.pilot.tests.test_workflow import call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_admitted_speech_snapshot_survives_preference_change_and_exact_retry():
    async def scenario():
        store = Mock()
        state = {"revision": 3}
        store.get.side_effect = (
            lambda kind, key: state.copy() if kind == "creative" else None
        )
        tasks = []

        def sql(query, *args):
            if query.startswith("SELECT * FROM public.vp_tasks"):
                return tasks.copy()
            if query.startswith("INSERT INTO public.vp_tasks"):
                task = {
                    "id": args[0],
                    "owner": args[1],
                    "project": args[2],
                    "operation": args[3],
                    "request_id": args[4],
                    "payload": json.loads(args[5]),
                }
                tasks.append(task)
                return [task]
            return []

        store.sql.side_effect = sql
        manager = Manager(store, SimpleNamespace())
        manager.execute = AsyncMock()
        args = {"text": "Hello", "output": "audio/narration.mp3"}
        first = manager.submit("owner", "project", "narrate", args, "speech")
        state["revision"] = 4
        repeated = manager.submit("owner", "project", "narrate", args, "speech")
        assert repeated["id"] == first["id"]
        assert first["payload"] == args  # metadata does not alter retry identity
        store.put.assert_called_once_with(
            "task_context", first["id"], {"submitted_creative_revision": 3}, ttl=2592000
        )
        await manager.running[first["id"]]
        manager.execute.assert_awaited_once()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "operation", ["narrate", "transcribe", "step", "review", "export"]
)
def test_task_result_returns_choice_that_changed_while_work_ran(pilot, operation):
    _, app = pilot
    app.state.store.put("task_context", TID, {"submitted_creative_revision": 1})
    current = {
        "revision": 2,
        "selected": "editorial",
        "selection_source": "user_click",
        "preferences": "Keep my logo",
        "assumptions": "General audience",
        "latest_feedback": {"note": "Use larger labels", "object_id": "earlier-draft"},
    }
    app.state.store.put("creative", PID, current)
    app.state.store.task = Mock(
        return_value={
            "id": TID,
            "project": PID,
            "operation": operation,
            "status": "succeeded",
            "result": {},
            "payload": {},
            "error": None,
            "created": "",
            "updated": "",
        }
    )
    app.state.manager.running = {}
    response = rpc(
        pilot, "tools/call", {"name": "get_video_task", "arguments": {"task_id": TID}}
    )
    assert not response.get("isError"), response
    data = response["structuredContent"]
    assert json.loads(response["content"][0]["text"]) == data
    assert data["creative"] == current
    handoff = data["creative_handoff"]
    assert handoff["current_revision"] == 2
    assert handoff["submitted_revision"] == 1
    assert handoff["preferences_changed"] is True
    assert handoff["selected_by_user"] is True
    assert "preferences changed" in data["next_action"]


def test_missing_revision_snapshot_is_unknown_not_an_unchanged_claim():
    state = {"revision": 2, "default": "diagram", "direction": "Navy diagrams"}
    result = creative_handoff({"operation": "narrate", "payload": {}}, state)
    assert result["preferences_changed"] is None
    assert result["submitted_revision"] is None
    assert result["selected_by_user"] is False
    assert state == {"revision": 2, "default": "diagram", "direction": "Navy diagrams"}


def test_render_payload_revision_is_used_without_inventing_change():
    result = creative_handoff(
        {"operation": "step", "payload": {"creative_revision": 3}},
        {"revision": 3, "selected": "diagram", "selection_source": "agent_default"},
    )
    assert result["preferences_changed"] is False
    assert result["selected_by_user"] is False


def test_preview_context_and_commentary_instruction_are_present_on_both_surfaces(pilot):
    _, app = pilot
    progress(app)
    current = {"revision": 3, "selected": "editorial", "selection_source": "user_click"}
    app.state.store.put("creative", PID, current)
    response = rpc(
        pilot,
        "tools/call",
        {"name": "show_video_preview", "arguments": {"project_id": PID}},
    )
    assert not response.get("isError"), response
    data = response["structuredContent"]
    assert json.loads(response["content"][0]["text"]) == data
    assert data["creative"] == current
    assert "chat sentence" in data["next_action"]
    assert "do not require a reply" in data["next_action"]
    assert data["media"]["object_id"] == "draft"


def test_assumptions_remain_distinct_from_user_preferences_and_preserve_on_update(
    pilot,
):
    result = call(
        pilot,
        "start_video",
        {
            "title": "Explain rain",
            "brief": "A short explainer of rain with narration",
            "category": "explainer",
            "preferences": "30 seconds and voiceover",
            "assumptions": "General audience; landscape; spare diagrams",
        },
    )
    state = result["creative"]
    assert state["brief_provenance"] == "assistant_summary"
    assert state["preferences"] == "30 seconds and voiceover"
    assert state["assumptions"] == "General audience; landscape; spare diagrams"
    assert "selected" not in state and "selection_source" not in state
    updated = call(
        pilot,
        "start_video",
        {
            "project_id": result["project_id"],
            "title": "Explain rain",
            "brief": "Explain rain more clearly",
            "category": "explainer",
        },
    )
    assert updated["creative"]["assumptions"] == state["assumptions"]
    assert updated["creative"]["preferences"] == state["preferences"]
    cleared = call(
        pilot,
        "start_video",
        {
            "project_id": result["project_id"],
            "title": "Explain rain",
            "brief": "Explain rain more clearly",
            "category": "explainer",
            "assumptions": "",
        },
    )
    assert cleared["creative"]["assumptions"] == ""
    assert cleared["creative"]["preferences"] == state["preferences"]


def test_choices_have_nonblocking_instruction_in_structured_result(pilot):
    project = call(
        pilot,
        "start_video",
        {"title": "Sound", "brief": "Explain sound", "category": "explainer"},
    )
    response = rpc(
        pilot,
        "tools/call",
        {
            "name": "show_video_choices",
            "arguments": {"project_id": project["project_id"]},
        },
    )
    data = response["structuredContent"]
    assert json.loads(response["content"][0]["text"]) == data
    assert "a click is optional" in data["next_action"]
    assert "approved" in data["next_action"]
    saved = pilot[1].state.store.get("creative", project["project_id"])
    assert "selected" not in saved and "selection_source" not in saved


def test_assembly_paths_and_exact_timing_survive_compact_log_response(pilot):
    assembly = {
        "output": "edit/assembled/draft.mp4",
        "quality": "draft",
        "duration": 7.067,
        "scenes": [
            {
                "scene_id": "mechanism",
                "seconds": 7.067,
                "video_path": "edit/scenes/mechanism.mp4",
                "reused": True,
            }
        ],
    }
    _, data = task_result(
        pilot, result={"stdout": "render output " * 1000, "assembly": assembly}
    )
    assert len(data["result"]["stdout"]) == 2000
    assert data["assembly"] == assembly
    assert "assemble_video quality=final" in data["next_action"]
