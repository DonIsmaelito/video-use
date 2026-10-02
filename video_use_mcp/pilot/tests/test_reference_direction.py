"""Real MCP reference choices persist explicit direction without an app or spend."""

from copy import deepcopy
import json

import pytest

from video_use_mcp.pilot import reference_sources
from video_use_mcp.pilot.intake import intake_context
from video_use_mcp.pilot.reference_direction import Reference, reference_context
from video_use_mcp.pilot.runtime import require_production_intake
from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_workflow import call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "references.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "sources": [
                    {
                        "id": "example",
                        "name": "Examples",
                        "url": "https://example.com/collection",
                        "categories": ["explainer"],
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(reference_sources, "REGISTRY", path)
    return path


@pytest.fixture
def project(pilot, registry):
    data = call(
        pilot,
        "start_video",
        dict(
            title="Moon",
            brief="Explain the Moon",
            category="explainer",
            output_profile={"duration_seconds": 30, "viewing_destination": "YouTube"},
        ),
    )
    call(
        pilot,
        "record_video_answers",
        data["question"]["record_with"]["arguments"]
        | dict(
            request_id="mode",
            user_message="Hands on",
            answers={"involvement": "hands_on"},
        ),
    )
    return data["project_id"]


def saved(pilot, project):
    return deepcopy(pilot[1].state.store.get("creative", project))


def refs():
    return [
        dict(
            id="diagram",
            title="Diagram motion",
            url="https://artist.example/diagram",
            observed_traits="Lines reveal the orbit before labels appear",
            inspection="video",
            source_id="example",
            discovery_url="https://example.com/collection/diagram",
        ),
        dict(
            id="editorial",
            title="Editorial stills",
            url="https://artist.example/editorial",
            observed_traits="Warm paper and restrained serif typography",
            inspection="image",
            source_id="example",
            discovery_url="https://example.com/collection/editorial",
        ),
    ]


def args(pilot, project, action="offer", **updates):
    return (
        dict(
            project_id=project,
            creative_revision=saved(pilot, project)["revision"],
            request_id="request-" + action,
            action=action,
        )
        | updates
    )


def invoke(pilot, project, action="offer", **updates):
    return call(
        pilot, "record_video_references", args(pilot, project, action, **updates)
    )


def failure(pilot, parameters):
    result = rpc(
        pilot, "tools/call", dict(name="record_video_references", arguments=parameters)
    )
    assert result.get("isError"), result
    return result["content"][0]["text"]


def test_rejected_delegated_direction_survives_first_reference_offer(pilot, project):
    invoke(
        pilot,
        project,
        action="delegate",
        request_id="delegate-first",
        user_message="You decide, try a bright look",
        direction="Bright neon typography",
    )
    invoke(
        pilot,
        project,
        action="refine",
        request_id="reject-delegated",
        user_message="No, avoid neon",
        direction="Keep it bright with natural colors",
    )
    offered = invoke(pilot, project, references=refs(), request_id="first-search")
    feedback = offered["reference_direction"]["recent_feedback"]
    assert feedback[0]["events"][0]["user_message"] == "No, avoid neon"
    assert feedback[0]["previous_selection"]["direction"] == "Bright neon typography"
    assert offered["reference_direction"]["status"] == "offered"
    with pytest.raises(ValueError, match="intake choices"):
        require_production_intake(
            saved(pilot, project), "step", {"production_stage": "excerpt"}
        )


def test_offered_references_have_no_custom_app_and_never_approve_production(
    pilot, project
):
    assert intake_context(saved(pilot, project))["phase"] == "references"
    tools = {t["name"]: t for t in rpc(pilot, "tools/list", {})["tools"]}
    tool = tools["record_video_references"]
    assert "ui" not in tool.get("_meta", {})
    assert "openai/outputTemplate" not in tool.get("_meta", {})
    result = invoke(pilot, project, references=refs())
    context = result["reference_direction"]
    assert context["status"] == "offered"
    assert context["presenter"] == "host"
    assert context["inspection_provenance"] == "assistant_reported_not_server_verified"
    assert [ref["inspection"] for ref in context["references"]] == ["video", "image"]
    assert context["selected_ids"] == []
    assert "custom form" in context["next_action"]
    assert "source_catalog" in context
    assert (
        "widget" not in result and "receipts" not in context and "rounds" not in context
    )
    state = saved(pilot, project)
    for op, payload in [
        ("narrate", {}),
        ("export", {}),
        ("step", {"production_stage": "excerpt"}),
    ]:
        with pytest.raises(ValueError):
            require_production_intake(state, op, payload)
    queries = [item.args[0] for item in pilot[1].state.store.sql.call_args_list]
    assert not any(
        "vp_reserve" in query or "INSERT INTO public.vp_tasks" in query
        for query in queries
    )


def test_explicit_selection_preserves_traits_but_requires_excerpt_review(
    pilot, project
):
    invoke(pilot, project, references=refs())
    result = invoke(
        pilot,
        project,
        "select",
        selected_ids=["diagram", "editorial"],
        direction="Orbit diagrams on warm paper",
        user_message="Use the orbit animation and the second one's typography",
    )
    context = result["reference_direction"]
    assert context["status"] == "accepted"
    assert context["direction"] == "Orbit diagrams on warm paper"
    assert context["decision_source"] == "assistant_reported_user"
    assert [ref["id"] for ref in context["selected_references"]] == [
        "diagram",
        "editorial",
    ]
    state = saved(pilot, project)
    assert state["intake"]["excerpt_review"] == {"status": "not_requested"}
    assert intake_context(state)["phase"] == "excerpt_review"
    require_production_intake(state, "narrate", {})
    require_production_intake(state, "step", {"production_stage": "excerpt"})
    with pytest.raises(ValueError):
        require_production_intake(state, "step", {"production_stage": "full_video"})


def test_refinement_keeps_rejections_likes_and_prior_selection_across_search_rounds(
    pilot, project
):
    invoke(pilot, project, references=refs())
    invoke(
        pilot,
        project,
        "select",
        selected_ids=["editorial"],
        user_message="I like the type",
        direction="Serif type",
    )
    invoke(pilot, project, "refine", user_message="But this feels too corporate")
    result = invoke(
        pilot,
        project,
        "refine",
        request_id="clarification",
        user_message="Keep the typography, add more playful movement",
    )
    context = result["reference_direction"]
    assert context["status"] == "refining"
    assert "focused contrast question" in context["next_action"]
    feedback = context["recent_feedback"][0]
    assert [event["user_message"] for event in feedback["events"]] == [
        "But this feels too corporate",
        "Keep the typography, add more playful movement",
    ]
    assert feedback["previous_selection"]["direction"] == "Serif type"
    assert feedback["references"][0]["url"] == refs()[0]["url"]
    with pytest.raises(ValueError):
        require_production_intake(saved(pilot, project), "narrate", {})
    replacements = [
        dict(ref, id=ref["id"] + "2", url=ref["url"] + "2") for ref in refs()
    ]
    next_offer = invoke(pilot, project, references=replacements, request_id="new-round")
    assert (
        next_offer["reference_direction"]["recent_feedback"]
        == context["recent_feedback"]
    )
    failure(
        pilot,
        args(
            pilot,
            project,
            "select",
            selected_ids=["editorial"],
            user_message="Choose the old one",
        ),
    )


def test_retry_is_exact_and_does_not_erase_later_excerpt_approval(pilot, project):
    offer_args = args(pilot, project, references=refs())
    first = call(pilot, "record_video_references", offer_args)
    repeated = call(pilot, "record_video_references", offer_args)
    assert (
        repeated["repeated"]
        and repeated["creative_revision"] == first["creative_revision"]
    )
    assert (
        repeated["reference_direction"]["round_id"]
        == first["reference_direction"]["round_id"]
    )
    select_args = args(
        pilot,
        project,
        "select",
        selected_ids=["diagram"],
        user_message="Use the diagram",
    )
    call(pilot, "record_video_references", select_args)
    state = saved(pilot, project)
    state["revision"] += 1
    state["intake"]["excerpt_review"] = {
        "status": "approved",
        "object_id": "reviewed-video",
    }
    pilot[1].state.store.put("creative", project, state)
    retry = call(pilot, "record_video_references", select_args)
    assert retry["repeated"] and retry["creative_revision"] == state["revision"]
    assert saved(pilot, project) == state
    assert "different reference action" in failure(
        pilot, select_args | {"user_message": "Choose something else"}
    )
    assert "Creative direction changed" in failure(
        pilot, select_args | {"request_id": "stale"}
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"selected_ids": ["missing"], "user_message": "Use this"},
        {"selected_ids": ["diagram", "diagram"], "user_message": "Use this"},
        {"selected_ids": [], "user_message": "Use this"},
        {"selected_ids": ["diagram"], "user_message": " "},
    ],
)
def test_invalid_or_inferred_selection_never_mutates(pilot, project, changes):
    invoke(pilot, project, references=refs())
    before = saved(pilot, project)
    failure(pilot, args(pilot, project, "select", **changes))
    assert saved(pilot, project) == before


