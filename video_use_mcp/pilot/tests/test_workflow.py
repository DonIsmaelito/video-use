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


def test_choices_are_optional_persisted_and_scoped(pilot):
    state = call(
        pilot,
        "start_video",
        dict(title="Sound", brief="Explain sound", category="explainer"),
    )
    pid = state["project_id"]
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
