"""Intake gates paid work, while legacy projects and exact retries remain usable."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from video_use_mcp.pilot.runtime import Manager, require_production_intake
from video_use_mcp.pilot.scenes import assembly_payload, register_scenes, scene_payload


def creative(mode="delegate", *, ready=True, review="not_requested", **intake):
    return {
        "revision": 1,
        "intake": {
            "version": 1,
            "mode": mode,
            "output_profile": {"duration_seconds": 30, "viewing_destination": "YouTube"}
            if ready
            else {},
            "delegated_basics": [],
            "provenance": {"mode": "user_submit"},
            "excerpt_review": {"status": review},
            **intake,
        },
    }


def fixture(state):
    values = {"creative": deepcopy(state), "tasks": []}
    store = Mock()
    store.get.side_effect = (
        lambda kind, key: deepcopy(values["creative"]) if kind == "creative" else None
    )
    store.reserve.return_value = "reservation"

    def sql(query, *params):
        if query.startswith("SELECT * FROM public.vp_tasks"):
            return deepcopy(values["tasks"])
        if query.startswith("INSERT INTO public.vp_tasks"):
            task = dict(
                id=params[0],
                owner=params[1],
                project=params[2],
                operation=params[3],
                request_id=params[4],
                payload=json.loads(params[5]),
                usage_id=params[6],
                status="queued",
            )
            values["tasks"].append(task)
            return [task]
        return []

    store.sql.side_effect = sql
    manager = Manager(store, SimpleNamespace(api_key="", speech_key=""))
    return manager, store, values


@pytest.mark.parametrize(
    "state",
    [
        creative(None),
        creative("delegate", ready=False),
        creative(
            "hands_on", pending_questions={"widget_id": "choice", "answered": False}
        ),
        creative("hands_on", pending_style={"answered": False}),
    ],
)
def test_unresolved_intake_blocks_all_production_before_reservation(state):
    manager, store, values = fixture(state)
    for operation in (
        "step",
        "narrate",
        "transcribe",
        "run",
        "write",
        "patch",
        "review",
        "preview",
        "export",
    ):
        with pytest.raises(ValueError, match="intake choices"):
            manager.submit("u", "p", operation, {"creative_revision": 1}, operation)
    store.reserve.assert_not_called()
    assert not values["tasks"] and not manager.running


@pytest.mark.parametrize(
    "state",
    [
        None,
        {"revision": 1},
        creative("delegate"),
        creative("key_moments"),
        creative("hands_on", review="approved"),
    ],
)
def test_legacy_delegate_selective_and_accepted_excerpt_allow_production(state):
    manager, store, _ = fixture(state)
    manager.execute = AsyncMock()

    async def scenario():
        task = manager.submit("u", "p", "step", {"creative_revision": 1}, "full")
        await asyncio.gather(*list(manager.running.values()))
        return task

    result = asyncio.run(scenario())
    store.reserve.assert_called_once()
    manager.execute.assert_awaited_once()
    assert result["status"] == "queued"


@pytest.mark.parametrize("status", ["not_requested", "pending", "changes_requested"])
def test_hands_on_blocks_full_work_but_allows_excerpt_and_supporting_work(status):
    state = creative("hands_on", review=status)
    for operation, payload in (
        ("step", {}),
        ("step", {"production_stage": "full_video"}),
        ("run", {}),
        ("export", {}),
    ):
        manager, store, _ = fixture(state)
        with pytest.raises(ValueError, match="explicit excerpt acceptance"):
            manager.submit(
                "u", "p", operation, payload | {"creative_revision": 1}, "work"
            )
        store.reserve.assert_not_called()
    for operation, payload in (
        ("step", {"production_stage": "excerpt"}),
        ("narrate", {}),
        ("review", {}),
        ("preview", {}),
        ("transcribe", {}),
        ("write", {}),
        ("patch", {}),
    ):
        require_production_intake(state, operation, payload)


def test_unknown_custom_stage_cannot_bypass_hands_on():
    with pytest.raises(ValueError, match="production_stage"):
        require_production_intake(
            creative("hands_on"), "step", {"production_stage": "planning"}
        )


def test_exact_completed_retry_does_not_create_work_when_intake_changed():
    manager, store, values = fixture(creative(None))
    previous = dict(
        id="old",
        owner="u",
        project="p",
        operation="narrate",
        payload={"text": "Hello"},
        status="succeeded",
    )
    values["tasks"].append(previous)
    assert manager.submit("u", "p", "narrate", {"text": "Hello"}, "retry") == previous
    store.reserve.assert_not_called()
    assert not manager.running


def test_changed_intake_after_admission_blocks_workspace_and_refunds_reservation():
    manager, store, values = fixture(creative("delegate"))
    manager.session = AsyncMock()
    manager.perform = AsyncMock()

    async def scenario():
        manager.submit("u", "p", "narrate", {"text": "Hello"}, "voice")
        values["creative"] = creative(None)
        await asyncio.gather(*list(manager.running.values()))

    asyncio.run(scenario())
    manager.session.assert_not_awaited()
    manager.perform.assert_not_awaited()
    store.settle.assert_called_once_with("reservation", 0)
    assert any("status='failed'" in call.args[0] for call in store.sql.call_args_list)


def test_perform_rechecks_before_sandbox_io_or_speech_provider():
    manager, store, _ = fixture(creative(None))
    sandbox = SimpleNamespace(write=AsyncMock(), run=AsyncMock(), upload=AsyncMock())
    task = dict(
        id="task",
        owner="u",
        project="p",
        operation="narrate",
        payload={"text": "Hello"},
    )
    with patch("video_use_mcp.pilot.runtime.ProductionAgent") as speech:
        with pytest.raises(ValueError, match="intake choices"):
            asyncio.run(manager.perform(task, sandbox))
        speech.assert_not_called()
    sandbox.write.assert_not_awaited()
    sandbox.run.assert_not_awaited()
    store.reserve.assert_not_called()


def test_scene_and_assembly_payloads_have_explicit_distinct_production_scope():
    scene = {
        "duration": 3,
        "marks": [{"id": "idea", "kind": "text", "text": "An idea"}],
    }
    excerpt = scene_payload(
        "one", scene, "First sample", 1, "", 0, production_stage="excerpt"
    )
    full = assembly_payload(
        "full", ["one"], {"one": scene}, "Full film", 1, production_stage="full_video"
    )
    assembled_excerpt = assembly_payload(
        "sample", ["one"], {"one": scene}, "Small sample", 1, production_stage="excerpt"
    )
    assert (
        excerpt["production_stage"]
        == assembled_excerpt["production_stage"]
        == "excerpt"
    )
    assert full["production_stage"] == "full_video"
    assert "production_stage" not in json.loads(
        assembled_excerpt["files"][-1]["content"]
    )


@pytest.mark.parametrize("tool_name", ["render_video_scene", "assemble_video"])
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("explicit_excerpt", [False, True])
def test_tool_scope_defaults_full_but_preserves_legacy_retry_payload(
    tool_name, legacy, explicit_excerpt
):
    functions = {}

    def tool(**kwargs):
        def register(function):
            functions[function.__name__] = function
            return function

        return register

    store = Mock()
    store.get.return_value = {"revision": 1} if legacy else creative("hands_on")
    manager = SimpleNamespace(
        submit=Mock(return_value={"id": "task", "status": "succeeded"})
    )
    register_scenes(
        SimpleNamespace(tool=tool),
        store,
        manager,
        lambda mutate: "u",
        {"task_result": AsyncMock()},
        None,
    )
    scene = {"duration": 3, "marks": [{"id": "idea", "kind": "text", "text": "Idea"}]}
    args = dict(project_id="p", request_id="sample", creative_revision=1, note="Sample")
    if tool_name == "render_video_scene":
        args.update(scene_id="one", scene=scene)
        expected = scene_payload("one", scene, "Sample", 1, "", 0)
    else:
        args.update(scene_ids=["one"], scenes={"one": scene})
        expected = assembly_payload(
            "sample",
            ["one"],
            {"one": scene},
            "Sample",
            1,
            narration_path="",
            narration_offset=0,
            quality="draft",
            width=0,
            height=0,
            fps=0,
            audio_normalization="web",
        )
    if explicit_excerpt:
        args["production_stage"] = "excerpt"
    with patch("video_use_mcp.pilot.scenes.wait_for_task", new=AsyncMock()):
        asyncio.run(functions[tool_name](**args))
    payload = manager.submit.call_args.args[3]
    if legacy and not explicit_excerpt:
        assert "production_stage" not in payload
        assert payload == expected
        assert payload["next_action"].startswith("Show this")
    else:
        assert payload["production_stage"] == (
            "excerpt" if explicit_excerpt else "full_video"
        )
