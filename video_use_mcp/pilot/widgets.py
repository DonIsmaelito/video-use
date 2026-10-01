"""Optional in-chat direction and story editors with durable user provenance."""

import hashlib
import json
from copy import deepcopy

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, ConfigDict, Field

from .creative_state import creative_edit
from .allowance import narration_allowance
from .experience import experience_context
from .interaction import UI_META
from .store import ident


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    label: str = Field(min_length=1, max_length=80)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    prompt: str = Field(min_length=1, max_length=180)
    options: list[Option] = Field(min_length=2, max_length=4)
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
    return {k: v for k, v in widget.items() if k != "receipts"}


def creative_public(creative):
    """Widget schemas/receipts need not be repeated in routine model context."""
    if creative is None:
        return None
    return {k: v for k, v in creative.items() if k != "widgets"}


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


def merge_brief_answers(previous, questions, answers):
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
            source="user_submit",
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
        return dict(
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

    def present(project_id, state, widget):
        # Keep at most the current brief and current story. One atomic KV write
        # contains the proposal, creative context and later idempotency receipts.
        state.setdefault("widgets", {})[widget["kind"]] = widget
        store.put("creative", project_id, state)
        data = output(project_id, state, widget)
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

    @mcp.tool(annotations=write, meta=UI_META, title="Shape the direction")
    @creative_edit
    def show_video_brief(
        project_id: str,
        creative_revision: int,
        questions: list[Question],
        title: str = "Make it yours",
    ) -> CallToolResult:
        """Optional compact choice buttons for 1–3 consequential unanswered questions, such as audience or tone. Author choices for this request; skip questions already answered or delegated. Recommendations are not selected or approved. The user can save any answers while you continue independent work; no approval stop. Use show_video_choices instead when actual motion references communicate a visual decision better."""
        state = context(project_id)
        if state["revision"] != creative_revision:
            raise ValueError(
                "Creative preferences changed; read get_video_project before proposing choices"
            )
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
        widget = dict(
            id=ident(),
            kind="brief",
            title=title,
            revision=1,
            creative_revision=creative_revision,
            state="open",
            questions=[q.model_dump() for q in questions],
            answers=saved_brief_answers(state, questions),
        )
        return present(project_id, state, widget)

    @mcp.tool(annotations=write, meta=UI_META, title="Shape the story and script")
    @creative_edit
    def show_video_story(
        project_id: str,
        creative_revision: int,
        beats: list[StoryBeat],
        title: str = "The story",
    ) -> CallToolResult:
        """Show and save a concise editable scene sequence with narration and proposed durations before voicing a substantial new story. This replaces a separate plan_video call when useful. These are story cards, not rendered frames or a measured timeline. User changes are optional and reach current creative context; keep working without an approval pause. Skip for a precise edit, delegated script or a trivial title card. Stable beat IDs support targeted revisions. Do not overwrite newer user direction."""
        state = context(project_id)
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
        """Save only an explicit user submission from the brief or story editor. Reject replaced/outdated widgets and conflicting retries; preserve unrelated creative choices."""
        state = context(project_id)
        widget = next(
            (w for w in state.get("widgets", {}).values() if w["id"] == widget_id), None
        )
        if not widget:
            raise ValueError("This editor was replaced; ask to see the latest version")
        if not 1 <= len(request_id) <= 120:
            raise ValueError("Provide a request ID of 1–120 characters")
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
            value = dict(answers)
        else:
            if answers is not None or beats is None:
                raise ValueError("Submit story beats for this editor")
            value = validate_beats(beats)
            if {b["id"] for b in value} != {b["id"] for b in widget["beats"]}:
                raise ValueError(
                    "Keep the current beat IDs; ask your assistant to add or remove scenes"
                )
        digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
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
        # Story edits must not silently replace a newer plan written elsewhere.
        if widget["kind"] == "story" and state.get("beats") != widget["beats"]:
            raise ValueError(
                "The story changed since this editor opened; ask to see the latest story"
            )
        previous = (
            widget.get("answers") if widget["kind"] == "brief" else widget["beats"]
        )
        if value == previous:
            return output(project_id, state, widget, saved=False)
        state["revision"] += 1
        widget["revision"] += 1
        widget["creative_revision"] = state["revision"]
        if widget["kind"] == "brief":
            widget["answers"] = value
            state["brief_answers"] = merge_brief_answers(
                state.get("brief_answers", []), widget["questions"], value
            )
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
            source="user_submit",
            creative_revision=state["revision"],
        )
        widget["receipts"] = (
            widget.get("receipts", []) + [{"id": request_id, "digest": digest}]
        )[-20:]
        store.put("creative", project_id, state)
        return output(project_id, state, widget, saved=True)
