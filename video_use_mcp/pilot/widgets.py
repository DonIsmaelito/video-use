"""Host-native questions and story context, with legacy editor save support."""

import hashlib
import json
from copy import deepcopy

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, ConfigDict, Field

from .creative_state import creative_edit
from .allowance import narration_allowance
from .experience import experience_context
from .store import ident
from .question_card import choice_presentation
from .intake import (
    intake_context,
    apply_intake_answers,
    initialize_intake,
    basics_snapshot,
    pending_widget,
    INVOLVEMENT_QUESTION,
    question_context,
    record_answered,
)


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    label: str = Field(min_length=1, max_length=80)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    prompt: str = Field(min_length=1, max_length=180)
    options: list[Option] = Field(min_length=2, max_length=5)
    recommended: str = ""


class StoryBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    title: str = Field(min_length=1, max_length=100)
    visual: str = Field(min_length=1, max_length=400)
    narration: str = Field(default="", max_length=2000)
    seconds: float = Field(gt=0, le=600, allow_inf_nan=False)


def validate_beats(beats):
    if not 1 <= len(beats) <= 12 or len({b.id for b in beats}) != len(beats):
        raise ValueError("Use 1–12 story beats with distinct stable IDs")
    if sum(b.seconds for b in beats) > 7200:
        raise ValueError("Keep the proposed story within two hours")
    if sum(len(b.narration) for b in beats) > 12000:
        raise ValueError("Keep the proposed script within 12000 characters")
    return [b.model_dump() for b in beats]


def widget_public(widget):
    return {k: v for k, v in widget.items() if k not in ("receipts", "intake_snapshot")}


def creative_public(creative):
    """Widget schemas/receipts need not be repeated in routine model context."""
    if creative is None:
        return None
    public = {k: v for k, v in creative.items() if k != "widgets"}
    if creative.get("intake", {}).get("reference_direction"):
        from .reference_direction import reference_context

        public["intake"] = dict(
            creative["intake"], reference_direction=reference_context(creative)
        )
    return public


def saved_brief_answers(state, questions):
    """Preselect only earlier explicit answers with the same question and option."""
    answers = {}
    for question in questions:
        previous = next(
            (
                answer
                for answer in state.get("brief_answers", [])
                if answer.get("question_id", question.id) == question.id
                and answer.get("question") == question.prompt
            ),
            None,
        )
        if previous:
            option = next(
                (
                    option
                    for option in question.options
                    if option.label == previous.get("answer")
                    and previous.get("option_id", option.id) == option.id
                ),
                None,
            )
            if option:
                answers[question.id] = option.id
    return answers


def merge_brief_answers(previous, questions, answers, source="user_submit"):
    """A submission replaces only offered questions, preserving earlier steering."""
    offered_ids = {q["id"] for q in questions}
    offered_prompts = {q["prompt"] for q in questions}
    retained = [
        answer
        for answer in previous
        if (
            answer["question_id"] not in offered_ids
            if "question_id" in answer
            else answer.get("question") not in offered_prompts
        )
    ]
    return retained + [
        dict(
            question_id=q["id"],
            question=q["prompt"],
            option_id=answers[q["id"]],
            answer=next(
                o["label"] for o in q["options"] if o["id"] == answers[q["id"]]
            ),
            source=source,
        )
        for q in questions
        if q["id"] in answers
    ]


