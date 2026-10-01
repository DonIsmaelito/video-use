"""Advertised guidance must be callable and fit a small browser editing context."""

import pytest

from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.workflow import WORKFLOW_DETAILS

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def guidance(pilot, topic):
    return rpc(
        pilot,
        "tools/call",
        {"name": "video_use_guidance", "arguments": {"topic": topic}},
    )


@pytest.mark.parametrize(
    "topic",
    sorted(
        {
            topic
            for workflow in WORKFLOW_DETAILS.values()
            for topic in workflow["guidance"]
        }
    ),
)
def test_every_advertised_topic_is_readable(pilot, topic):
    result = guidance(pilot, topic)
    assert not result.get("isError"), result
    assert result["content"][0]["text"]


@pytest.mark.parametrize(
    "canonical,alias", [("manim", "manim-video"), ("motion", "motion-design")]
)
def test_aliases_return_same_compact_runtime_contract(pilot, canonical, alias):
    first = guidance(pilot, canonical)["content"][0]["text"]
    assert first == guidance(pilot, alias)["content"][0]["text"]
    # Enough room for useful guidance, but not the old 60KB recursive local skill.
    assert len(first.encode()) < 9000
    overview = guidance(pilot, "overview")["content"][0]["text"]
    assert len((first + overview).encode()) < 18000
    assert "show_video_preview" in first and "preview_path" in overview


def test_detailed_references_remain_available_without_path_escape(pilot):
    detailed = guidance(pilot, "skills/manim-video/references/equations.md")
    assert not detailed.get("isError")
    escaped = guidance(pilot, "../video-use/SKILL.md")
    assert escaped.get("isError")


@pytest.mark.parametrize("topic", ["overview", "scenes", "motion", "manim"])
def test_served_compact_guides_preserve_explicit_intake_and_sample_review(pilot, topic):
    """Technique guidance must not override the product's requested interaction."""
    result = guidance(pilot, topic)
    assert not result.get("isError"), result
    text = result["content"][0]["text"]
    for concept in (
        "start_video",
        "Hands off",
        "Key moments",
        "Hands on",
        "duration",
        "destination",
        "Legacy",
        "show_video_checkpoint",
        'production_stage="excerpt"',
        "full_video",
    ):
        assert concept in text, (topic, concept)
    for obsolete_rule in (
        "one optional brief question can ask how involved",
        "The unanswered default is `key_moments`",
        "there is no required\napproval pause",
        "Continue\nwithout mandatory approval",
        "It is not a required approval checkpoint",
        "Display each substantial draft immediately",
    ):
        assert obsolete_rule not in text, (topic, obsolete_rule)


@pytest.mark.parametrize(
    "topic", ["overview", "workflows", "scenes", "motion", "manim"]
)
def test_served_guides_keep_questions_in_native_tools_or_normal_chat(pilot, topic):
    result = guidance(pilot, topic)
    assert not result.get("isError"), result
    text = " ".join(result["content"][0]["text"].split())
    assert "native question tool if available" in text
    assert "normal chat" in text
    assert "show_video_brief" in text and "repeat" in text
    assert "show_video_checkpoint" in text and "second card" in text
    for obsolete_surface in (
        "Questions can use the implemented brief widget",
        "show_video_story`: editable scene cards",
        "show_video_brief`: 1–3 tailored questions",
    ):
        assert obsolete_surface not in text


def test_overview_keeps_internal_plan_and_irrelevant_quota_out_of_conversation(pilot):
    text = " ".join(guidance(pilot, "overview")["content"][0]["text"].split())
    assert (
        "Keep IDs, revisions, JSON and technical EDLs out of user-facing questions"
        in text
    )
    assert "show_video_story`: saves the story and script internally" in text
    assert "Check speech capacity only when narration is requested or needed" in text
    assert (
        "Never silently change audio or visual direction while the mode answer is pending"
        in text
    )
