"""Exercise the requested native conversation sequence through actual MCP tools.

Cloud rendering is represented by a persisted published clip. This tests the
conversation and production gates, not Claude's host UI or creative judgment.
"""

import pytest

from video_use_mcp.pilot.intake import intake_context
from video_use_mcp.pilot.runtime import require_production_intake
from video_use_mcp.pilot.tests.test_intake_flow import (
    answer,
    error,
    publish,
    start,
    state,
)
from video_use_mcp.pilot.tests.test_reference_direction import (
    registry as registry,
    refs,
    research,
)
from video_use_mcp.pilot.tests.test_workflow import call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


@pytest.mark.usefixtures("registry")
def test_native_references_then_reviewed_snippet_then_full_video(pilot):
    first = start(pilot, {"duration_seconds": 30})
    pid = first["project_id"]
    assert first["question"]["required"] == ["involvement"]
    selected = answer(pilot, first, {"involvement": "hands_on"})
    tool = selected["intake"]["next_tool"]
    basics = call(pilot, tool["name"], tool["arguments"])
    assert basics["question"]["required"] == ["viewing_destination"]
    ready = answer(pilot, basics, {"viewing_destination": "landscape"})
    assert ready["intake"]["phase"] == "approach"
    tool = ready["intake"]["next_tool"]
    approach = call(pilot, tool["name"], tool["arguments"])
    assert approach["question"]["required"] == ["creation_approach"]
    ready = answer(pilot, approach, {"creation_approach": "diagram_animation"})
    assert ready["intake"]["phase"] == "references"
    assert ready["intake"]["creation_approach"]["id"] == "diagram_animation"

    references = [
        dict(
            refs()[0],
            id=f"choice-{i}",
            title=f"Direction {i + 1}",
            url=f"https://artist.example/film-{i}",
            discovery_url=f"https://example.com/collection/film-{i}",
        )
        for i in range(5)
    ]
    offered = call(
        pilot,
        "record_video_references",
        dict(
            project_id=pid,
            creative_revision=ready["creative_revision"],
            request_id="offer",
            action="offer",
            references=references,
            search=research(references),
        ),
    )
    direction = offered["reference_direction"]
    assert [c["url"] for c in direction["link_cards"]] == [r["url"] for r in references]
    question = direction["question"]
    options = question["questions"][0]["options"]
    assert len(options) == 7 and options[-1]["input"] == "text"
    assert options[-2]["label"] == "Find another batch"
    recovered = intake_context(state(pilot, pid), pid)
    assert recovered["question"]["presentation_key"] == question["presentation_key"]
    assert recovered["question"]["questions"] == question["questions"]
    with pytest.raises(ValueError):
        require_production_intake(
            state(pilot, pid), "step", {"production_stage": "excerpt"}
        )

    choose = options[2]["record_with"]
    chosen = call(
        pilot,
        choose["name"],
        choose["arguments"]
        | dict(
            request_id="choose-third",
            user_message="The third one, especially the clean lines",
            direction="Use the third reference's clean line work for the rain explanation",
        ),
    )
    assert intake_context(state(pilot, pid))["phase"] == "excerpt_review"
    assert chosen["reference_direction"]["selected_ids"] == ["choice-2"]
    assert "question" not in chosen["reference_direction"]
    require_production_intake(
        state(pilot, pid), "step", {"production_stage": "excerpt"}
    )
    with pytest.raises(ValueError):
        require_production_intake(
            state(pilot, pid), "step", {"production_stage": "full_video"}
        )

    publish(pilot, pid)
    preview = call(pilot, "show_video_preview", {"project_id": pid})
    tool = preview["next_tool"]
    review = call(pilot, tool["name"], tool["arguments"])
    assert "widget" not in review
    assert review["question"]["media_object_id"] == "sample"
    refined = call(
        pilot,
        "record_video_answers",
        review["question"]["record_with"]["arguments"]
        | dict(
            request_id="refine",
            user_message="Slow down the cloud forming",
            answers={"excerpt_review": "refine"},
        ),
    )
    assert (
        refined["intake"]["excerpt_review"]["user_message"]
        == "Slow down the cloud forming"
    )
    repeated = call(
        pilot,
        "record_video_answers",
        review["question"]["record_with"]["arguments"]
        | dict(
            request_id="refine",
            user_message="Slow down the cloud forming",
            answers={"excerpt_review": "refine"},
        ),
    )
    assert (
        repeated["repeated"]
        and repeated["creative_revision"] == refined["creative_revision"]
    )
    assert "different changes" in error(
        pilot,
        "record_video_answers",
        **(
            review["question"]["record_with"]["arguments"]
            | dict(
                request_id="refine",
                user_message="Speed up the cloud forming",
                answers={"excerpt_review": "refine"},
            )
        ),
    )
    assert (
        state(pilot, pid)["intake"]["excerpt_review"]["user_message"]
        == "Slow down the cloud forming"
    )
    with pytest.raises(ValueError):
        require_production_intake(state(pilot, pid), "export", {})

    publish(pilot, pid, "slower-sample")
    review = call(
        pilot,
        "show_video_checkpoint",
        dict(
            project_id=pid,
            creative_revision=refined["creative_revision"],
            object_id="slower-sample",
        ),
    )
    approved = answer(
        pilot, review, {"excerpt_review": "continue"}, request_id="approve"
    )
    assert approved["intake"]["phase"] == "production"
    assert approved["intake"]["excerpt_review"]["object_id"] == "slower-sample"
    assert state(pilot, pid)["intake"]["reference_direction"]["selected_ids"] == [
        "choice-2"
    ]
    require_production_intake(
        state(pilot, pid), "step", {"production_stage": "full_video"}
    )
    require_production_intake(state(pilot, pid), "export", {})

    assert not any(
        "widget" in result
        for result in [first, basics, offered, chosen, review, approved]
    )
    assert set(state(pilot, pid)["widgets"]) == {"brief"}
