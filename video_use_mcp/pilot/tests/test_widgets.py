"""Optional widgets preserve user edits, revision safety and retry identity."""

from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.interaction import UI_URI
from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_workflow import call
from video_use_mcp.pilot.tests.test_narration_continuation import (
    read_task,
    narration_result,
)

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


QUESTIONS = [
    dict(
        id="audience",
        prompt="Who is this for?",
        recommended="general",
        options=[
            dict(id="general", label="Everyone"),
            dict(id="kids", label="Children"),
        ],
    ),
    dict(
        id="tone",
        prompt="What should it feel like?",
        options=[
            dict(id="warm", label="Warm and curious"),
            dict(id="precise", label="Clear and precise"),
        ],
    ),
]
BEATS = [
    dict(
        id="opening",
        title="Start with a question",
        visual="Phone beside a router",
        narration="How does this phone reach the internet?",
        seconds=5,
    ),
    dict(
        id="mechanism",
        title="The connection",
        visual="Packets move between router and phone",
        narration="The router sends data using radio waves.",
        seconds=6,
    ),
]


@pytest.fixture
def project(pilot):
    project_id = call(
        pilot,
        "start_video",
        dict(title="Wi-Fi", brief="Explain Wi-Fi", category="explainer"),
    )["project_id"]
    # This file covers the legacy optional-editor contract. The explicit v1
    # mode/basics flow is exercised separately in test_intake.py.
    store = pilot[1].state.store
    state = store.get("creative", project_id)
    state.pop("intake", None)
    store.put("creative", project_id, state)
    return project_id


def show(pilot, project, kind="brief", **updates):
    state = pilot[1].state.store.get("creative", project)
    args = dict(project_id=project, creative_revision=state["revision"])
    args.update(questions=deepcopy(QUESTIONS)) if kind == "brief" else args.update(
        beats=deepcopy(BEATS)
    )
    return call(pilot, "show_video_" + kind, args | updates)


def save(pilot, shown, **changes):
    args = (
        dict(
            project_id=shown["project_id"],
            widget_id=shown["widget"]["id"],
            revision=shown["widget"]["revision"],
            request_id="click-1",
        )
        | changes
    )
    return call(pilot, "save_video_widget", args)


def error(pilot, name, args):
    result = rpc(pilot, "tools/call", dict(name=name, arguments=args))
    assert result["isError"], result


def test_widget_discovery_and_matching_response_surfaces(pilot, project):
    tools = {t["name"]: t for t in rpc(pilot, "tools/list", {})["tools"]}
    for name in ("show_video_brief", "show_video_story"):
        assert tools[name]["_meta"]["ui"]["resourceUri"] == UI_URI
    assert tools["save_video_widget"]["_meta"]["ui"]["visibility"] == ["app"]
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="show_video_brief",
            arguments=dict(
                project_id=project, creative_revision=1, questions=QUESTIONS
            ),
        ),
    )
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert "widgets" not in result["structuredContent"]["creative"]


def test_recommendations_are_not_selections_or_approval(pilot, project):
    shown = show(pilot, project)
    assert shown["widget"]["answers"] == {}
    assert shown["creative"]["revision"] == 1
    assert "brief_answers" not in shown["creative"]
    assert "not an approval gate" in shown["next_action"]
    assert "Do not end the turn" in shown["next_action"]


def test_partial_brief_answers_preserve_unrelated_changes_and_are_idempotent(
    pilot, project
):
    shown = show(pilot, project)
    store = pilot[1].state.store
    state = store.get("creative", project)
    state.update(
        revision=2,
        preferences="Keep my logo",
        selected="editorial",
        latest_feedback={"note": "Bigger labels"},
    )
    store.put("creative", project, state)
    saved = save(pilot, shown, answers={"audience": "kids"})
    assert saved["creative"]["revision"] == 3
    assert saved["creative"]["brief_answers"] == [
        dict(
            question_id="audience",
            question="Who is this for?",
            option_id="kids",
            answer="Children",
            source="user_submit",
        )
    ]
    assert saved["creative"]["preferences"] == "Keep my logo"
    assert saved["creative"]["latest_feedback"] == {"note": "Bigger labels"}
    assert saved["creative"]["latest_widget_change"]["source"] == "user_submit"
    repeated = save(pilot, shown, answers={"audience": "kids"})
    assert repeated["repeated"] and repeated["creative"]["revision"] == 3
    assert (
        "receipts" not in repeated["widget"] and "widgets" not in repeated["creative"]
    )