def test_empty_catalog_requires_user_reference_or_explicit_delegation(
    pilot, project, registry
):
    registry.write_text('{"version":1,"sources":[]}')
    assert (
        reference_context(saved(pilot, project))["source_catalog"]["status"]
        == "awaiting_curation"
    )
    assert "curated" in failure(pilot, args(pilot, project, references=refs()))
    assert "explicit reply" in failure(pilot, args(pilot, project, "delegate"))
    result = invoke(
        pilot,
        project,
        "delegate",
        user_message="Skip the search and use my blue diagrams",
        direction="Blue diagrams",
    )
    assert result["reference_direction"]["status"] == "delegated"
    assert result["reference_direction"]["decision_source"] == "assistant_reported_user"
    require_production_intake(
        saved(pilot, project), "step", {"production_stage": "excerpt"}
    )


def test_single_user_reference_allowed_without_curated_source(pilot, project, registry):
    registry.write_text('{"version":1,"sources":[]}')
    supplied = [dict(refs()[0], source="user_supplied", source_id="", discovery_url="")]
    result = invoke(pilot, project, references=supplied)
    assert len(result["reference_direction"]["references"]) == 1
    assert result["reference_direction"]["status"] == "offered"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/plain,hello",
        "file:///etc/passwd",
        "https://localhost/image",
        "http://127.0.0.1/a",
        "http://127.1/a",
        "http://[::1]/a",
        "http://10.0.0.1/a",
        "http://169.254.169.254/a",
        "https://host.local/a",
        "https://host.internal/a",
        "https://a.invalid/a",
        "https://user:password@example.com/a",
        "https://example.com:8080/a",
        "https://example.com\\@localhost/a",
        "https://example.com/\nsecret",
        "https://%31%32%37.0.0.1/a",
    ],
)
def test_reference_urls_reject_nonpublic_locations_or_credentials(url):
    with pytest.raises(ValueError):
        Reference.model_validate(dict(refs()[0], url=url))


