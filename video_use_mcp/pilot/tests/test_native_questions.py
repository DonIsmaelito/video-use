"""Question/story proposals use host conversation, never an embedded form."""

import json

import pytest

from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_workflow import call
from video_use_mcp.pilot.tests.test_widgets import BEATS, QUESTIONS
from video_use_mcp.pilot.intake import intake_context

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def start(pilot, **updates):
    return call(
        pilot,
        "start_video",
        dict(title="Moon", brief="Explain the Moon", category="explainer") | updates,
    )


def answer(pilot, data, answers=None, user_message="Hands on", **updates):
    question = data["question"]
    return call(
        pilot,
        "record_video_answers",
        question["record_with"]["arguments"]
        | dict(request_id="answer-1", user_message=user_message, answers=answers or {})
        | updates,
    )


def test_question_and_story_tools_have_no_embedded_app_resource(pilot):
    tools = {t["name"]: t for t in rpc(pilot, "tools/list", {})["tools"]}
    for name in (
        "start_video",
        "show_video_brief",
        "show_video_story",
        "show_video_checkpoint",
    ):
        assert "ui" not in tools[name].get("_meta", {}), name
        assert "openai/outputTemplate" not in tools[name].get("_meta", {}), name
    assert tools["save_video_widget"]["_meta"]["ui"]["visibility"] == ["app"]


def test_first_question_has_one_host_presenter_and_no_redundant_tool_instruction(pilot):
    data = start(pilot)
    assert "widget" not in data
    question = data["question"]
    assert question["presenter"] == "host"
    assert (
        question["presentation"] == "native_question_tool_if_available_else_short_chat"
    )
    assert question["status"] == "awaiting_user"
    assert question["recorded_answers"] == {}
    assert question["required"] == ["involvement"]
    assert [q["id"] for q in question["questions"]] == ["involvement"]
    assert "next_tool" not in data["intake"]
    assert "do not call show_video_brief" in data["intake"]["next_action"]
    assert "otherwise ask briefly in chat" in question["instructions"]
    assert "never a JSON payload" in question["instructions"]


def test_accidental_duplicate_preparation_keeps_first_question_answerable(pilot):
    first = start(pilot)
    pid = first["project_id"]
    state = pilot[1].state.store.get("creative", pid)
    repeated = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=pid,
            creative_revision=state["revision"],
            questions=first["question"]["questions"],
        ),
    )
    assert "widget" not in repeated and "creative" not in repeated
    assert repeated["question"]["id"] == first["question"]["id"]
    assert (
        repeated["question"]["presentation_key"]
        == first["question"]["presentation_key"]
    )
    assert pilot[1].state.store.get("creative", pid)["revision"] == state["revision"]
    saved = answer(pilot, first, {"involvement": "hands_on"})
    assert "widget" not in saved and "creative" not in saved
    assert saved["question"]["status"] == "answered"
    assert saved["intake"]["mode"] == "hands_on"
    assert saved["intake"]["source"] == "assistant_reported_user"
    stored = pilot[1].state.store.get("creative", pid)
    assert stored["latest_widget_change"]["user_message"] == "Hands on"
    retry = answer(pilot, first, {"involvement": "hands_on"})
    assert (
        retry["repeated"] and retry["creative_revision"] == saved["creative_revision"]
    )


def test_native_mode_then_missing_basics_accepts_precise_ordinary_reply(pilot):
    first = start(pilot)
    chosen = answer(pilot, first, {"involvement": "delegate"}, user_message="Hands off")
    tool = chosen["intake"]["next_tool"]
    basics = call(pilot, tool["name"], tool["arguments"])
    assert "widget" not in basics
    assert basics["question"]["required"] == ["duration", "viewing_destination"]
    duplicate = call(pilot, tool["name"], tool["arguments"])
    assert (
        duplicate["question"]["presentation_key"]
        == basics["question"]["presentation_key"]
    )
    saved = answer(
        pilot,
        basics,
        user_message="45 seconds, for internal training",
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
    assert saved["question"]["status"] == "answered"
    assert saved["creative_revision"] == 3


def test_empty_native_answer_never_advances_required_intake(pilot):
    first = start(pilot)
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="record_video_answers",
            arguments=first["question"]["record_with"]["arguments"]
            | dict(request_id="no-answer", user_message="", answers={}),
        ),
    )
    assert result["isError"]
    assert (
        pilot[1].state.store.get("creative", first["project_id"])["intake"]["mode"]
        is None
    )


