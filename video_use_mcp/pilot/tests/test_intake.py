"""New requests require actual involvement and missing-basics answers only."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.intake import (
    initialize_intake,
    intake_context,
    pending_widget,
    apply_intake_answers,
)
from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_workflow import call as call_tool
from video_use_mcp.pilot.tests.test_widgets import QUESTIONS, BEATS, legacy_record

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def call(pilot, name, args):
    data = call_tool(pilot, name, args)
    # These tests also exercise backward-compatible app saves. Public native
    # question responses are asserted without this fixture in test_native_questions.
    if "widget" not in data and ("question" in data or "story" in data):
        return legacy_record(pilot, data, "story" if "story" in data else "brief")
    return data


def start(pilot, **kwargs):
    return call(
        pilot,
        "start_video",
        dict(title="Wi-Fi", brief="Explain Wi-Fi", category="explainer") | kwargs,
    )


def save(pilot, shown, answers=None, *, chat=None, **kwargs):
    args = dict(
        project_id=shown["project_id"],
        widget_id=shown["widget"]["id"],
        revision=shown["widget"]["revision"],
        request_id="answer-1",
    )
    if answers is not None:
        args["answers"] = answers
    if chat is not None:
        args["user_message"] = chat
    return call(
        pilot,
        "record_video_answers" if chat is not None else "save_video_widget",
        args | kwargs,
    )


def fail_save(pilot, shown, answers, **kwargs):
    args = dict(
        project_id=shown["project_id"],
        widget_id=shown["widget"]["id"],
        revision=shown["widget"]["revision"],
        request_id="bad-answer",
        answers=answers,
    )
    result = rpc(
        pilot, "tools/call", dict(name="save_video_widget", arguments=args | kwargs)
    )
    assert result["isError"], result
    return result


def basics(pilot, shown, mode="key_moments"):
    chosen = save(pilot, shown, {"involvement": mode})
    next_tool = chosen["intake"]["next_tool"]
    return call(pilot, next_tool["name"], next_tool["arguments"])


def ready(pilot, mode="hands_on"):
    shown = start(
        pilot, output_profile={"duration_seconds": 30, "viewing_destination": "YouTube"}
    )
    return save(pilot, shown, {"involvement": mode})


def test_fresh_request_asks_one_unselected_mode_even_with_explicit_basics(pilot):
    shown = start(
        pilot,
        output_profile={
            "duration_seconds": 25,
            "viewing_destination": "YouTube Shorts",
        },
    )
    assert shown["intake"]["phase"] == "mode"
    assert shown["intake"]["mode"] is None
    widget = shown["widget"]
    assert widget["required"] == ["involvement"]
    assert widget["answers"] == {}
    assert [q["id"] for q in widget["questions"]] == ["involvement"]
    assert [o["label"] for o in widget["questions"][0]["options"]] == [
        "Hands off",
        "Key moments",
        "Hands on",
    ]
    fail_save(pilot, shown, {})
    assert pilot[1].state.store.get("creative", shown["project_id"])["revision"] == 1
    chosen = save(pilot, shown, {"involvement": "delegate"})
    assert chosen["intake"]["phase"] == "production"
    assert chosen["intake"]["missing_basics"] == []
    assert chosen["intake"]["output_profile"] == {
        "duration_seconds": 25,
        "viewing_destination": "YouTube Shorts",
    }
    assert chosen["intake"]["source"] == "user_submit"
    assert (
        chosen["widget"]["id"] == widget["id"]
    )  # Save returns its receipt, never swaps pages.


def test_missing_basics_require_every_offered_answer_and_explicit_delegation(pilot):
    shown = basics(pilot, start(pilot))
    assert [q["id"] for q in shown["widget"]["questions"]] == [
        "duration",
        "viewing_destination",
    ]
    assert (
        shown["widget"]["questions"][1]["prompt"]
        == "Where will this video be most watched?"
    )
    fail_save(pilot, shown, {"duration": "30"})
    fail_save(pilot, shown, {})
    saved = save(
        pilot, shown, {"duration": "you_decide", "viewing_destination": "you_decide"}
    )
    assert saved["intake"]["phase"] == "production"
    assert saved["intake"]["output_profile"] == {}
    assert set(saved["intake"]["delegated_basics"]) == {
        "duration",
        "viewing_destination",
    }
    assert all(a["source"] == "user_submit" for a in saved["creative"]["brief_answers"])
    assert save(
        pilot, shown, {"duration": "you_decide", "viewing_destination": "you_decide"}
    )["repeated"]


def test_only_missing_field_asked_and_repeated_start_preserves_pending_widget(pilot):
    original = start(pilot, output_profile={"duration_seconds": 45})
    shown = basics(pilot, original)
    assert shown["widget"]["required"] == ["viewing_destination"]
    repeated = start(pilot, project_id=shown["project_id"])
    assert repeated["widget"]["id"] == shown["widget"]["id"]
    saved = save(pilot, repeated, {"viewing_destination": "vertical"})
    assert saved["intake"]["output_profile"] == {
        "duration_seconds": 45,
        "viewing_destination": "vertical",
    }
    assert saved["intake"]["phase"] == "production"


def test_profile_change_replaces_pending_basics_instead_of_overwriting_new_values(
    pilot,
):
    shown = basics(pilot, start(pilot))
    current = start(
        pilot, project_id=shown["project_id"], output_profile={"duration_seconds": 45}
    )
    assert current["widget"]["id"] != shown["widget"]["id"]
    assert current["widget"]["required"] == ["viewing_destination"]
    fail_save(pilot, shown, {"duration": "15", "viewing_destination": "vertical"})
    assert current["intake"]["output_profile"]["duration_seconds"] == 45


def test_exact_chat_basics_preserve_nonpreset_values_and_honest_provenance(pilot):
    shown = basics(pilot, start(pilot))
    saved = save(
        pilot,
        shown,
        chat="45 seconds and internal training",
        output_profile={
            "duration_seconds": 45,
            "viewing_destination": "internal training",
        },
    )
    assert saved["intake"]["phase"] == "production"
    assert saved["intake"]["output_profile"] == {
        "duration_seconds": 45,
        "viewing_destination": "internal training",
    }
    answers = {a["question_id"]: a for a in saved["creative"]["brief_answers"]}
    assert answers["duration"]["answer"] == "45 seconds"
    assert answers["viewing_destination"]["answer"] == "internal training"
    assert "option_id" not in answers["duration"]  # Never invent a button choice.
    assert answers["duration"]["source"] == "assistant_reported_user"
    assert (
        saved["creative"]["latest_widget_change"]["user_message"]
        == "45 seconds and internal training"
    )
    retry = save(
        pilot,
        shown,
        chat="45 seconds and internal training",
        output_profile={
            "duration_seconds": 45,
            "viewing_destination": "internal training",
        },
    )
    assert (
        retry["repeated"]
        and retry["creative"]["revision"] == saved["creative"]["revision"]
    )


def test_chat_mixed_preset_exact_value_and_unasked_or_conflicting_values(pilot):
    shown = basics(pilot, start(pilot))
    saved = save(
        pilot,
        shown,
        {"viewing_destination": "you_decide"},
        chat="45 seconds, you pick the format",
        output_profile={"duration_seconds": 45},
    )
    assert saved["intake"]["output_profile"] == {"duration_seconds": 45}
    assert saved["intake"]["delegated_basics"] == ["viewing_destination"]
    other = basics(pilot, start(pilot, output_profile={"duration_seconds": 30}))
    for profile, answers in [
        ({"duration_seconds": 45}, {"viewing_destination": "square"}),
        (
            {"viewing_destination": "internal training"},
            {"viewing_destination": "square"},
        ),
    ]:
        result = rpc(
            pilot,
            "tools/call",
            dict(
                name="record_video_answers",
                arguments=dict(
                    project_id=other["project_id"],
                    widget_id=other["widget"]["id"],
                    revision=other["widget"]["revision"],
                    request_id="invalid",
                    user_message="45 seconds",
                    output_profile=profile,
                    answers=answers,
                ),
            ),
        )
        assert result["isError"]


def test_changed_basics_snapshot_rejects_stale_form_without_overwriting(pilot):
    shown = basics(pilot, start(pilot))
    store, pid = pilot[1].state.store, shown["project_id"]
    state = initialize_intake(store.get("creative", pid), {"duration_seconds": 45})
    store.put("creative", pid, state)
    fail_save(pilot, shown, {"duration": "15", "viewing_destination": "vertical"})
    assert store.get("creative", pid)["intake"]["output_profile"] == {
        "duration_seconds": 45
    }


def test_preset_update_removes_old_exact_values_from_widget(pilot):
    shown = basics(pilot, start(pilot))
    saved = save(
        pilot,
        shown,
        chat="45 seconds for internal training",
        output_profile={
            "duration_seconds": 45,
            "viewing_destination": "internal training",
        },
    )
    updated = save(
        pilot,
        saved,
        {"duration": "60", "viewing_destination": "landscape"},
        request_id="answer-2",
    )
    assert "output_profile" not in updated["widget"]
    assert updated["intake"]["output_profile"] == {
        "duration_seconds": 60,
        "viewing_destination": "landscape",
    }
    assert {
        a["question_id"]: a["answer"] for a in updated["creative"]["brief_answers"]
    }["duration"] == "60 seconds"


def test_chat_mode_requires_message_and_offered_answer_and_records_source(pilot):
    shown = start(pilot)
    for message, answers in [
        ("", {"involvement": "delegate"}),
        ("Hands off", {}),
        ("Automatic", {"involvement": "automatic"}),
    ]:
        result = rpc(
            pilot,
            "tools/call",
            dict(
                name="record_video_answers",
                arguments=dict(
                    project_id=shown["project_id"],
                    widget_id=shown["widget"]["id"],
                    revision=1,
                    request_id="invalid",
                    user_message=message,
                    answers=answers,
                ),
            ),
        )
        assert result["isError"]
    saved = save(pilot, shown, {"involvement": "delegate"}, chat="Hands off")
    assert saved["intake"]["mode"] == "delegate"
    assert saved["intake"]["source"] == "assistant_reported_user"


def test_cannot_bypass_mode_or_basics_with_generic_questions_or_story(pilot):
    initial = start(pilot)
    for shown in [initial, save(pilot, initial, {"involvement": "key_moments"})]:
        for tool, args in [
            ("show_video_brief", {"questions": QUESTIONS}),
            ("show_video_story", {"beats": BEATS}),
        ]:
            result = rpc(
                pilot,
                "tools/call",
                dict(
                    name=tool,
                    arguments=dict(
                        project_id=shown["project_id"],
                        creative_revision=shown["creative"]["revision"],
                    )
                    | args,
                ),
            )
            assert result["isError"]


def test_hands_on_content_answers_do_not_skip_reference_direction(pilot):
    initial = ready(pilot)
    assert initial["intake"]["phase"] == "references"
    shown = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=initial["project_id"],
            creative_revision=initial["creative"]["revision"],
            questions=QUESTIONS,
        ),
    )
    assert shown["intake"]["phase"] == "personalization"
    fail_save(pilot, shown, {"audience": "kids"})
    saved = save(pilot, shown, {"audience": "kids", "tone": "warm"})
    assert saved["intake"]["phase"] == "references"
    assert "pending_questions" not in saved["creative"]["intake"]
    assert saved["intake"]["excerpt_review"]["status"] == "not_requested"


def test_key_moments_optional_brief_and_delegate_skips_optional_widgets(pilot):
    initial = ready(pilot, "key_moments")
    shown = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=initial["project_id"],
            creative_revision=initial["creative"]["revision"],
            questions=QUESTIONS,
        ),
    )
    assert not shown["widget"].get("required")
    assert save(pilot, shown, {"audience": "kids"})["intake"]["phase"] == "production"
    delegate = ready(pilot, "delegate")
    for name, values in [
        ("show_video_brief", {"questions": QUESTIONS}),
        ("show_video_story", {"beats": BEATS}),
    ]:
        result = rpc(
            pilot,
            "tools/call",
            dict(
                name=name,
                arguments=dict(
                    project_id=delegate["project_id"],
                    creative_revision=delegate["creative"]["revision"],
                )
                | values,
            ),
        )
        assert result["isError"]


def checkpoint(pilot):
    initial = ready(pilot)
    pid = initial["project_id"]
    state = deepcopy(pilot[1].state.store.get("creative", pid))
    state["intake"]["reference_direction"].update(status="accepted")
    widget = dict(
        id="review-widget",
        kind="brief",
        purpose="excerpt_review",
        revision=1,
        creative_revision=state["revision"],
        state="open",
        media_object_id="preview-1",
        required=["excerpt_review"],
        answers={},
        questions=[
            dict(
                id="excerpt_review",
                prompt="Use this direction for the rest?",
                options=[
                    dict(id="continue", label="Continue with this"),
                    dict(id="refine", label="Refine the sample"),
                ],
            )
        ],
    )
    state["widgets"] = {"brief": widget}
    state["intake"]["excerpt_review"] = dict(
        status="pending", object_id="preview-1", creative_revision=state["revision"]
    )
    pilot[1].state.store.put("creative", pid, state)
    pilot[1].state.store.put(
        "progress", pid, {"latest_preview": {"preview": {"object_id": "preview-1"}}}
    )
    return dict(project_id=pid, widget=widget, creative=state)


@pytest.mark.parametrize(
    "choice,phase,status",
    [
        ("continue", "production", "approved"),
        ("refine", "excerpt_review", "changes_requested"),
    ],
)
def test_excerpt_review_explicit_answer_preserves_binding_and_retry(
    pilot, choice, phase, status
):
    shown = checkpoint(pilot)
    fail_save(pilot, shown, {})
    saved = save(pilot, shown, {"excerpt_review": choice})
    assert saved["intake"]["phase"] == phase
    assert saved["intake"]["excerpt_review"] == dict(
        status=status,
        object_id="preview-1",
        creative_revision=saved["creative"]["revision"],
        source="user_submit",
    )
    assert save(pilot, shown, {"excerpt_review": choice})["repeated"]


@pytest.mark.parametrize("change", ["preview", "creative"])
def test_excerpt_review_cannot_approve_stale_media_or_changed_direction(pilot, change):
    shown = checkpoint(pilot)
    store, pid = pilot[1].state.store, shown["project_id"]
    if change == "preview":
        store.put(
            "progress", pid, {"latest_preview": {"preview": {"object_id": "preview-2"}}}
        )
    else:
        state = store.get("creative", pid)
        state["revision"] += 1
        state["preferences"] = "Change the palette"
        store.put("creative", pid, state)
    fail_save(pilot, shown, {"excerpt_review": "continue"})
    assert store.get("creative", pid)["intake"]["excerpt_review"]["status"] == "pending"


def test_helpers_preserve_legacy_and_involvement_change_releases_obsolete_questions():
    for state in [None, Mock(), {}, {"intake": {"version": 2}}]:
        assert intake_context(state) is None
    state = initialize_intake({"revision": 1}, {"duration_seconds": 45})
    state["intake"] = apply_intake_answers(
        state["intake"], "mode", {"involvement": "hands_on"}, "user_submit"
    )
    state["intake"].update(
        pending_questions={"widget_id": "old", "answered": False},
        pending_style={"revision": 1},
    )
    state["intake"] = apply_intake_answers(
        state["intake"], "mode", {"involvement": "delegate"}, "user_submit"
    )
    assert (
        "pending_questions" not in state["intake"]
        and "pending_style" not in state["intake"]
    )
    newer = initialize_intake(state, {"viewing_destination": "internal training"})
    assert state["intake"]["output_profile"] == {"duration_seconds": 45}
    assert newer["intake"]["mode"] == "delegate"
    assert intake_context(newer)["phase"] == "production"
    assert pending_widget(newer) is None


@pytest.mark.parametrize(
    "profile",
    [
        {"duration_seconds": True},
        {"duration_seconds": -1},
        {"duration_seconds": float("inf")},
        {"viewing_destination": " "},
        {"unknown": "x"},
        [],
    ],
)
def test_invalid_output_profile_rejected(profile):
    with pytest.raises(ValueError):
        initialize_intake({"revision": 1}, profile)
