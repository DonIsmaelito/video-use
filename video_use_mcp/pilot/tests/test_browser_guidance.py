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