def register_widgets(mcp, store, muser, read, write):
    def context(project_id):
        store.project(muser(True), project_id)
        state = deepcopy(store.get("creative", project_id) or {})
        if not state:
            raise ValueError("Start this video before offering a creative choice")
        return state

    def output(project_id, state, widget, *, saved=False, repeated=False):
        result = dict(
            project_id=project_id,
            widget=widget_public(widget),
            creative=creative_public(state),
            saved=saved,
            repeated=repeated,
            next_action=(
                "Use these explicit user changes in the next affected edit; retain "
                "compatible work. Read the current creative revision before rendering."
                if saved
                else "This is an optional steering control, not an approval gate. "
                "Briefly explain your recommended direction and continue independent "
                "work using reversible assumptions. Read current creative choices in "
                "task results before paid narration or further rendering. A displayed "
                "proposal or recommended option is not user approval. Do not end the "
                "turn just because this widget was shown."
            ),
        )
        intake = intake_context(state, project_id)
        if intake:
            result["intake"] = intake
            result["next_action"] = intake["next_action"]
        return result

    def native_output(project_id, state, record, *, saved=False, repeated=False):
        data = dict(
            project_id=project_id,
            creative_revision=state["revision"],
            saved=saved,
            repeated=repeated,
        )
        intake = intake_context(state, project_id)
        if intake:
            data["intake"] = {
                k: v
                for k, v in intake.items()
                if k
                not in (
                    "questions",
                    "missing_basic_questions",
                    "question",
                    "next_action",
                )
            }
            data["next_action"] = intake["next_action"]
        else:
            data["next_action"] = (
                "Use the explicit user answer in the next edit; preserve compatible work."
                if saved
                else "Ask only if this unresolved choice matters. It is optional, not an approval gate; continue independent work. A recommendation is not a user answer."
            )
        if record["kind"] == "brief":
            data["question"] = question_context(
                project_id, record, answered=saved or bool(record.get("receipts"))
            )
        else:
            data["story"] = dict(
                id=record["id"],
                revision=record["revision"],
                title=record["title"],
                beats=[
                    {k: beat[k] for k in ("id", "title", "seconds")}
                    for beat in record["beats"]
                ],
                proposed_duration=sum(b["seconds"] for b in record["beats"]),
                source=state.get("plan_provenance", "assistant_plan"),
                presentation="short_chat_summary",
                instructions="Summarize the proposed story in a few natural sentences. Do not show an editable form, field-by-field script, JSON or an app. These durations are proposed, not measured. Invite ordinary conversational corrections without a routine approval stop.",
            )
        return choice_presentation(data, store)

    def present(project_id, state, widget):
        # Keep at most the current brief and current story. One atomic KV write
        # contains the proposal, creative context and later idempotency receipts.
        state.setdefault("widgets", {})[widget["kind"]] = widget
        store.put("creative", project_id, state)
        data = native_output(project_id, state, widget)
        if widget["kind"] == "story" and state.get("script"):
            data["narration_allowance"] = narration_allowance(
                store, muser(True), requested_characters=len(state["script"])
            )
            if data["narration_allowance"].get("fits_available") is False:
                data["experience"] = experience_context(
                    state,
                    event="story",
                    blocker={
                        "kind": "narration_capacity_shortfall",
                        "resource": "narration",
                        "automatic_retry": False,
                    },
                )
                data["next_action"] = (
                    "This proposed script exceeds the current remaining allowance for "
                    "new narration. Explain the shortfall now and offer a compact choice "
                    "with show_video_brief if input is needed: wait for capacity, supply "
                    "audio with request_video_sources, or explicitly choose a silent draft. "
                    "Existing matching cached audio may still be reusable. Continue cheap "
                    "independent sketches; resolve the requested audio before committing "
                    "to full scene timing. Do not silently remove voiceover or assume "
                    "permission to increase the allowance."
                )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(data))],
            structuredContent=data,
        )

    @mcp.tool(annotations=write, title="Prepare a creative question")
    @creative_edit
    def show_video_brief(
        project_id: str,
        creative_revision: int,
        questions: list[Question],
        title: str = "Make it yours",
    ) -> CallToolResult:
        """Prepare a question for you to ask using the host's native question tool if available, otherwise short ordinary chat. This tool displays no custom UI. Do not call it for a question already returned by start_video; present that question once instead. Identical questions reuse their existing ID. Required involvement/basics/creation approach and offered Hands on content need explicit answers; during the approach phase tailor only one creation_approach question with 2–5 relevant options including you_decide, without selecting for the user. If the host cannot fit all options, ask in short normal chat. Key moments questions remain optional. Record the user's actual words with record_video_answers. Never paste tool JSON into chat or ask known context again."""
        state = context(project_id)
        if state["revision"] != creative_revision:
            raise ValueError(
                "Creative preferences changed; read get_video_project before proposing choices"
            )
        intake = intake_context(state, project_id)
        if intake and intake["phase"] in ("mode", "basics"):
            # These questions belong to saved intake, not a host reconstruction.
            # Reuse their identity and ask only what is still unanswered.
            return present(project_id, state, pending_widget(state))
        if not title.strip() or len(title) > 120 or not 1 <= len(questions) <= 3:
            raise ValueError("Use a short title and 1–3 focused questions")
        if len({q.id for q in questions}) != len(questions):
            raise ValueError("Question IDs must be distinct")
        for question in questions:
            ids = {o.id for o in question.options}
            if len(ids) != len(question.options) or (
                question.recommended and question.recommended not in ids
            ):
                raise ValueError(
                    "Options must be distinct and recommendations must name an offered option"
                )
        purpose, required = None, []
        if intake:
            if intake["phase"] == "approach":
                if (
                    len(questions) != 1
                    or questions[0].id != "creation_approach"
                    or "you_decide" not in {o.id for o in questions[0].options}
                ):
                    raise ValueError(
                        "Ask one creation_approach question with relevant video types and a you_decide option"
                    )
                purpose, required = "approach", ["creation_approach"]
            elif any(q.id == "involvement" for q in questions):
                if [q.model_dump() for q in questions] != [
                    Question(**INVOLVEMENT_QUESTION).model_dump()
                ]:
                    raise ValueError(
                        "Offer the involvement question separately with its standard choices"
                    )
                purpose, required = "mode", ["involvement"]
            elif intake["mode"] == "hands_on":
                purpose, required = "personalization", [q.id for q in questions]
            elif intake["mode"] == "delegate":
                raise ValueError(
                    "Hands off is selected. Continue to the finished video without optional questions."
                )
        existing = state.get("widgets", {}).get("brief") or {}
        values = [q.model_dump() for q in questions]
        if (
            existing.get("questions") == values
            and existing.get("purpose") == purpose
            and (
                purpose != "basics"
                or existing.get("intake_snapshot") == basics_snapshot(state["intake"])
            )
        ):
            return present(project_id, state, existing)
        widget = dict(
            id=ident(),
            kind="brief",
            title=title,
            revision=1,
            creative_revision=creative_revision,
            state="open",
            questions=values,
            answers={}
            if purpose in ("mode", "basics", "approach")
            else saved_brief_answers(state, questions),
        )
        if purpose:
            widget.update(purpose=purpose, required=required)
        if purpose not in ("mode", "basics", "approach"):
            prior_text = {}
            for question in questions:
                if question.id in widget["answers"]:
                    continue
                previous = next(
                    (
                        a
                        for a in state.get("brief_answers", [])
                        if a.get("question_id") == question.id
                        and a.get("question") == question.prompt
                        and a.get("source") == "assistant_reported_user"
                        and "option_id" not in a
                    ),
                    None,
                )
                if (
                    previous
                    and isinstance(previous.get("answer"), str)
                    and previous["answer"].strip()
                ):
                    prior_text[question.id] = previous["answer"]
            if prior_text:
                widget["text_answers"] = prior_text
        if purpose == "basics":
            widget["intake_snapshot"] = basics_snapshot(state["intake"])
        if purpose == "personalization":
            if record_answered(widget):
                state["intake"].pop("pending_questions", None)
            else:
                state["intake"]["pending_questions"] = dict(
                    widget_id=widget["id"], answered=False
                )
        return present(project_id, state, widget)

    @mcp.tool(annotations=write, title="Prepare the story")
    @creative_edit
    def show_video_story(
        project_id: str,
        creative_revision: int,
        beats: list[StoryBeat],
        title: str = "The story",
    ) -> CallToolResult:
        """Save the proposed story/script and return a compact outline for a short conversational summary. No custom form or app is displayed. Do not expose editable fields or paste JSON; the user can request changes in ordinary chat. Proposed durations are not measured. Hands on separately reviews a real short excerpt. Hands off plans internally instead. Skip precise edits or already specified scripts and never overwrite newer direction."""
        state = context(project_id)
        intake = intake_context(state, project_id)
        if intake and intake["phase"] in (
            "mode",
            "basics",
            "approach",
            "personalization",
            "references",
        ):
            raise ValueError(intake["next_action"])
        if intake and intake["mode"] == "delegate":
            raise ValueError(
                "Hands off is selected. Plan internally and proceed to the finished video."
            )
        if state["revision"] != creative_revision:
            raise ValueError(
                "Creative preferences changed; read get_video_project before proposing a story"
            )
        if not title.strip() or len(title) > 120:
            raise ValueError("Use a story title of 1–120 characters")
        values = validate_beats(beats)
        state["revision"] += 1
        state["beats"] = values
        state["script"] = "\n\n".join(b["narration"] for b in values if b["narration"])
        state["plan_provenance"] = "assistant_plan"
        widget = dict(
            id=ident(),
            kind="story",
            title=title,
            revision=1,
            creative_revision=state["revision"],
            state="open",
            beats=values,
        )
        return present(project_id, state, widget)

    def save_widget(
        project_id: str,
        widget_id: str,
        revision: int,
        request_id: str,
        answers: dict[str, str] | None = None,
        beats: list[StoryBeat] | None = None,
        *,
        source="user_submit",
        user_message="",
        output_profile=None,
        text_answers=None,
    ) -> dict:
        """Save only an explicit user submission from the brief or story editor. Reject replaced/outdated widgets and conflicting retries; preserve unrelated creative choices."""
        state = context(project_id)
        widget = next(
            (w for w in state.get("widgets", {}).values() if w["id"] == widget_id), None
        )
        if not widget:
            raise ValueError("This editor was replaced; ask to see the latest version")
        if not 1 <= len(request_id) <= 120:
            raise ValueError("Provide a request ID of 1–120 characters")
        purpose = widget.get("purpose")
        exact = {}
        freeform = {} if text_answers is None else text_answers
        if freeform:
            if (
                source != "assistant_reported_user"
                or widget["kind"] != "brief"
                or purpose in ("mode", "basics", "excerpt_review")
            ):
                raise ValueError(
                    "Freeform answers are only for content questions, not involvement, output basics, or excerpt acceptance"
                )
            if (
                any(
                    key
                    in (
                        "involvement",
                        "duration",
                        "viewing_destination",
                        "excerpt_review",
                    )
                    or not isinstance(value, str)
                    or not value.strip()
                    or len(value) > 2000
                    for key, value in freeform.items()
                )
                or sum(len(value) for value in freeform.values()) > 4000
            ):
                raise ValueError(
                    "Use 1–2000 characters per content answer, up to 4000 total; use explicit choices for involvement and review"
                )
            freeform = {key: value.strip() for key, value in freeform.items()}
        if output_profile is not None:
            if purpose != "basics" or source != "assistant_reported_user":
                raise ValueError(
                    "Exact output values can answer only the current basics page from an explicit chat reply"
                )
            exact = initialize_intake({"revision": 1}, output_profile)["intake"][
                "output_profile"
            ]
            asked = {q["id"] for q in widget["questions"]}
            fields = {
                "duration_seconds": "duration",
                "viewing_destination": "viewing_destination",
            }
            if any(fields[field] not in asked for field in exact):
                raise ValueError("Only supply output values asked on this page")
            if any(fields[field] in (answers or {}) for field in exact):
                raise ValueError(
                    "Give either an offered choice or an exact chat value for each question"
                )
        if widget["kind"] == "brief":
            if beats is not None or answers is None:
                raise ValueError("Submit answers for this direction picker")
            offered = {
                q["id"]: {o["id"] for o in q["options"]} for q in widget["questions"]
            }
            if any(
                key not in offered or value not in offered[key]
                for key, value in answers.items()
            ):
                raise ValueError("Choose only offered answers")
            if any(key not in offered or key in answers for key in freeform):
                raise ValueError(
                    "Give either an offered choice or a freeform answer for each current content question"
                )
            value = dict(answers)
        else:
            if answers is not None or beats is None:
                raise ValueError("Submit story beats for this editor")
            value = validate_beats(beats)
            if {b["id"] for b in value} != {b["id"] for b in widget["beats"]}:
                raise ValueError(
                    "Keep the current beat IDs; ask your assistant to add or remove scenes"
                )
        submitted = {"answers": value, "output_profile": exact} if exact else value
        if freeform:
            submitted = dict(answers=value, text_answers=freeform)
        if source == "assistant_reported_user":
            # A second "Refine" with different words is a different edit.
            # Legacy app receipts keep their format; old native receipts fail
            # closed rather than silently treating unverifiable feedback as equal.
            submitted = dict(values=submitted, source=source, user_message=user_message)
        digest = hashlib.sha256(
            json.dumps(submitted, sort_keys=True).encode()
        ).hexdigest()
        receipt = next(
            (r for r in widget.get("receipts", []) if r["id"] == request_id), None
        )
        if receipt:
            if receipt["digest"] != digest:
                raise ValueError(
                    "That request ID saved different changes; use a new request ID"
                )
            return output(project_id, state, widget, saved=True, repeated=True)
        if revision != widget["revision"]:
            raise ValueError(
                "This editor is outdated; reopen the latest version before saving"
            )
        answered = (
            (set(value) if isinstance(value, dict) else set())
            | {"duration" if f == "duration_seconds" else f for f in exact}
            | set(freeform)
        )
        if source == "assistant_reported_user":
            answered |= set(widget.get("answers", {})) | set(
                widget.get("text_answers", {})
            )
            answered |= {
                "duration" if key == "duration_seconds" else key
                for key in widget.get("output_profile", {})
            }
        if widget.get("required") and any(
            q not in answered for q in widget["required"]
        ):
            raise ValueError(
                "Answer every question on this page; an offered You decide is an explicit answer"
            )
        if purpose == "basics" and widget.get("intake_snapshot") != basics_snapshot(
            state["intake"]
        ):
            raise ValueError(
                "Output basics changed since this page opened; ask for the current missing questions"
            )
        if purpose == "excerpt_review":
            review = state.get("intake", {}).get("excerpt_review", {})
            bound = widget.get("media_object_id")
            progress = store.get("progress", project_id) or {}
            latest = progress.get("latest_preview") or next(
                (
                    u
                    for u in reversed(progress.get("updates", []))
                    if u.get("preview") and u.get("stage") != "review"
                ),
                {},
            )
            current = latest.get("preview", {}).get("object_id")
            if not bound or review.get("object_id") != bound or current != bound:
                raise ValueError(
                    "This excerpt is outdated; ask to review the current preview"
                )
            if review.get("creative_revision") != state["revision"]:
                raise ValueError(
                    "Creative preferences changed; show the current excerpt for review again"
                )
            if review.get("status") not in ("pending", "changes_requested"):
                raise ValueError("This excerpt review is no longer pending")
            if value.get("excerpt_review") not in ("continue", "refine"):
                raise ValueError("Choose Continue or Refine for this excerpt")
        # Story edits must not silently replace a newer plan written elsewhere.
        if widget["kind"] == "story" and state.get("beats") != widget["beats"]:
            raise ValueError(
                "The story changed since this editor opened; ask to see the latest story"
            )
        previous = (
            widget.get("answers") if widget["kind"] == "brief" else widget["beats"]
        )
        previously_answered = widget["kind"] == "brief" and record_answered(widget)
        if (
            value == previous
            and freeform == widget.get("text_answers", {})
            and not widget.get("required")
        ):
            return output(project_id, state, widget, saved=False)
        state["revision"] += 1
        widget["revision"] += 1
        widget["creative_revision"] = state["revision"]
        if widget["kind"] == "brief":
            previous_text = widget.get("text_answers", {})
            previous_exact = widget.get("output_profile", {})
            supplied = (
                set(value)
                | set(freeform)
                | {"duration" if k == "duration_seconds" else k for k in exact}
            )
            native = source == "assistant_reported_user"
            widget["answers"] = (widget.get("answers", {}) | value) if native else value
            for key in set(freeform) | {
                "duration" if k == "duration_seconds" else k for k in exact
            }:
                widget["answers"].pop(key, None)
            retained_text = (
                {k: v for k, v in previous_text.items() if k not in supplied}
                if native
                else {}
            )
            retained_exact = (
                {
                    k: v
                    for k, v in previous_exact.items()
                    if ("duration" if k == "duration_seconds" else k) not in supplied
                }
                if native
                else {}
            )
            widget.pop("output_profile", None)
            widget.pop("text_answers", None)
            state["brief_answers"] = merge_brief_answers(
                state.get("brief_answers", []),
                [q for q in widget["questions"] if q["id"] in supplied]
                if native
                else widget["questions"],
                value,
                source,
            )
            if exact:
                for field, exact_value in exact.items():
                    question_id = "duration" if field == "duration_seconds" else field
                    question = next(
                        q for q in widget["questions"] if q["id"] == question_id
                    )
                    state["brief_answers"].append(
                        dict(
                            question_id=question_id,
                            question=question["prompt"],
                            answer=f"{exact_value:g} seconds"
                            if field == "duration_seconds"
                            else exact_value,
                            source=source,
                        )
                    )
            if retained_exact or exact:
                widget["output_profile"] = retained_exact | exact
            if freeform:
                state["brief_answers"].extend(
                    dict(
                        question_id=question["id"],
                        question=question["prompt"],
                        answer=freeform[question["id"]],
                        source=source,
                    )
                    for question in widget["questions"]
                    if question["id"] in freeform
                )
            if retained_text or freeform:
                widget["text_answers"] = retained_text | freeform
            if purpose in ("mode", "basics"):
                state["intake"] = apply_intake_answers(
                    state["intake"], purpose, value, source
                )
                if exact:
                    state = initialize_intake(state, exact)
                    widget = state["widgets"][widget["kind"]]
                if purpose == "basics":
                    widget["intake_snapshot"] = basics_snapshot(state["intake"])
            elif purpose == "approach":
                choice = widget["answers"].get("creation_approach")
                custom = widget.get("text_answers", {}).get("creation_approach")
                selected = next(
                    (o for o in widget["questions"][0]["options"] if o["id"] == choice),
                    None,
                )
                if not selected and not custom:
                    raise ValueError(
                        "Choose a creation approach or describe the type of video you want"
                    )
                state["intake"]["creation_approach"] = dict(
                    version=1,
                    status="delegated" if choice == "you_decide" else "selected",
                    id=choice or "user_described",
                    label=selected["label"] if selected else custom,
                    source=source,
                    user_message=user_message,
                )
            elif purpose == "personalization":
                pending = state["intake"].get("pending_questions")
                if (pending and pending.get("widget_id") != widget_id) or (
                    not pending
                    and not widget.get("receipts")
                    and not previously_answered
                ):
                    raise ValueError("This content question is outdated")
                state["intake"].pop("pending_questions", None)
            elif purpose == "excerpt_review":
                state["intake"]["excerpt_review"].update(
                    status="approved"
                    if value["excerpt_review"] == "continue"
                    else "changes_requested",
                    source=source,
                    creative_revision=state["revision"],
                )
                if user_message:
                    state["intake"]["excerpt_review"]["user_message"] = user_message
                else:
                    state["intake"]["excerpt_review"].pop("user_message", None)
        else:
            widget["beats"] = value
            state["beats"] = value
            state["script"] = "\n\n".join(
                b["narration"] for b in value if b["narration"]
            )
            state["plan_provenance"] = "user_edit"
        state["latest_widget_change"] = dict(
            kind=widget["kind"],
            widget_id=widget_id,
            source=source,
            creative_revision=state["revision"],
        )
        if user_message:
            state["latest_widget_change"]["user_message"] = user_message
        widget["receipts"] = (
            widget.get("receipts", []) + [{"id": request_id, "digest": digest}]
        )[-20:]
        store.put("creative", project_id, state)
        return output(project_id, state, widget, saved=True)

    @mcp.tool(
        annotations=write,
        meta={"ui": {"visibility": ["app"]}},
        title="Save creative changes",
    )
    @creative_edit
    def save_video_widget(
        project_id: str,
        widget_id: str,
        revision: int,
        request_id: str,
        answers: dict[str, str] | None = None,
        beats: list[StoryBeat] | None = None,
    ) -> dict:
        """Save an explicit user submission from an in-chat editor."""
        return save_widget(project_id, widget_id, revision, request_id, answers, beats)

    @mcp.tool(
        annotations=write,
        meta={"ui": {"visibility": ["app"]}},
        title="Save your choice",
    )
    @creative_edit
    def submit_video_choice(
        project_id: str,
        widget_id: str,
        revision: int,
        request_id: str,
        answers: dict[str, str],
    ) -> dict:
        """Save a choice card click and return a short conversational reply."""
        state = context(project_id)
        widget = next(
            (w for w in state.get("widgets", {}).values() if w["id"] == widget_id),
            None,
        )
        if not widget or widget["kind"] != "brief":
            raise ValueError(
                "This question has changed; ask to see the current choices"
            )
        if not answers:
            raise ValueError("Choose an option before submitting")
        labels = [
            option["label"]
            for q in widget["questions"]
            for option in q["options"]
            if answers.get(q["id"]) == option["id"]
        ]
        saved = save_widget(project_id, widget_id, revision, request_id, answers)
        state = context(project_id)
        record = next(w for w in state["widgets"].values() if w["id"] == widget_id)
        data = native_output(
            project_id, state, record, saved=True, repeated=saved["repeated"]
        )
        return {
            "saved": True,
            "message": "; ".join(labels),
            "context": data
            | {
                "answer_already_saved": True,
                "handoff": "These explicit choices are already saved. Continue from this project's intake; do not record the same answer again.",
            },
        }

    @mcp.tool(annotations=write, title="Record your answer")
    @creative_edit
    def record_video_answers(
        project_id: str,
        widget_id: str,
        revision: int,
        request_id: str,
        user_message: str,
        answers: dict[str, str] | None = None,
        output_profile: dict | None = None,
        text_answers: dict[str, str] | None = None,
    ) -> dict:
        """Record the user's explicit native-question or chat reply. Quote their actual words in user_message, never JSON or inferred consent. Map offered choices in answers. For output basics outside presets use exact output_profile={duration_seconds:45,viewing_destination:'internal training'}. For content questions outside offered options, use text_answers={question_id:'their answer'} without inventing an option ID. Freeform cannot approve involvement or an excerpt. Every required question needs an explicit answer. Provenance remains assistant-reported user input, not a button click."""
        if not user_message.strip() or len(user_message) > 4000:
            raise ValueError("Include the user's explicit answer in 1–4000 characters")
        saved = save_widget(
            project_id,
            widget_id,
            revision,
            request_id,
            answers or {},
            source="assistant_reported_user",
            user_message=user_message,
            output_profile=output_profile,
            text_answers=text_answers,
        )
        state = context(project_id)
        record = next(w for w in state["widgets"].values() if w["id"] == widget_id)
        return native_output(
            project_id, state, record, saved=saved["saved"], repeated=saved["repeated"]
        )
