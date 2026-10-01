"""Versioned request intake; explicit answers, not recommendations, advance it."""

from copy import deepcopy
import math

from .store import ident

MODES = {"delegate", "key_moments", "hands_on"}
INVOLVEMENT_QUESTION = dict(
    id="involvement",
    prompt="How involved would you like to be?",
    options=[
        dict(id="delegate", label="Hands off"),
        dict(id="key_moments", label="Key moments"),
        dict(id="hands_on", label="Hands on"),
    ],
    recommended="key_moments",
)
BASIC_QUESTIONS = {
    "duration": dict(
        id="duration",
        prompt="How long should it be?",
        recommended="",
        options=[
            dict(id="15", label="15 seconds"),
            dict(id="30", label="30 seconds"),
            dict(id="60", label="60 seconds"),
            dict(id="you_decide", label="You decide"),
        ],
    ),
    "viewing_destination": dict(
        id="viewing_destination",
        prompt="Where will this video be most watched?",
        recommended="",
        options=[
            dict(id="landscape", label="Landscape · web or YouTube"),
            dict(id="vertical", label="Vertical · Reels or TikTok"),
            dict(id="square", label="Square · social feed"),
            dict(id="you_decide", label="You decide"),
        ],
    ),
}


def initialize_intake(state, output_profile=None):
    """Return copied state; supplied basics are assistant-reported user values."""
    state = deepcopy(state)
    intake = state.get("intake")
    if not isinstance(intake, dict) or intake.get("version") != 1:
        intake = dict(
            version=1,
            mode=None,
            output_profile={},
            delegated_basics=[],
            provenance={},
            excerpt_review={"status": "not_requested"},
        )
        state["intake"] = intake
    profile = {} if output_profile is None else output_profile
    if not isinstance(profile, dict) or set(profile) - {
        "duration_seconds",
        "viewing_destination",
    }:
        raise ValueError(
            "Output profile accepts duration_seconds and viewing_destination"
        )
    for field, value in profile.items():
        if value is None:
            continue
        if field == "duration_seconds":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 < value <= 7200
            ):
                raise ValueError(
                    "Duration must be a positive number of seconds up to 7200"
                )
            question = "duration"
        else:
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise ValueError("Viewing destination must be 1–120 characters")
            value, question = value.strip(), "viewing_destination"
        intake["output_profile"][field] = value
        intake["provenance"][question] = "assistant_reported_user"
        intake["delegated_basics"] = [
            q for q in intake["delegated_basics"] if q != question
        ]
    return state


def intake_context(state, project_id=None):
    if not isinstance(state, dict):
        return None
    intake = state.get("intake")
    if not isinstance(intake, dict) or intake.get("version") != 1:
        return None
    profile, delegated = (
        intake.get("output_profile", {}),
        intake.get("delegated_basics", []),
    )
    missing = [
        q
        for q, field in (
            ("duration", "duration_seconds"),
            ("viewing_destination", "viewing_destination"),
        )
        if profile.get(field) is None and q not in delegated
    ]
    mode = intake.get("mode")
    review = intake.get("excerpt_review", {"status": "not_requested"})
    pending_questions, pending_style = (
        intake.get("pending_questions"),
        intake.get("pending_style"),
    )
    if mode not in MODES:
        phase = "mode"
        questions = [deepcopy(INVOLVEMENT_QUESTION)]
        action = "Ask this one involvement question first and wait for an explicit answer. A recommendation or silence is not a choice. Do not begin production yet."
    elif missing:
        phase = "basics"
        questions = [deepcopy(BASIC_QUESTIONS[q]) for q in missing]
        action = "Ask only these missing output basics and wait for explicit answers; You decide is valid delegation. Do not repeat known values or begin production yet."
    elif (pending_questions and not pending_questions.get("answered")) or pending_style:
        phase, questions = "personalization", []
        action = "The hands-on user has an unanswered content or style choice. Wait for that explicit answer before dependent production; do not invent a selection."
    elif mode == "hands_on" and review.get("status") != "approved":
        phase, questions = "excerpt_review", []
        if review.get("status") == "pending":
            action = "The short excerpt is awaiting the user's explicit Continue or Refine answer. Wait before producing the complete video; a recommendation or silence is not acceptance."
        elif review.get("status") == "changes_requested":
            action = "The user asked to refine the sample. Use feedback already supplied; if none says what should change, ask one focused content or style refinement question before revising. Do not invent a change. Show the revised short excerpt for explicit review before completing the video."
        else:
            action = "Use the user's content and style direction to make one short excerpt. Show it for explicit review before producing the complete video. Ask topic/content questions only where needed; do not repeat supplied context."
    else:
        phase, questions = "production", []
        action = (
            "The user delegated execution. Proceed to the finished video without intermediate previews or routine approval questions."
            if mode == "delegate"
            else "Continue authorized production; show selective meaningful updates without routine approval stops."
            if mode == "key_moments"
            else "The excerpt was explicitly approved. Continue to the finished video, preserving the reviewed direction."
        )
    context = dict(
        version=1,
        phase=phase,
        mode=mode if mode in MODES else None,
        source=intake.get("provenance", {}).get("mode", "awaiting_user"),
        output_profile=deepcopy(profile),
        delegated_basics=list(delegated),
        missing_basics=missing,
        missing_basic_questions=[deepcopy(BASIC_QUESTIONS[q]) for q in missing],
        excerpt_review=deepcopy(review),
        next_action=action,
    )
    if pending_questions:
        context["pending_questions"] = deepcopy(pending_questions)
    if pending_style:
        context["pending_style"] = deepcopy(pending_style)
    if questions:
        context["questions"] = questions
        if project_id:
            existing = state.get("widgets", {}).get("brief") or {}
            if (
                existing.get("purpose") == phase
                and existing.get("questions") == questions
                and (
                    phase != "basics"
                    or existing.get("intake_snapshot") == basics_snapshot(intake)
                )
            ):
                context["question"] = question_context(project_id, existing)
                context["next_action"] += (
                    " Present the supplied question once through the host; do not call show_video_brief to display it again."
                )
            else:
                context["next_tool"] = dict(
                    name="show_video_brief",
                    arguments=dict(
                        project_id=project_id,
                        creative_revision=state["revision"],
                        questions=questions,
                        title="Make it yours" if phase == "mode" else "The basics",
                    ),
                )
    elif project_id and pending_questions:
        existing = state.get("widgets", {}).get("brief") or {}
        if existing.get("id") == pending_questions.get("widget_id"):
            context["question"] = question_context(project_id, existing)
            context["next_action"] += (
                " Reuse this existing question; do not replace it just to display it again."
            )
    return context


