"""Conversation guidance follows evidence without becoming an approval gate."""

from copy import deepcopy

import pytest

from video_use_mcp.pilot.experience import experience_context, involvement_preference


def creative(mode=None):
    return dict(
        revision=3,
        brief_answers=[]
        if mode is None
        else [dict(question_id="involvement", option_id=mode, source="user_submit")],
    )


def task(**changes):
    return dict(id="task-1", operation="step", status="succeeded", result={}) | changes


@pytest.mark.parametrize("mode", ["hands_on", "key_moments", "delegate"])
def test_explicit_involvement_is_preserved_without_creating_an_approval_gate(mode):
    response = experience_context(creative(mode), event="start")
    assert (response["mode"], response["source"]) == (mode, "user_submit")
    check = response["check_in"]
    assert check["blocking_scope"] == "none"
    assert check["continuation"] == "continue_authorized_work"
    assert "defaults are not user approval" in check["hint"]
    assert "Choose at most one" in check["hint"]


@pytest.mark.parametrize(
    "answer",
    [
        dict(question_id="involvement", option_id="delegate", source="default"),
        dict(question_id="involvement", option_id="delegate", source="assistant_plan"),
        dict(question_id="involvement", option_id="invented", source="user_submit"),
        dict(question_id="tone", option_id="delegate", source="user_submit"),
    ],
)
def test_default_and_untrusted_mode_are_not_mislabeled_as_user_preference(answer):
    state = creative()
    state["brief_answers"] = [answer]
    state["preferences"] = "The assistant might delegate this"
    assert involvement_preference(state) == ("key_moments", "default")


def test_reads_do_not_mutate_state_or_claim_update_delivery():
    state, completed = creative("hands_on"), task()
    completed["media"] = dict(object_id="clip-1", media_type="video/mp4")
    before = deepcopy((state, completed))
    first = experience_context(state, task=completed)
    repeated = experience_context(state, task=completed)
    assert (state, completed) == before
    assert first == repeated
    assert first["repeat_key"] == "media:clip-1:creative:3"
    assert first["check_in"]["trigger"] == "media_available"
    assert "once in the conversation" in first["check_in"]["hint"]
    assert (
        experience_context(state, task=completed, media={"object_id": "clip-2"})[
            "repeat_key"
        ]
        != first["repeat_key"]
    )


def test_delegation_still_acknowledges_new_explicit_direction():
    response = experience_context(
        creative("delegate"), task=task(), handoff={"preferences_changed": True}
    )
    check = response["check_in"]
    assert check["trigger"] == "saved_preferences_changed"
    assert check["update"] == "brief"
    assert check["question"] == "none"
    assert check["continuation"] == "continue_authorized_work"


def test_quota_blocks_only_affected_component_and_does_not_expand_spending():
    response = experience_context(
        creative("delegate"),
        task=task(
            operation="narrate",
            status="failed",
            blocker=dict(kind="service_allowance", automatic_retry=False),
        ),
    )
    check = response["check_in"]
    assert check["trigger"] == "reported_blocker"
    assert check["blocking_scope"] == "affected_component"
    assert check["continuation"] == "continue_independent_work"
    assert check["automatic_retry"] is False
    assert check["question"] == "only_if_needed_to_unblock"
    assert "do not quietly omit" in check["hint"]


def test_ordinary_failed_render_guides_repair_without_permission_ritual():
    check = experience_context(
        creative("hands_on"), task=task(status="failed", result={"exit_code": 1})
    )["check_in"]
    assert check["continuation"] == "repair_failed_work"
    assert check["blocking_scope"] == "none"
    assert check["widgets"] == []


def test_cancelled_work_is_not_automatically_restarted():
    check = experience_context(creative(), task=task(status="cancelled"))["check_in"]
    assert check["continuation"] == "respect_cancellation"


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_failure_or_cancellation_takes_precedence_over_changed_preferences(status):
    check = experience_context(
        creative("hands_on"),
        task=task(status=status),
        handoff={"preferences_changed": True},
    )["check_in"]
    assert check["trigger"] == f"task_{status}"
    assert check["continuation"] != "continue_authorized_work"
    if status == "cancelled":
        check = experience_context(
            creative(),
            task=task(status=status),
            blocker={"kind": "service_allowance", "automatic_retry": False},
        )["check_in"]
        assert check["continuation"] == "respect_cancellation"


def test_legacy_task_with_no_creative_context_uses_honest_default():
    response = experience_context(None, task=task())
    assert (response["mode"], response["source"]) == ("key_moments", "default")
    assert response["check_in"]["blocking_scope"] == "none"


def test_pending_task_does_not_invent_questions_or_progress_media():
    for mode in ("hands_on", "key_moments", "delegate"):
        check = experience_context(creative(mode), task=task(status="running"))[
            "check_in"
        ]
        assert check["continuation"] == "follow_existing_task"
        assert check["question"] == "none"
        assert check["widgets"] == []
    pending = experience_context(creative("hands_on"), task=task(status="running"))
    completed = experience_context(creative("hands_on"), task=task())
    assert pending["repeat_key"] != completed["repeat_key"]


def test_reported_defects_are_distinct_from_optional_style_and_resolved_issues():
    findings = [
        dict(kind="style", description="Try purple", resolved=False),
        dict(kind="audio", description="Clipped ending", resolved=True),
    ]
    check = experience_context(creative(), task=task(), findings=findings)["check_in"]
    assert check["blocking_scope"] == "none"
    findings.append(
        dict(kind="meaning", description="Reversed direction", resolved=False)
    )
    check = experience_context(creative(), task=task(), findings=findings)["check_in"]
    assert check["reported_defect_kinds"] == ["meaning"]
    assert check["continuation"] == "correct_reported_defects"
    assert "not automatic factual verification" in check["hint"]


def test_actual_final_video_is_delivered_without_asking_for_another_approval():
    check = experience_context(
        creative("hands_on"),
        task=task(operation="export", result={"video_id": "finished"}),
    )["check_in"]
    assert check["trigger"] == "finished_video_available"
    assert check["question"] == "none"
    assert check["continuation"] == "deliver_requested_result"
    assert check["blocking_scope"] == "none"


def test_missing_artifact_does_not_become_a_playable_finished_video():
    check = experience_context(creative(), task=task(operation="export"))["check_in"]
    assert check["trigger"] == "task_completed"
    assert check["widgets"] == []


def test_involvement_changes_cadence_not_routine_authorization():
    for mode, update in [
        ("hands_on", "only_if_meaningful"),
        ("key_moments", "none"),
        ("delegate", "none"),
    ]:
        check = experience_context(creative(mode), task=task(operation="narrate"))[
            "check_in"
        ]
        assert check["update"] == update
        assert check["blocking_scope"] == "none"
        assert check["continuation"] == "continue_authorized_work"
    assert (
        experience_context(creative(), event="project")["check_in"]["update"] == "none"
    )
