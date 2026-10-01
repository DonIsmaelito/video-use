"""Forward interaction cases use real intake transitions without running media."""

from copy import deepcopy

import pytest

from video_use_mcp.pilot.experience import experience_context, involvement_preference
from video_use_mcp.pilot.intake import apply_intake_answers, initialize_intake


def new_request(profile=None):
    return initialize_intake({"revision": 1}, profile)


def answer(state, purpose, answers):
    updated = deepcopy(state)
    updated["intake"] = apply_intake_answers(
        state["intake"], purpose, answers, "user_submit"
    )
    updated["revision"] += 1
    return updated


def ready_request(mode):
    state = new_request({"duration_seconds": 30, "viewing_destination": "web"})
    return answer(state, "mode", {"involvement": mode})


def test_mode_is_first_even_with_all_basics_or_a_legacy_default_available():
    state = new_request({"duration_seconds": 30, "viewing_destination": "web"})
    state["brief_answers"] = [
        {"question_id": "involvement", "option_id": "delegate", "source": "default"}
    ]
    before = deepcopy(state)
    result = experience_context(state, event="start")
    assert involvement_preference(state) == (None, "awaiting_user")
    assert result["intake"]["phase"] == "mode"
    assert result["check_in"]["question"] == "required_mode_choice"
    assert result["check_in"]["continuation"] == "wait_for_mode_choice"
    assert result["check_in"]["widgets"] == []
    assert (
        result["check_in"]["presentation"]
        == "host_native_question_if_available_else_short_chat"
    )
    assert state == before
    assert (
        experience_context(state, event="project")["repeat_key"] == result["repeat_key"]
    )


def test_basics_follow_mode_and_ask_only_for_missing_output_information():
    state = new_request({"duration_seconds": 25})
    state = answer(state, "mode", {"involvement": "hands_on"})
    result = experience_context(state, event="start")
    assert result["check_in"]["question"] == "missing_output_basics_only"
    assert result["check_in"]["missing_basics"] == ["viewing_destination"]
    assert [q["id"] for q in result["intake"]["questions"]] == ["viewing_destination"]
    assert result["check_in"]["blocking_scope"] == "dependent_production"
    assert "show_video_choices" not in result["check_in"]["widgets"]


def test_hands_off_forward_flow_requires_basics_then_stays_quiet_until_final():
    state = answer(new_request(), "mode", {"involvement": "delegate"})
    assert experience_context(state)["intake"]["phase"] == "basics"
    state = answer(
        state, "basics", {"duration": "you_decide", "viewing_destination": "vertical"}
    )
    started = experience_context(state, event="start")
    assert started["intake"]["phase"] == "production"
    assert started["check_in"]["update"] == "none"
    assert started["check_in"]["widgets"] == []
    for media in (None, {"object_id": "draft", "media_type": "video/mp4"}):
        step = experience_context(state, task={"status": "succeeded"}, media=media)
        assert step["check_in"]["update"] == "none"
        assert step["check_in"]["question"] == "none"
        assert step["check_in"]["widgets"] == []
    delivered = experience_context(state, media={"object_id": "final", "final": True})
    assert delivered["check_in"]["continuation"] == "deliver_requested_result"
    assert delivered["check_in"]["widgets"] == ["show_video_preview"]


def test_key_moments_retains_selective_nonblocking_draft_updates():
    state = ready_request("key_moments")
    result = experience_context(state, media={"object_id": "draft"})
    assert result["check_in"]["question"] == "optional_if_consequential"
    assert result["check_in"]["blocking_scope"] == "none"
    assert result["check_in"]["continuation"] == "continue_authorized_work"


@pytest.mark.parametrize(
    "pending",
    [
        {"pending_questions": {"answered": False}},
        {"pending_style": {"widget_id": "style"}},
    ],
)
def test_offered_hands_on_questions_wait_before_dependent_work(pending):
    state = ready_request("hands_on")
    state["intake"].update(pending)
    result = experience_context(state, event="start")
    assert result["check_in"]["trigger"] == "early_decision_pending"
    assert result["check_in"]["continuation"] == "continue_cheap_independent_work"
    assert result["check_in"]["blocking_scope"] == "dependent_production"
    assert result["check_in"]["question"] == "await_offered_content_or_style_answer"


def test_hands_on_context_then_excerpt_review_then_remaining_production():
    state = ready_request("hands_on")
    early = experience_context(state, event="start")
    assert early["check_in"]["trigger"] == "representative_excerpt_needed"
    assert "If the topic is unfamiliar" in early["check_in"]["hint"]
    assert "tailored content questions" in early["check_in"]["hint"]
    assert early["check_in"]["widgets"] == [], "No invented visual exists yet"
    state["intake"]["excerpt_review"] = {"status": "pending", "object_id": "snippet"}
    before = deepcopy(state)
    shown = experience_context(state, media={"object_id": "snippet"})
    assert shown["check_in"]["question"] == "review_representative_excerpt"
    assert shown["check_in"]["continuation"] == "wait_for_excerpt_feedback"
    assert shown["check_in"]["blocking_scope"] == "remaining_production"
    assert state == before, "Reading progress does not mark a snippet approved"
    state["intake"]["excerpt_review"]["status"] = "changes_requested"
    revision = experience_context(state, handoff={"preferences_changed": True})
    assert revision["check_in"]["continuation"] == "revise_representative_excerpt"
    assert revision["check_in"]["question"] == "none"
    state["intake"]["excerpt_review"].update(status="approved", source="user_submit")
    final = experience_context(state, media={"object_id": "finished", "final": True})
    assert final["intake"]["phase"] == "production"
    assert final["check_in"]["continuation"] == "deliver_requested_result"


def test_an_existing_final_asset_does_not_invent_missing_hands_on_approval():
    state = ready_request("hands_on")
    state["intake"]["excerpt_review"] = {"status": "pending", "object_id": "snippet"}
    result = experience_context(state, media={"object_id": "later-cut", "final": True})
    assert result["check_in"]["continuation"] == "wait_for_excerpt_feedback"


def test_real_blocker_still_surfaces_in_hands_off_mode_without_forcing_style():
    result = experience_context(
        ready_request("delegate"),
        blocker={"kind": "service_allowance", "automatic_retry": False},
    )["check_in"]
    assert result["question"] == "only_if_needed_to_unblock"
    assert result["blocking_scope"] == "affected_component"
    assert result["widgets"] == []
