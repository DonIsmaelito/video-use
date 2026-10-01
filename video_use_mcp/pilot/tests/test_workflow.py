import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import pytest
from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.runtime import Manager

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def call(pilot, name, args):
    r = rpc(pilot, "tools/call", dict(name=name, arguments=args))
    assert not r.get("isError"), r
    return r.get("structuredContent") or json.loads(r["content"][0]["text"])


def legacy_project(pilot, pid):
    """Existing projects retain their pre-intake interaction behavior."""
    state = pilot[1].state.store.get("creative", pid)
    state.pop("intake", None)
    state.pop("widgets", None)
    pilot[1].state.store.put("creative", pid, state)


def test_legacy_choices_are_optional_persisted_and_scoped(pilot):
    state = call(
        pilot,
        "start_video",
        dict(title="Sound", brief="Explain sound", category="explainer"),
    )
    pid = state["project_id"]
    legacy_project(pilot, pid)
    assert state["creative"]["revision"] == 1
    r = call(pilot, "show_video_choices", dict(project_id=pid))
    assert len(r["choices"]["options"]) == 2
    assert all(o["url"].startswith("https://") for o in r["choices"]["options"])
    selected = call(
        pilot,
        "choose_video_style",
        dict(project_id=pid, revision=1, choice="editorial"),
    )
    assert selected["creative"]["selected"] == "editorial"
    assert selected["creative"]["revision"] == 2
    for choice, revision in [("diagram", 1), ("invented", 2)]:
        r = rpc(
            pilot,
            "tools/call",
            dict(
                name="choose_video_style",
                arguments=dict(project_id=pid, revision=revision, choice=choice),
            ),
        )
        assert r["isError"]
    result = call(
        pilot,
        "plan_video",
        dict(
            project_id=pid,
            revision=2,
            beats=[
                dict(title="Cancellation", visual="Opposing waves combine", seconds=6)
            ],
        ),
    )
    assert result["creative"]["revision"] == 3
    assert result["creative"]["selected"] == "editorial"
    # Planning advances render context but must not expire the visible picker.
    clicked = call(
        pilot, "choose_video_style", dict(project_id=pid, revision=2, choice="diagram")
    )
    assert clicked["creative"]["revision"] == 4
    assert clicked["creative"]["choice_revision"] == 3
    assert clicked["creative"]["beats"] == result["creative"]["beats"]
    pilot[1].state.store.project.side_effect = PermissionError("Not your project")
    r = rpc(
        pilot,
        "tools/call",
        dict(
            name="choose_video_style",
            arguments=dict(project_id=pid, revision=3, choice="diagram"),
        ),
    )
    assert r["isError"]


def test_precise_edit_does_not_offer_templates(pilot):
    state = call(
        pilot,
        "start_video",
        dict(title="Trim", brief="Remove last two seconds", category="precise_edit"),
    )
    assert not state["workflow"]["choices"]
    result = rpc(
        pilot,
        "tools/call",
        dict(name="show_video_choices", arguments=dict(project_id=state["project_id"])),
    )
    assert result["isError"]


def test_category_change_preserves_user_edits_and_retires_old_style_picker(pilot):
    from video_use_mcp.pilot.tests.test_widgets import BEATS, QUESTIONS, save, show

    started = call(
        pilot,
        "start_video",
        dict(
            title="Sound",
            brief="Explain sound",
            category="explainer",
            preferences="Keep my logo",
            assumptions="A short landscape explainer",
        ),
    )
    pid = started["project_id"]
    legacy_project(pilot, pid)
    brief = show(pilot, pid)
    save(pilot, brief, answers={"audience": "kids"})
    story = show(pilot, pid, "story")
    beats = [dict(beat) for beat in BEATS]
    beats[0]["narration"] = "Keep this exact opening from me."
    save(pilot, story, beats=beats)
    call(pilot, "show_video_choices", dict(project_id=pid))
    call(
        pilot,
        "choose_video_style",
        dict(project_id=pid, revision=1, choice="editorial"),
    )
    store = pilot[1].state.store
    before = store.get("creative", pid)
    before["latest_feedback"] = {"note": "Keep the opening diagram"}
    store.put("creative", pid, before)
    updated = call(
        pilot,
        "start_video",
        dict(
            project_id=pid,
            title="Sound from my slides",
            brief="Turn my sound lesson into a video",
            category="document_video",
        ),
    )["creative"]
    for key in (
        "preferences",
        "assumptions",
        "brief_answers",
        "beats",
        "script",
        "plan_provenance",
        "latest_feedback",
        "latest_widget_change",
    ):
        assert updated[key] == before[key], key
    assert updated["revision"] == before["revision"] + 1
    assert updated["category"] == "document_video"
    assert not {"offered", "default", "selected", "selection_source"}.intersection(
        updated
    )
    assert updated["visual_choice_history"][-1] == dict(
        category="explainer",
        selected="editorial",
        source="user_click",
        creative_revision=before["revision"],
    )
    assert store.get("creative", pid)["widgets"] == before["widgets"]
    stale = rpc(
        pilot,
        "tools/call",
        dict(
            name="choose_video_style",
            arguments=dict(
                project_id=pid,
                revision=before["choice_revision"],
                choice="diagram",
            ),
        ),
    )
    assert stale["isError"]
    # Previously saved widget requests remain idempotent after reclassification.
    retried = save(pilot, brief, answers={"audience": "kids"})
    assert (
        retried["repeated"] and retried["creative"]["revision"] == updated["revision"]
    )
    reopened = show(pilot, pid, questions=[QUESTIONS[0]])
    assert reopened["widget"]["answers"] == {"audience": "kids"}


def test_parallel_components_bounded_and_assembly_only_on_success():
    async def scenario(fail):
        store = Mock()
        store.get.return_value = None
        manager = Manager(store, SimpleNamespace())
        manager.event = Mock()
        active = 0
        peak = 0
        completed = []

        async def run(command, timeout):
            nonlocal active, peak
            if command == "assemble":
                assert len(completed) == 5
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            completed.append(command)
            return dict(
                exit_code=int(fail and command == "scene-2"), stdout=command, stderr=""
            )

        sb = SimpleNamespace(run=AsyncMock(side_effect=run), write=AsyncMock())
        task = dict(
            owner="u",
            project="p",
            id="t",
            operation="step",
            payload=dict(
                components=[
                    dict(name=f"scene-{i}", command=f"scene-{i}") for i in range(5)
                ],
                command="assemble",
                stage="planning",
                note="Scenes",
            ),
        )
        result = await manager.perform(task, sb)
        assert peak == 2
        assert ("assemble" in completed) == (not fail)
        assert bool(result.get("exit_code")) == fail

    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_preference_changes_block_stale_render_and_export():
    store = Mock()
    store.get.side_effect = (
        lambda k, p: {"revision": 3}
        if k == "creative"
        else (2 if k == "render_revision" else None)
    )
    manager = Manager(store, SimpleNamespace())
    sb = SimpleNamespace(run=AsyncMock(), write=AsyncMock())
    for op in ("step", "export"):
        task = dict(
            owner="u",
            project="p",
            id="t",
            operation=op,
            payload=dict(creative_revision=2),
        )
        with pytest.raises(ValueError, match="preferences changed"):
            asyncio.run(manager.perform(task, sb))
    sb.run.assert_not_awaited()