def test_native_story_is_a_small_summary_while_complete_plan_is_preserved(pilot):
    first = start(
        pilot, output_profile={"duration_seconds": 30, "viewing_destination": "web"}
    )
    chosen = answer(
        pilot, first, {"involvement": "key_moments"}, user_message="Key moments"
    )
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="show_video_story",
            arguments=dict(
                project_id=first["project_id"],
                creative_revision=chosen["creative_revision"],
                beats=BEATS,
            ),
        ),
    )
    assert not result.get("isError"), result
    data = result["structuredContent"]
    assert json.loads(result["content"][0]["text"]) == data
    assert "widget" not in data and "creative" not in data
    assert data["story"]["presentation"] == "short_chat_summary"
    assert data["story"]["source"] == "assistant_plan"
    assert all(
        set(beat) == {"id", "title", "seconds"} for beat in data["story"]["beats"]
    )
    assert data["story"]["proposed_duration"] == 11
    stored = pilot[1].state.store.get("creative", first["project_id"])
    assert stored["beats"] == BEATS
    assert stored["script"] == "\n\n".join(b["narration"] for b in BEATS)


def content_question(pilot):
    first = start(
        pilot,
        output_profile={"duration_seconds": 30, "viewing_destination": "web"},
        creation_approach="Motion design",
    )
    chosen = answer(pilot, first, {"involvement": "hands_on"})
    return call(
        pilot,
        "show_video_brief",
        dict(
            project_id=first["project_id"],
            creative_revision=chosen["creative_revision"],
            questions=QUESTIONS,
        ),
    )


def test_pending_content_question_is_recovered_without_replacing_it(pilot):
    shown = content_question(pilot)
    state = pilot[1].state.store.get("creative", shown["project_id"])
    context = intake_context(state, shown["project_id"])
    assert context["phase"] == "personalization"
    assert (
        context["question"]["presentation_key"] == shown["question"]["presentation_key"]
    )
    assert "next_tool" not in context
    assert "do not replace it" in context["next_action"]


def test_actual_freeform_content_answer_preserves_words_without_fake_option(pilot):
    shown = content_question(pilot)
    saved = answer(
        pilot,
        shown,
        {"tone": "warm"},
        user_message="For first-year engineering students, warm and curious",
        text_answers={"audience": "First-year engineering students"},
    )
    assert saved["intake"]["phase"] == "references"
    assert saved["question"]["status"] == "answered"
    assert saved["question"]["recorded_text_answers"] == {
        "audience": "First-year engineering students"
    }
    state = pilot[1].state.store.get("creative", shown["project_id"])
    answers = {a["question_id"]: a for a in state["brief_answers"]}
    assert answers["audience"]["answer"] == "First-year engineering students"
    assert answers["audience"]["source"] == "assistant_reported_user"
    assert "option_id" not in answers["audience"]
    assert answers["tone"]["option_id"] == "warm"
    assert "pending_questions" not in state["intake"]
    retried = answer(
        pilot,
        shown,
        {"tone": "warm"},
        user_message="For first-year engineering students, warm and curious",
        text_answers={"audience": "First-year engineering students"},
    )
    assert (
        retried["repeated"]
        and retried["creative_revision"] == saved["creative_revision"]
    )


@pytest.mark.parametrize(
    "texts,choices",
    [
        ({"audience": "x" * 2001}, {"tone": "warm"}),
        ({"audience": " "}, {"tone": "warm"}),
        ({"not_asked": "Someone"}, {"audience": "kids", "tone": "warm"}),
        ({"audience": "Teens"}, {"audience": "kids", "tone": "warm"}),
    ],
)
def test_freeform_content_is_bounded_current_and_unambiguous(pilot, texts, choices):
    shown = content_question(pilot)
    before = pilot[1].state.store.get("creative", shown["project_id"])
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="record_video_answers",
            arguments=shown["question"]["record_with"]["arguments"]
            | dict(
                request_id="invalid",
                user_message="My audience",
                text_answers=texts,
                answers=choices,
            ),
        ),
    )
    assert result["isError"]
    assert pilot[1].state.store.get("creative", shown["project_id"]) == before


def test_freeform_never_implies_involvement_choice(pilot):
    first = start(pilot)
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="record_video_answers",
            arguments=first["question"]["record_with"]["arguments"]
            | dict(
                request_id="invalid",
                user_message="Make it good",
                text_answers={"involvement": "Make it good"},
            ),
        ),
    )
    assert result["isError"]
    assert (
        pilot[1].state.store.get("creative", first["project_id"])["intake"]["mode"]
        is None
    )


def test_revised_freeform_replaces_same_answer_and_preserves_unrelated_context(pilot):
    shown = content_question(pilot)
    first = answer(
        pilot,
        shown,
        {"tone": "warm"},
        user_message="First-year students, warm",
        text_answers={"audience": "First-year students"},
    )
    revised = answer(
        pilot,
        first,
        {"tone": "precise"},
        user_message="Actually PhD students, precise",
        text_answers={"audience": "PhD students"},
        request_id="answer-2",
    )
    state = pilot[1].state.store.get("creative", shown["project_id"])
    entries = state["brief_answers"]
    assert sum(a["question_id"] == "audience" for a in entries) == 1
    assert {a["question_id"]: a["answer"] for a in entries} == {
        "involvement": "Hands on",
        "audience": "PhD students",
        "tone": "Clear and precise",
    }
    assert revised["question"]["recorded_text_answers"] == {"audience": "PhD students"}


