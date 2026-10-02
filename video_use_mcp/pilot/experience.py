"""Compact conversation opportunities derived from saved choices and real outcomes.

This describes the conversation around persisted intake and actual production.
Reads do not invent answers or mark an update delivered: only the host knows what
it said. Required intake decisions are distinct from routine tool approvals.
"""

from .intake import intake_context

MODES = {"hands_on", "key_moments", "delegate"}
DEFECT_KINDS = {"correctness", "meaning", "layout", "audio"}


def involvement_preference(creative):
    """Version-1 requests await a choice; only legacy requests get a default."""
    intake = intake_context(creative)
    if intake is not None:
        return intake["mode"], intake["source"]
    for answer in reversed((creative or {}).get("brief_answers", [])):
        if (
            answer.get("question_id") == "involvement"
            and answer.get("option_id") in MODES
            and answer.get("source") == "user_submit"
        ):
            return answer["option_id"], "user_submit"
    return "key_moments", "default"


def experience_context(
    creative,
    *,
    event="task",
    task=None,
    media=None,
    handoff=None,
    blocker=None,
    findings=None,
):
    """Describe the next interaction without inventing uncertainty or approval.

    Pass the public task result after its real media/blocker fields are assembled.
    Version-1 mode/output setup and requested hands-on decisions precede dependent
    production. Legacy requests retain their defaults. Repeat keys are scoped to
    the containing project/conversation,
    not delivery receipts. The assistant authors all actual questions and copy.
    """
    creative, task = creative or {}, task or {}
    result = task.get("result") or {}
    media = media if media is not None else task.get("media")
    handoff = handoff if handoff is not None else task.get("creative_handoff")
    blocker = blocker if blocker is not None else task.get("blocker")
    findings = findings if findings is not None else task.get("review_findings", [])
    intake = intake_context(creative)
    mode, source = (
        (intake["mode"], intake["source"])
        if intake is not None
        else involvement_preference(creative)
    )
    revision = creative.get("revision", 0)
    awaiting_excerpt = bool(
        intake and mode == "hands_on" and intake["phase"] == "excerpt_review"
    )
    key = f"{event}:{task.get('id', '')}:{task.get('status', '')}:creative:{revision}"
    check = dict(
        trigger="context_available",
        update="none",
        question="none",
        widgets=[],
        continuation="continue_authorized_work",
        blocking_scope="none",
    )
    defects = sorted(
        {
            finding["kind"]
            for finding in findings or []
            if finding.get("kind") in DEFECT_KINDS
            and not finding.get("resolved", False)
        }
    )
    if task.get("status") == "cancelled":
        check.update(
            trigger="task_cancelled",
            update="brief",
            continuation="respect_cancellation",
            hint="Respect the cancellation and the current user request. Do not automatically restart cancelled work.",
        )
    elif blocker:
        check.update(
            trigger="reported_blocker",
            update="brief",
            question="only_if_needed_to_unblock",
            continuation="continue_independent_work",
            blocking_scope="affected_component",
            blocker_kind=blocker.get("kind", "reported"),
            hint="Explain the actual blocker. Continue compatible authorized work. Ask only for genuinely missing input or authorization for a new commitment; do not quietly omit a requested component.",
        )
        if "automatic_retry" in blocker:
            check["automatic_retry"] = blocker["automatic_retry"]
    elif task.get("status") == "failed" or result.get("exit_code"):
        check.update(
            trigger="task_failed",
            update="none" if mode == "delegate" else "brief",
            question="only_if_needed_to_unblock",
            continuation="repair_failed_work",
            hint="Describe the actual outcome plainly. Repair ordinary execution failures within the request; do not turn routine recovery into an approval stage or poll a finished task.",
        )
        if mode == "delegate":
            check["hint"] = (
                "Repair ordinary execution failures internally and continue the requested work. Surface an error only when it becomes a genuine blocker needing user input; do not poll a finished task."
            )
    elif intake and intake["phase"] in {
        "mode",
        "basics",
        "approach",
        "personalization",
        "references",
    }:
        phase = intake["phase"]
        key = f"intake:{phase}:creative:{revision}"
        check.update(
            trigger={
                "mode": "involvement_required",
                "basics": "output_basics_required",
                "approach": "creation_approach_required",
                "personalization": "early_decision_pending",
                "references": "reference_direction_needed",
            }[phase],
            update="brief",
            question={
                "mode": "required_mode_choice",
                "basics": "missing_output_basics_only",
                "approach": "choose_video_creation_approach",
                "personalization": "await_offered_content_or_style_answer",
                "references": "choose_or_refine_visual_references",
            }[phase],
            continuation="continue_cheap_independent_work",
            blocking_scope="dependent_production",
            hint=intake["next_action"],
        )
        if intake.get("next_tool"):
            check["next_tool"] = intake["next_tool"]
        if phase == "mode":
            check["continuation"] = "wait_for_mode_choice"
        elif phase == "basics":
            check["missing_basics"] = intake.get("missing_basics", [])
        check["presentation"] = "host_native_question_if_available_else_short_chat"
        if phase == "references":
            check["continuation"] = "research_and_align_references"
    elif (
        handoff and handoff.get("preferences_changed") is True and not awaiting_excerpt
    ):
        check.update(
            trigger="saved_preferences_changed",
            update="brief",
            hint="Acknowledge the saved change and apply it to the next affected edit. Preserve compatible work; do not ask the user to approve their own submitted preference again.",
        )
    elif task.get("status") in ("queued", "running"):
        check.update(
            trigger="task_in_progress",
            update="only_if_meaningful" if mode == "hands_on" else "none",
            continuation="follow_existing_task",
            hint="Keep the existing task. Do not invent visual progress, resubmit it, or create a question just to fill the wait.",
        )
    elif defects:
        check.update(
            trigger="reported_review_findings",
            update="none" if mode == "delegate" else "brief",
            continuation="correct_reported_defects",
            blocking_scope="affected_delivery",
            reported_defect_kinds=defects,
            hint="Use the recorded findings and actual review evidence. Correct ordinary defects within the authorized edit; ask about genuine creative tradeoffs only. These are reported findings, not automatic factual verification.",
        )
        if mode == "delegate":
            check["hint"] = (
                "Correct the reported defects internally using actual review evidence. These findings are not automatic factual verification. Ask only if a genuine blocker prevents the requested result; do not introduce an optional style decision."
            )
    elif (
        (
            task.get("status") == "succeeded"
            and task.get("operation") == "export"
            and result.get("video_id")
        )
        or (media and media.get("final") and media.get("object_id"))
    ) and not awaiting_excerpt:
        check.update(
            trigger="finished_video_available",
            update="brief",
            widgets=["show_video_preview"],
            continuation="deliver_requested_result",
            hint="Deliver the playable video and download. Reuse the existing player or open it if needed. Do not request another routine approval or claim review you did not perform.",
        )
    elif awaiting_excerpt:
        review = intake.get("excerpt_review") or {}
        status = review.get("status", "not_requested")
        key = f"intake:excerpt_review:{status}:{review.get('object_id', '')}:creative:{revision}"
        check.update(
            trigger="representative_excerpt_needed",
            update="brief" if event == "start" else "none",
            question="tailored_content_if_unresolved",
            continuation="develop_representative_excerpt",
            blocking_scope="remaining_production",
            hint="Use the saved reference direction and user feedback to make one short representative snippet: carry through the chosen composition, typography, palette and pacing rather than reverting to a generic template. Resolve consequential content uncertainties using available sources and short conversation, without repeating known answers. Show the excerpt for review before building the rest.",
        )
        if status == "changes_requested":
            check.update(
                trigger="excerpt_changes_requested",
                question="none",
                continuation="revise_representative_excerpt",
                hint="Apply the user's requested changes to the representative snippet. Preserve compatible work and show the revised snippet for review before remaining production. Do not treat requested changes as approval or repeat already answered content questions.",
            )
        elif status == "pending" or (media and media.get("object_id")):
            check.update(
                trigger="excerpt_review_pending",
                update="brief",
                question="review_representative_excerpt",
                widgets=["show_video_preview"],
                continuation="wait_for_excerpt_feedback",
                hint="Use the existing snippet player, opening it only if missing. Ask for the requested early review and wait before making the rest of the video. Cheap independent work can continue, but an unanswered review is not approval. Show actual media only; do not substitute an inspection sheet or a status card.",
            )
    elif media and media.get("object_id"):
        key = f"media:{media['object_id']}:creative:{revision}"
        check.update(
            trigger="media_available",
            update="none" if mode == "delegate" else "brief",
            question="optional_if_consequential" if mode != "delegate" else "none",
            widgets=[] if mode == "delegate" else ["show_video_preview"],
            hint="Show or refresh this real media once in the conversation with a short update. Invite useful redirection where a consequential choice remains; keep working without requiring a reply.",
        )
        if mode == "delegate":
            check["hint"] = (
                "Keep this intermediate media and its inspection internal. Continue the authorized edit without optional questions or preview updates; show the finished video and download when ready."
            )
    elif event == "start":
        check.update(
            trigger="request_started",
            update="none" if mode == "delegate" else "brief",
            question="optional_if_consequential" if mode != "delegate" else "none",
            widgets=[],
            hint="Discuss at most one consequential unresolved choice in normal conversation, using a native question tool only if the host exposes one. Do not show a custom questionnaire, script editor or checklist of cards. Continue authorized work with reversible defaults; defaults are not user approval.",
        )
        if mode == "delegate":
            check["hint"] = (
                "Make creative decisions within the saved request and complete production. Do not show optional questions, story cards, draft previews or routine updates. Surface a genuine blocker when user input is needed, and deliver the final playable video and download."
            )
    elif task.get("status") == "succeeded":
        check.update(
            trigger="task_completed",
            update="only_if_meaningful" if mode == "hands_on" else "none",
            question="optional_if_consequential" if mode == "hands_on" else "none",
            hint="Continue from the real result. A meaningful new design decision can merit a short update or optional question; a tool completing alone does not require either.",
        )
    response = dict(mode=mode, source=source, repeat_key=key, check_in=check)
    if intake is not None:
        response["intake"] = intake
    return response
