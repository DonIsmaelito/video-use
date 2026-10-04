"""The example-library handoff preserves real user decisions and snippet gates."""

from copy import deepcopy

import pytest

from video_use_mcp.pilot.example_library import example_library_context
from video_use_mcp.pilot.intake import intake_context, initialize_intake
from video_use_mcp.pilot.runtime import require_production_intake
from video_use_mcp.pilot.tests.test_creation_approach import begin, prepare
from video_use_mcp.pilot.tests.test_intake_flow import answer, state
from video_use_mcp.pilot.tests.test_workflow import call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_library_appears_after_approach_without_approving_anything(pilot):
    initial = begin(pilot)
    assert "example_library" not in initial["intake"]
    chosen = answer(pilot, prepare(pilot, initial), {"creation_approach": "procedural_3d"})
    library = chosen["intake"]["example_library"]
    assert library["url"] == "https://video-use.insforge.site?technique=3d"
    assert library["optional"] is True
    assert chosen["intake"]["phase"] == "references"
    current = state(pilot, chosen["project_id"])
    before = deepcopy(current)
    repeated = intake_context(current, chosen["project_id"])
    assert repeated["example_library"]["presentation_key"] == library["presentation_key"]
    assert current == before
    with pytest.raises(ValueError, match="intake"):
        require_production_intake(current, "step", {"production_stage": "excerpt"})


@pytest.mark.parametrize("approach", ["you_decide", "user_described", "unrecognized"])
def test_unmapped_approaches_do_not_invent_a_filter(approach):
    data = {"creation_approach": {"id": approach, "status": "selected"}}
    assert example_library_context(data)["url"] == "https://video-use.insforge.site"


def test_hands_off_does_not_gain_a_library_detour():
    current = initialize_intake(
        {"revision": 1},
        {"duration_seconds": 20, "viewing_destination": "web"},
        creation_approach="motion design",
    )
    current["intake"]["mode"] = "delegate"
    context = intake_context(current)
    assert context["phase"] == "production"
    assert "example_library" not in context


def test_pasted_workflow_can_skip_research_but_not_snippet_approval(pilot):
    initial = begin(pilot, creation_approach="motion design")
    message = (
        "Use this workflow as my creative direction and adapt it to our coffee brand. "
        "Skip searching for other reference videos. Show me a short snippet first."
    )
    chosen = call(
        pilot,
        "record_video_references",
        {
            "project_id": initial["project_id"],
            "creative_revision": initial["creative_revision"],
            "request_id": "chosen-library-workflow",
            "action": "delegate",
            "direction": "Adapt the chosen product launch workflow to our coffee brand",
            "user_message": message,
        },
    )
    assert not chosen.get("isError"), chosen
    current = state(pilot, initial["project_id"])
    assert current["intake"]["reference_direction"]["user_message"] == message
    assert intake_context(current)["phase"] == "excerpt_review"
    require_production_intake(current, "step", {"production_stage": "excerpt"})
    with pytest.raises(ValueError, match="excerpt acceptance"):
        require_production_intake(current, "step", {"production_stage": "full_video"})
