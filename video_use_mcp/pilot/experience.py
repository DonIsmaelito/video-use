"""Compact conversation opportunities derived from saved choices and real outcomes.

This is guidance for the host assistant, not an execution or approval gate. Reads
do not mark a conversation update as delivered: only the host knows what it said.
"""

MODES = {"hands_on", "key_moments", "delegate"}
DEFECT_KINDS = {"correctness", "meaning", "layout", "audio"}


def involvement_preference(creative):
    """Only a persisted explicit submission establishes the user's chosen mode."""
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
    """Suggest a useful check-in without inventing uncertainty or user approval.

    Pass the public task result after its real media/blocker fields are assembled.
    ``event='start'`` offers optional direction; ``event='project'`` is a quiet
    context read. Repeat keys are scoped to the containing project/conversation,
    not delivery receipts. The assistant authors all actual questions and copy.
    """
    creative, task = creative or {}, task or {}
    result = task.get("result") or {}
    media = media if media is not None else task.get("media")
    handoff = handoff if handoff is not None else task.get("creative_handoff")
    blocker = blocker if blocker is not None else task.get("blocker")
    findings = findings if findings is not None else task.get("review_findings", [])
    mode, source = involvement_preference(creative)
    revision = creative.get("revision", 0)
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
            update="brief",
            question="only_if_needed_to_unblock",
            continuation="repair_failed_work",
            hint="Describe the actual outcome plainly. Repair ordinary execution failures within the request; do not turn routine recovery into an approval stage or poll a finished task.",
        )
    elif handoff and handoff.get("preferences_changed") is True:
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
            update="brief",
            continuation="correct_reported_defects",
            blocking_scope="affected_delivery",
            reported_defect_kinds=defects,
            hint="Use the recorded findings and actual review evidence. Correct ordinary defects within the authorized edit; ask about genuine creative tradeoffs only. These are reported findings, not automatic factual verification.",
        )
    elif (
        task.get("status") == "succeeded"
        and task.get("operation") == "export"
        and result.get("video_id")
    ) or (media and media.get("final") and media.get("object_id")):
        check.update(
            trigger="finished_video_available",
            update="brief",
            widgets=["show_video_preview"],
            continuation="deliver_requested_result",
            hint="Deliver the playable video and download. Reuse the existing player or open it if needed. Do not request another routine approval or claim review you did not perform.",
        )
    elif media and media.get("object_id"):
        key = f"media:{media['object_id']}:creative:{revision}"
        check.update(
            trigger="media_available",
            update="brief",
            question="optional_if_consequential" if mode != "delegate" else "none",
            widgets=["show_video_preview"],
            hint="Show or refresh this real media once in the conversation with a short update. Invite useful redirection where a consequential choice remains; keep working without requiring a reply.",
        )
    elif event == "start":
        check.update(
            trigger="request_started",
            update="brief",
            question="optional_if_consequential"
            if mode != "delegate"
            else "only_if_required",
            widgets=["show_video_brief", "show_video_choices", "show_video_story"]
            if mode != "delegate"
            else [],
            hint="State consequential assumptions briefly. Choose at most one useful steering surface for an unresolved decision; author it for this request, not a questionnaire ritual. Continue authorized work with reversible defaults; defaults are not user approval.",
        )
    elif task.get("status") == "succeeded":
        check.update(
            trigger="task_completed",
            update="only_if_meaningful" if mode == "hands_on" else "none",
            question="optional_if_consequential" if mode == "hands_on" else "none",
            hint="Continue from the real result. A meaningful new design decision can merit a short update or optional question; a tool completing alone does not require either.",
        )
    return dict(mode=mode, source=source, repeat_key=key, check_in=check)