def test_successive_briefs_preserve_prior_answers_and_reopen_actual_choices(
    pilot, project
):
    audience = show(pilot, project, questions=[QUESTIONS[0]])
    save(pilot, audience, answers={"audience": "kids"})
    tone = show(pilot, project, questions=[QUESTIONS[1]])
    assert tone["widget"]["answers"] == {}
    saved = save(pilot, tone, answers={"tone": "warm"})
    answers = {a["question_id"]: a for a in saved["creative"]["brief_answers"]}
    assert answers["audience"]["answer"] == "Children"
    assert answers["tone"]["answer"] == "Warm and curious"
    assert all(a["source"] == "user_submit" for a in answers.values())
    reopened = show(pilot, project, questions=[QUESTIONS[0]])
    assert reopened["widget"]["answers"] == {"audience": "kids"}
    cleared = save(pilot, reopened, answers={})
    assert cleared["saved"]
    assert cleared["creative"]["brief_answers"] == [answers["tone"]]


def test_new_brief_keeps_legacy_answers_outside_its_questions(pilot, project):
    store = pilot[1].state.store
    state = store.get("creative", project)
    legacy = dict(question="Who is this for?", answer="Children")
    state["brief_answers"] = [legacy]
    store.put("creative", project, state)
    tone = show(pilot, project, questions=[QUESTIONS[1]])
    saved = save(pilot, tone, answers={"tone": "precise"})
    assert saved["creative"]["brief_answers"][0] == legacy
    reopened = show(pilot, project, questions=[QUESTIONS[0]])
    assert reopened["widget"]["answers"] == {"audience": "kids"}
    changed = save(pilot, reopened, answers={"audience": "general"})
    assert len(changed["creative"]["brief_answers"]) == 2
    assert changed["creative"]["brief_answers"][-1]["question_id"] == "audience"
    assert changed["creative"]["brief_answers"][-1]["answer"] == "Everyone"


def test_conflicting_retry_and_stale_revision_do_not_overwrite(pilot, project):
    shown = show(pilot, project)
    saved = save(pilot, shown, answers={"audience": "kids"})
    args = dict(
        project_id=project,
        widget_id=shown["widget"]["id"],
        revision=1,
        request_id="click-1",
        answers={"audience": "general"},
    )
    error(pilot, "save_video_widget", args)
    error(pilot, "save_video_widget", args | {"request_id": "click-2"})
    assert (
        pilot[1].state.store.get("creative", project)["revision"]
        == saved["creative"]["revision"]
    )


def test_replaced_picker_rejects_old_card(pilot, project):
    shown = show(pilot, project)
    show(pilot, project)
    error(
        pilot,
        "save_video_widget",
        dict(
            project_id=project,
            widget_id=shown["widget"]["id"],
            revision=1,
            request_id="click",
            answers={"audience": "kids"},
        ),
    )


def test_story_is_a_proposal_then_user_changes_reach_task_context(pilot, project):
    shown = show(pilot, project, "story")
    assert shown["creative"]["plan_provenance"] == "assistant_plan"
    assert shown["creative"]["revision"] == 2
    beats = deepcopy(BEATS)
    beats[0]["narration"] = "What connects my phone to the world?"
    beats[0]["seconds"] = 4
    saved = save(pilot, shown, beats=beats)
    assert saved["creative"]["plan_provenance"] == "user_edit"
    assert saved["creative"]["beats"] == beats
    assert saved["creative"]["script"].startswith(beats[0]["narration"])
    # The task fixture uses a known different ID; copy state to check public
    # response propagation through the actual task result handler.
    from video_use_mcp.pilot.tests.test_cards import PID

    pilot[1].state.store.put(
        "creative", PID, pilot[1].state.store.get("creative", project)
    )
    _, task = read_task(pilot, result=narration_result())
    assert task["creative"]["script"] == saved["creative"]["script"]
    assert "widgets" not in task["creative"]
    assert task["narration_continuation"]["creative_revision"] == 3


def test_story_save_does_not_replace_newer_agent_plan(pilot, project):
    shown = show(pilot, project, "story")
    updated = call(
        pilot,
        "plan_video",
        dict(
            project_id=project,
            revision=2,
            beats=[dict(title="New structure", visual="A network", seconds=10)],
        ),
    )
    assert "script" not in updated["creative"]
    # The old draft remains recoverable without being mislabeled as current.
    stored = pilot[1].state.store.get("creative", project)
    assert stored["widgets"]["story"]["beats"] == BEATS
    error(
        pilot,
        "save_video_widget",
        dict(
            project_id=project,
            widget_id=shown["widget"]["id"],
            revision=1,
            request_id="late-edit",
            beats=BEATS,
        ),
    )
    assert (
        pilot[1].state.store.get("creative", project)["beats"][0]["title"]
        == "New structure"
    )