def question_context(project_id, record, *, answered=False):
    """Host-authored conversation, with a stable identity for deduplication.

    This is model context, not an embedded app or a claim that the host exposes
    native question controls. The host remains the only presenter.
    """
    data = dict(
        id=record["id"],
        revision=record["revision"],
        presentation_key=f"{record['id']}:{record['revision']}",
        presenter="host",
        presentation="native_question_tool_if_available_else_short_chat",
        status="answered" if answered or record_answered(record) else "awaiting_user",
        questions=deepcopy(record["questions"]),
        required=list(record.get("required", [])),
        recorded_answers=deepcopy(record.get("answers", {})),
        record_with=dict(
            name="record_video_answers",
            arguments=dict(
                project_id=project_id,
                widget_id=record["id"],
                revision=record["revision"],
            ),
        ),
        instructions=(
            "Present only the question and short option labels using your native question tool if available; otherwise ask briefly in chat. "
            "You are the only presenter. Do not build an app, display a form, paste JSON or call show_video_brief to repeat this question. "
            "If this presentation_key was already asked, wait for its answer instead of asking again. "
            "Record only the user's actual reply with record_video_answers; user_message is their ordinary words, never a JSON payload. "
            "An answered question is an acknowledgement, not a request to ask it again."
        ),
    )
    if record.get("text_answers"):
        data["recorded_text_answers"] = deepcopy(record["text_answers"])
    return data


def record_answered(record):
    """Only actual saved/preselected answers count; recommendations never do."""
    asked = {q["id"] for q in record["questions"]}
    actual = set(record.get("answers", {})) | set(record.get("text_answers", {}))
    actual |= {
        "duration" if key == "duration_seconds" else key
        for key in record.get("output_profile", {})
    }
    return bool(asked) and asked <= actual


def pending_widget(state):
    """Construct or reuse a required brief; caller persists it with creative state."""
    context = intake_context(state)
    if not context or context["phase"] not in ("mode", "basics"):
        return None
    purpose, questions = context["phase"], context["questions"]
    existing = state.get("widgets", {}).get("brief")
    snapshot = basics_snapshot(state["intake"])
    if (
        existing
        and existing.get("purpose") == purpose
        and existing.get("questions") == questions
        and (purpose != "basics" or existing.get("intake_snapshot") == snapshot)
    ):
        return deepcopy(existing)
    widget = dict(
        id=ident(),
        kind="brief",
        purpose=purpose,
        title="Make it yours" if purpose == "mode" else "The basics",
        revision=1,
        creative_revision=state["revision"],
        state="open",
        questions=questions,
        required=[q["id"] for q in questions],
        answers={},
    )
    if purpose == "basics":
        widget["intake_snapshot"] = snapshot
    return widget


def initial_widget(state):
    return pending_widget(state)


def basics_snapshot(intake):
    return {
        key: deepcopy(intake.get(key, default))
        for key, default in (("output_profile", {}), ("delegated_basics", []))
    }


def apply_intake_answers(intake, purpose, answers, source):
    """Return updated intake only after a validated, explicit submission."""
    updated = deepcopy(intake)
    if purpose == "mode":
        mode = answers.get("involvement")
        if mode not in MODES:
            raise ValueError("Choose Hands off, Key moments, or Hands on")
        updated["mode"] = mode
        updated["provenance"]["mode"] = source
        if mode != "hands_on":
            updated.pop("pending_questions", None)
            updated.pop("pending_style", None)
    elif purpose == "basics":
        for question, choice in answers.items():
            field = (
                "duration_seconds" if question == "duration" else "viewing_destination"
            )
            updated["provenance"][question] = source
            if choice == "you_decide":
                updated["output_profile"].pop(field, None)
                updated["delegated_basics"] = list(
                    dict.fromkeys(updated["delegated_basics"] + [question])
                )
            else:
                updated["output_profile"][field] = (
                    int(choice) if question == "duration" else choice
                )
                updated["delegated_basics"] = [
                    q for q in updated["delegated_basics"] if q != question
                ]
    return updated