@pytest.mark.parametrize(
    "change",
    [
        {"pending_style": True},
        {"pending_questions": {"answered": False}},
        {"output_profile": {}},
        {"mode": "key_moments"},
        {"mode": "delegate"},
    ],
)
def test_pending_intake_and_other_modes_cannot_be_overwritten(pilot, project, change):
    state = saved(pilot, project)
    state["intake"].update(change)
    pilot[1].state.store.put("creative", project, state)
    failure(pilot, args(pilot, project, references=refs()))
    assert saved(pilot, project) == state


def test_ownership_is_checked_even_for_retry(pilot, project):
    parameters = args(pilot, project, references=refs())
    call(pilot, "record_video_references", parameters)
    state = saved(pilot, project)
    pilot[1].state.store.project.side_effect = PermissionError("Not your project")
    assert "Not your project" in failure(pilot, parameters)
    assert saved(pilot, project) == state


def test_legacy_reads_unchanged_and_explicit_hands_on_call_can_opt_in(pilot, project):
    state = saved(pilot, project)
    state["intake"].pop("reference_direction")
    state["intake"]["excerpt_review"] = {"status": "approved"}
    pilot[1].state.store.put("creative", project, state)
    assert reference_context(state) is None
    assert intake_context(state)["phase"] == "production"
    invoke(pilot, project, references=refs())
    state = saved(pilot, project)
    assert state["intake"]["reference_direction"]["version"] == 1
    assert state["intake"]["excerpt_review"] == {"status": "not_requested"}
    assert intake_context(state)["phase"] == "references"


def test_full_legacy_project_is_not_silently_opted_in(pilot, project):
    state = saved(pilot, project)
    state.pop("intake")
    pilot[1].state.store.put("creative", project, state)
    failure(pilot, args(pilot, project, references=refs()))
    assert saved(pilot, project) == state


def test_private_history_is_bounded_and_context_has_no_receipts(pilot, project):
    for index in range(8):
        invoke(pilot, project, references=refs(), request_id=f"offer-{index}")
        invoke(
            pilot,
            project,
            "refine",
            user_message=f"Try variation {index}",
            request_id=f"reject-{index}",
        )
    state = saved(pilot, project)
    assert len(state["intake"]["reference_direction"]["rounds"]) == 6
    context = reference_context(state)
    assert len(context["recent_feedback"]) == 3
    assert "receipts" not in json.dumps(context)
    assert "digest" not in json.dumps(context)