def test_unchanged_story_and_empty_brief_are_not_approval(pilot, project):
    brief = show(pilot, project)
    empty = save(pilot, brief, answers={})
    assert not empty["saved"] and empty["creative"]["revision"] == 1
    story = show(pilot, project, "story")
    unchanged = save(pilot, story, beats=BEATS)
    assert not unchanged["saved"] and unchanged["creative"]["revision"] == 2
    assert unchanged["creative"]["plan_provenance"] == "assistant_plan"


@pytest.mark.parametrize("answers", [{"unasked": "kids"}, {"audience": "invented"}])
def test_only_offered_answers_are_accepted(pilot, project, answers):
    shown = show(pilot, project)
    error(
        pilot,
        "save_video_widget",
        dict(
            project_id=project,
            widget_id=shown["widget"]["id"],
            revision=1,
            request_id="bad",
            answers=answers,
        ),
    )


@pytest.mark.parametrize(
    "bad",
    [
        [],
        QUESTIONS * 2,
        [QUESTIONS[0], QUESTIONS[0]],
        [QUESTIONS[0] | {"recommended": "unoffered"}],
        [QUESTIONS[0] | {"options": [QUESTIONS[0]["options"][0]] * 2}],
    ],
)
def test_bad_question_sets_fail_before_writing(pilot, project, bad):
    before = pilot[1].state.store.get("creative", project)
    error(
        pilot,
        "show_video_brief",
        dict(project_id=project, creative_revision=1, questions=bad),
    )
    assert pilot[1].state.store.get("creative", project) == before


@pytest.mark.parametrize(
    "bad",
    [
        [],
        BEATS * 7,
        [BEATS[0], BEATS[0]],
        [BEATS[0] | {"seconds": -1}],
        [BEATS[0] | {"seconds": 601}],
        [BEATS[0] | {"narration": "x" * 2001}],
    ],
)
def test_story_bounds_fail_before_writing(pilot, project, bad):
    before = pilot[1].state.store.get("creative", project)
    error(
        pilot,
        "show_video_story",
        dict(project_id=project, creative_revision=1, beats=bad),
    )
    assert pilot[1].state.store.get("creative", project) == before


def test_widgets_require_owner_and_current_proposal_revision(pilot, project):
    error(
        pilot,
        "show_video_brief",
        dict(project_id=project, creative_revision=9, questions=QUESTIONS),
    )
    shown = show(pilot, project)
    pilot[1].state.store.project = Mock(side_effect=PermissionError("Not your project"))
    error(
        pilot,
        "save_video_widget",
        dict(
            project_id=project,
            widget_id=shown["widget"]["id"],
            revision=1,
            request_id="foreign",
            answers={"audience": "kids"},
        ),
    )


def test_failed_atomic_save_can_be_retried_without_double_revision(pilot, project):
    shown = show(pilot, project)
    store = pilot[1].state.store
    original = store.put

    def failed(kind, *args, **kwargs):
        if kind == "creative":
            raise ValueError("Database unavailable")
        return original(kind, *args, **kwargs)

    store.put = failed
    error(
        pilot,
        "save_video_widget",
        dict(
            project_id=project,
            widget_id=shown["widget"]["id"],
            revision=1,
            request_id="click-1",
            answers={"audience": "kids"},
        ),
    )
    store.put = original
    saved = save(pilot, shown, answers={"audience": "kids"})
    assert saved["creative"]["revision"] == 2
    assert save(pilot, shown, answers={"audience": "kids"})["creative"]["revision"] == 2


def test_simultaneous_style_and_brief_clicks_preserve_both(pilot, project, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    shown = show(pilot, project)
    call(pilot, "show_video_choices", {"project_id": project})
    app = pilot[1]
    monkeypatch.setattr(
        "video_use_mcp.pilot.server.get_access_token",
        lambda: SimpleNamespace(
            subject="tester", scopes=["video:read", "video:write"], client_id="test"
        ),
    )
    original_get = app.state.store.get

    def slow_read(kind, key, **kwargs):
        value = original_get(kind, key, **kwargs)
        if kind == "creative":
            time.sleep(
                0.02
            )  # competing read/modify/write paths overlap without the shared lock
        return value

    app.state.store.get = slow_read
    barrier = threading.Barrier(2)
    tools = app.state.mcp._tool_manager._tools

    def brief():
        barrier.wait()
        return tools["save_video_widget"].fn(
            project_id=project,
            widget_id=shown["widget"]["id"],
            revision=1,
            request_id="concurrent",
            answers={"audience": "kids"},
        )

    def style():
        barrier.wait()
        return tools["choose_video_style"].fn(
            project_id=project, choice="editorial", revision=1
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(brief), pool.submit(style)
        a.result(timeout=5)
        b.result(timeout=5)
    state = original_get("creative", project)
    assert state["revision"] == 3
    assert state["selected"] == "editorial"
    assert state["brief_answers"][0]["answer"] == "Children"