def test_freeform_cannot_substitute_for_excerpt_acceptance(pilot):
    from video_use_mcp.pilot.tests.test_intake import checkpoint

    shown = checkpoint(pilot)
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
                user_message="Looks okay I guess",
                text_answers={"excerpt_review": "Looks okay I guess"},
            ),
        ),
    )
    assert result["isError"]
    assert (
        pilot[1].state.store.get("creative", shown["project_id"])["intake"][
            "excerpt_review"
        ]["status"]
        == "pending"
    )


def test_partial_chat_correction_preserves_prior_answers_and_retry_identity(pilot):
    shown = content_question(pilot)
    first = answer(
        pilot,
        shown,
        {"tone": "warm"},
        user_message="First-year students, warm",
        text_answers={"audience": "First-year students"},
    )
    revised = answer(
        pilot,
        first,
        user_message="Actually PhD students",
        text_answers={"audience": "PhD students"},
        request_id="audience-change",
    )
    entries = pilot[1].state.store.get("creative", shown["project_id"])["brief_answers"]
    assert {a["question_id"]: a["answer"] for a in entries} == {
        "involvement": "Hands on",
        "audience": "PhD students",
        "tone": "Warm and curious",
    }
    later = answer(
        pilot,
        revised,
        {"tone": "precise"},
        user_message="Make the tone precise",
        request_id="tone-change",
    )
    repeated = answer(
        pilot,
        first,
        user_message="Actually PhD students",
        text_answers={"audience": "PhD students"},
        request_id="audience-change",
    )
    assert repeated["repeated"]
    assert repeated["creative_revision"] == later["creative_revision"]
    assert repeated["question"]["recorded_answers"]["tone"] == "precise"
    assert repeated["question"]["status"] == "answered"


def test_known_reopened_content_does_not_force_another_answer(pilot):
    shown = content_question(pilot)
    answered = answer(
        pilot,
        shown,
        {"audience": "kids", "tone": "warm"},
        user_message="Children, warm and curious",
    )
    reopened = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=shown["project_id"],
            creative_revision=answered["creative_revision"],
            questions=[QUESTIONS[0]],
        ),
    )
    assert reopened["question"]["status"] == "answered"
    assert reopened["question"]["recorded_answers"] == {"audience": "kids"}
    assert reopened["intake"]["phase"] == "references"
    assert (
        "pending_questions"
        not in pilot[1].state.store.get("creative", shown["project_id"])["intake"]
    )


def test_known_freeform_answer_survives_reopened_question_and_can_be_corrected(pilot):
    shown = content_question(pilot)
    first = answer(
        pilot,
        shown,
        {"tone": "warm"},
        user_message="Engineering students, warm",
        text_answers={"audience": "Engineering students"},
    )
    reopened = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=shown["project_id"],
            creative_revision=first["creative_revision"],
            questions=[QUESTIONS[0]],
        ),
    )
    assert reopened["question"]["status"] == "answered"
    assert reopened["question"]["recorded_text_answers"] == {
        "audience": "Engineering students"
    }
    assert reopened["intake"]["phase"] == "references"
    corrected = answer(
        pilot,
        reopened,
        user_message="Make that PhD students",
        text_answers={"audience": "PhD students"},
    )
    assert corrected["question"]["recorded_text_answers"] == {
        "audience": "PhD students"
    }


def test_freeform_restoration_with_a_new_question_requires_only_its_answer(pilot):
    shown = content_question(pilot)
    first = answer(
        pilot,
        shown,
        {"tone": "warm"},
        user_message="Engineering students, warm",
        text_answers={"audience": "Engineering students"},
    )
    goal = dict(
        id="goal",
        prompt="What should they take away?",
        options=[
            dict(id="intuition", label="An intuition"),
            dict(id="method", label="A method"),
        ],
    )
    reopened = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=shown["project_id"],
            creative_revision=first["creative_revision"],
            questions=[QUESTIONS[0], goal],
        ),
    )
    assert reopened["question"]["status"] == "awaiting_user"
    assert reopened["question"]["recorded_text_answers"] == {
        "audience": "Engineering students"
    }
    saved = answer(pilot, reopened, {"goal": "intuition"}, user_message="An intuition")
    assert saved["intake"]["phase"] == "references"
    entries = pilot[1].state.store.get("creative", shown["project_id"])["brief_answers"]
    assert {a["question_id"]: a["answer"] for a in entries} == {
        "involvement": "Hands on",
        "audience": "Engineering students",
        "tone": "Warm and curious",
        "goal": "An intuition",
    }
