"""Creation technique is chosen before reference research, using native questions."""

from copy import deepcopy

import pytest

from video_use_mcp.pilot.intake import intake_context, initialize_intake
from video_use_mcp.pilot.runtime import require_production_intake
from video_use_mcp.pilot.tests.test_intake_flow import answer, error, start, state
from video_use_mcp.pilot.tests.test_workflow import call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def begin(pilot, **extra):
    initial = call(
        pilot,
        "start_video",
        dict(
            title="Life in 2050",
            brief="Make me a cool video about what life might look like in 2050",
            category="custom",
            output_profile={"duration_seconds": 30, "viewing_destination": "YouTube"},
        )
        | extra,
    )
    return answer(pilot, initial, {"involvement": "hands_on"})


def prepare(pilot, data):
    tool = data["intake"]["next_tool"]
    return call(pilot, tool["name"], tool["arguments"])


def test_broad_hands_on_asks_approach_after_only_missing_basics(pilot):
    first = start(pilot, {"duration_seconds": 30})
    mode = answer(pilot, first, {"involvement": "hands_on"})
    basics = prepare(pilot, mode)
    choice = answer(pilot, basics, {"viewing_destination": "landscape"})
    assert choice["intake"]["phase"] == "approach"
    pid = first["project_id"]
    with pytest.raises(ValueError, match="intake"):
        require_production_intake(
            state(pilot, pid), "step", {"production_stage": "excerpt"}
        )
    question = prepare(pilot, choice)
    assert "widget" not in question
    offered = question["question"]["questions"][0]
    assert offered["id"] == "creation_approach"
    assert [o["id"] for o in offered["options"]] == [
        "motion_design",
        "diagram_animation",
        "cinematic",
        "you_decide",
    ]
    assert not offered["recommended"]
    assert not question["question"]["recorded_answers"]
    assert (
        intake_context(state(pilot, pid), pid)["question"]["presentation_key"]
        == question["question"]["presentation_key"]
    )
    chosen = answer(pilot, question, {"creation_approach": "cinematic"})
    assert chosen["intake"]["phase"] == "references"
    assert chosen["intake"]["creation_approach"]["id"] == "cinematic"
    assert chosen["intake"]["creation_approach"]["source"] == "assistant_reported_user"
    assert (
        state(pilot, pid)["category"] == "explainer"
    )  # Content classification stays separate.
    assert "saved creation_approach" in chosen["next_action"]
    repeated = answer(pilot, question, {"creation_approach": "cinematic"})
    assert (
        repeated["repeated"]
        and repeated["creative_revision"] == chosen["creative_revision"]
    )


def test_explicit_technique_is_preserved_without_repeat_question(pilot):
    result = begin(pilot, creation_approach="Manim animation")
    assert result["intake"]["phase"] == "references"
    assert result["intake"]["creation_approach"]["label"] == "Manim animation"
    pid = result["project_id"]
    updated = call(
        pilot,
        "start_video",
        dict(
            project_id=pid, title="Future life", brief="Life in 2050", category="custom"
        ),
    )
    assert (
        updated["intake"]["creation_approach"] == result["intake"]["creation_approach"]
    )


def test_host_can_tailor_approaches_and_user_can_give_unlisted_direction(pilot):
    result = begin(pilot)
    tailored = call(
        pilot,
        "show_video_brief",
        dict(
            project_id=result["project_id"],
            creative_revision=result["creative_revision"],
            questions=[
                dict(
                    id="creation_approach",
                    prompt="How should this future feel on screen?",
                    options=[
                        dict(id="collage", label="Editorial collage"),
                        dict(id="miniatures", label="3D miniatures"),
                        dict(id="you_decide", label="You decide"),
                    ],
                )
            ],
        ),
    )
    chosen = call(
        pilot,
        "record_video_answers",
        tailored["question"]["record_with"]["arguments"]
        | dict(
            request_id="custom-style",
            user_message="A mixed-media documentary with real city clips",
            text_answers={
                "creation_approach": "A mixed-media documentary with real city clips"
            },
        ),
    )
    assert chosen["intake"]["phase"] == "references"
    approach = chosen["intake"]["creation_approach"]
    assert approach["id"] == "user_described"
    assert approach["label"] == "A mixed-media documentary with real city clips"
    assert approach["user_message"] == approach["label"]


def test_approach_delegation_is_explicit_and_does_not_skip_references(pilot):
    question = prepare(pilot, begin(pilot))
    chosen = answer(pilot, question, {"creation_approach": "you_decide"})
    assert chosen["intake"]["phase"] == "references"
    assert chosen["intake"]["creation_approach"]["status"] == "delegated"


def test_approach_cannot_be_replaced_by_unrelated_question(pilot):
    result = begin(pilot)
    assert "creation_approach" in error(
        pilot,
        "show_video_brief",
        project_id=result["project_id"],
        creative_revision=result["creative_revision"],
        questions=[
            dict(
                id="tone",
                prompt="Tone?",
                options=[dict(id="fun", label="Fun"), dict(id="calm", label="Calm")],
            )
        ],
    )


@pytest.mark.parametrize("prior", ["legacy", "offered", "accepted", "excerpt"])
def test_existing_reference_and_snippet_projects_do_not_gain_new_gate(prior):
    current = initialize_intake(
        {"revision": 1}, {"duration_seconds": 30, "viewing_destination": "web"}
    )
    current["intake"]["mode"] = "hands_on"
    if prior == "legacy":
        current["intake"].pop("creation_approach")
    elif prior == "offered":
        current["intake"]["reference_direction"].update(
            status="needed", rounds=[{"id": "prior"}]
        )
    elif prior == "accepted":
        current["intake"]["reference_direction"].update(status="accepted")
    else:
        current["intake"]["excerpt_review"] = {
            "status": "pending",
            "object_id": "snippet",
        }
    before = deepcopy(current)
    assert intake_context(current)["phase"] != "approach"
    assert current == before


def test_known_source_category_gets_relevant_starting_types():
    current = initialize_intake(
        {"revision": 1, "category": "software_demo"},
        {"duration_seconds": 30, "viewing_destination": "web"},
    )
    current["intake"]["mode"] = "hands_on"
    offered = intake_context(current)["questions"][0]["options"]
    assert offered[0]["id"] == "screen_demo"
    assert "diagram_animation" not in {o["id"] for o in offered}


@pytest.mark.parametrize(
    "category,choice,qualification",
    [
        ("custom", "cinematic", "supplied footage"),
        ("software_demo", "screen_demo", "recording"),
        ("procedural_3d", "procedural_3d", "Procedural 3D"),
    ],
)
def test_conditional_approaches_stay_available_with_concise_prerequisites(
    category, choice, qualification
):
    current = initialize_intake(
        {"revision": 1, "category": category},
        {"duration_seconds": 30, "viewing_destination": "web"},
    )
    current["intake"]["mode"] = "hands_on"
    context = intake_context(current)
    assert context["phase"] == "approach"
    question = context["questions"][0]
    assert question["id"] == "creation_approach"
    choices = {option["id"]: option for option in question["options"]}
    assert qualification in choices[choice]["label"]
    assert "you_decide" in choices
    assert len(choices[choice]["label"]) < 60
    # Requirements are model guidance, not extra controls or a second question.
    assert len(context["questions"]) == 1
    assert set(choices[choice]) == {"id", "label"}
    for requirement in (
        "video_use_capabilities",
        "supplied or licensed footage",
        "screen demos need a recording",
        "Three.js or Manim",
        "not Blender",
        "Keep these options available",
    ):
        assert requirement in context["next_action"]
