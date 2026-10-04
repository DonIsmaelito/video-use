"""Real MCP reference choices persist explicit direction without an app or spend."""

from copy import deepcopy
import hashlib
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
            creation_approach="Manim diagrams",
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


def mark_downloaded(state):
    """Emulate verified acquisition when testing later conversation checkpoints."""
    direction = state["intake"]["reference_direction"]
    for ref in direction["selected_references"]:
        direction["clone"]["media"][ref["id"]] = dict(source={"path": "sources/reference.mp4"}, metadata={"sha256": "verified"})
    return state


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


def many_refs(count, offset=0):
    return [
        dict(
            refs()[index % 2],
            id=f"reference-{index}",
            title=f"Reference {index + 1}",
            url=f"https://artist.example/reference-{index}",
            discovery_url=f"https://example.com/collection/reference-{index}",
        )
        for index in range(offset, offset + count)
    ]


def args(pilot, project, action="offer", **updates):
    search = {}
    if action in {"offer", "append"} and updates.get("references"):
        search = {"search": research(updates["references"])}
    return (
        dict(
            project_id=project,
            creative_revision=saved(pilot, project)["revision"],
            request_id="request-" + action,
            action=action,
        )
        | search
        | updates
    )


def research(references):
    return dict(
        search_intent="Compare ways to explain lunar phases with readable geometry",
        search_queries=["orbital diagram motion", "editorial astronomy animation"],
        candidates=[
            dict(
                reference=reference,
                evidence_note=(
                    "Inspected the opening excerpt showing the orbit reveal"
                    if reference["inspection"] == "video"
                    else "Inspected the project image, not playback"
                ),
                fit="Readable lunar geometry with room for labels",
                limitations="Adapt to this audience; references do not verify lunar facts",
                disposition="recommend",
            )
            for reference in references
        ],
        selection_reason="Contrast diagram-led motion with editorial typography",
        coverage_limitations="Small relevant sample, not an exhaustive search",
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


def test_five_real_references_have_link_cards_and_native_choice_with_final_input(
    pilot, project
):
    references = many_refs(5)
    parameters = args(pilot, project, references=references)
    result = call(pilot, "record_video_references", parameters)
    context = result["reference_direction"]
    assert (
        context["link_presentation"]
        == "native_link_preview_if_available_else_markdown_link"
    )
    assert [card["url"] for card in context["link_cards"]] == [
        item["url"] for item in references
    ]
    assert [card["title"] for card in context["link_cards"]] == [
        item["title"] for item in references
    ]
    question = context["question"]
    assert (
        question["presentation"] == "native_question_tool_if_available_else_short_chat"
    )
    assert question["status"] == "awaiting_user"
    assert len(question["questions"]) == 1
    options = question["questions"][0]["options"]
    assert [item["reference_id"] for item in options[:-2]] == [
        item["id"] for item in references
    ]
    for reference, option in zip(references, options[:-2], strict=True):
        assert option["record_with"] == {
            "name": "record_video_references",
            "arguments": {
                "project_id": project,
                "creative_revision": result["creative_revision"],
                "action": "select",
                "round_id": context["round_id"],
                "selected_ids": [reference["id"]],
            },
        }
    assert options[-1]["input"] == "text"
    assert options[-1]["label"] == "Give my input"
    assert options[-1]["record_with"]["arguments"]["action"] == "refine"
    assert not any("recommended" in option for option in options)
    assert "default" not in question
    assert "widget" not in result
    assert "_meta" not in question
    repeated = call(pilot, "record_video_references", parameters)
    assert repeated["reference_direction"]["question"] == question
    assert reference_context(saved(pilot, project), project)["question"] == question


def test_six_reference_offer_and_selection_are_rejected_without_mutation(
    pilot, project
):
    before = saved(pilot, project)
    assert "at most five" in failure(
        pilot, args(pilot, project, references=many_refs(6))
    )
    assert saved(pilot, project) == before
    invoke(pilot, project, references=many_refs(5))
    before = saved(pilot, project)
    assert "at most five" in failure(
        pilot,
        args(
            pilot,
            project,
            "select",
            selected_ids=[f"reference-{index}" for index in range(6)],
            user_message="Combine them",
        ),
    )
    assert saved(pilot, project) == before


def test_reference_cards_stay_compact_without_losing_full_inspection_notes(
    pilot, project
):
    reference = many_refs(1)[0]
    reference["title"] = "Reference with a detailed descriptive name " * 3
    reference["observed_traits"] = (
        "Large warm shapes move around readable scene labels. " * 18
    )
    offered = invoke(pilot, project, references=[reference])["reference_direction"]
    card = offered["link_cards"][0]
    option = offered["question"]["questions"][0]["options"][0]
    assert len(card["description"]) <= 240
    assert len(option["label"]) <= 80
    assert card["title"] == reference["title"].strip()
    assert (
        offered["references"][0]["observed_traits"]
        == reference["observed_traits"].strip()
    )
    assert option["reference_id"] == reference["id"]


def test_one_fresh_reference_is_enough_and_empty_offer_does_not_meet_quota(
    pilot, project
):
    before = saved(pilot, project)
    assert "1–5 actual references" in failure(
        pilot, args(pilot, project, references=[])
    )
    assert saved(pilot, project) == before
    result = invoke(pilot, project, references=many_refs(1))
    assert len(result["reference_direction"]["link_cards"]) == 1
    assert (
        len(result["reference_direction"]["question"]["questions"][0]["options"]) == 3
    )


def test_final_input_records_feedback_and_requires_a_new_reference_choice(
    pilot, project
):
    result = invoke(pilot, project, references=many_refs(5))
    question = result["reference_direction"]["question"]
    input_option = question["questions"][0]["options"][-1]
    feedback = call(
        pilot,
        input_option["record_with"]["name"],
        input_option["record_with"]["arguments"]
        | {
            "request_id": "real-feedback",
            "user_message": "None of these; I want a playful paper cutout look",
            "direction": "Playful paper cutout movement",
        },
    )
    context = feedback["reference_direction"]
    assert context["status"] == "refining"
    assert not context["selected_ids"]
    assert not context["selected_references"]
    assert "question" not in context
    assert context["recent_feedback"][0]["events"][-1]["user_message"] == (
        "None of these; I want a playful paper cutout look"
    )
    state = saved(pilot, project)
    assert state["intake"]["excerpt_review"] == {"status": "not_requested"}
    for payload in (
        {"production_stage": "excerpt"},
        {"production_stage": "full_video"},
    ):
        with pytest.raises(ValueError):
            require_production_intake(state, "step", payload)
    replacement = invoke(
        pilot, project, references=many_refs(1, offset=5), request_id="fresh-search"
    )
    assert (
        replacement["reference_direction"]["question"]["presentation_key"]
        != question["presentation_key"]
    )


def test_reference_summary_without_project_id_never_emits_incomplete_tool_call(
    pilot, project
):
    invoke(pilot, project, references=refs())
    question = reference_context(saved(pilot, project))["question"]
    assert all(
        "record_with" not in option for option in question["questions"][0]["options"]
    )


def test_native_reference_choice_unlocks_snippet_but_never_full_video(pilot, project):
    offered = invoke(pilot, project, references=many_refs(5))
    option = offered["reference_direction"]["question"]["questions"][0]["options"][4]
    call(
        pilot,
        option["record_with"]["name"],
        option["record_with"]["arguments"]
        | {"request_id": "choose-fifth", "user_message": "Reference 5"},
    )
    state = saved(pilot, project)
    assert intake_context(state)["phase"] == "excerpt_review"
    mark_downloaded(state)
    require_production_intake(state, "step", {"production_stage": "excerpt"})
    with pytest.raises(ValueError):
        require_production_intake(state, "step", {"production_stage": "full_video"})
    assert "question" not in reference_context(state, project)


@pytest.mark.parametrize(
    "change",
    [
        {"owner": "another-user"},
        {"project": "another-project"},
        {"page_url": "https://unrelated.example/film"},
    ],
)
def test_browser_evidence_must_belong_to_project_and_cited_page(pilot, project, change):
    store = pilot[1].state.store
    references = refs()
    references[0]["evidence_ids"] = ["capture"]
    store.put(
        "reference_browser_evidence",
        "capture",
        {
            "owner": "tester",
            "project": project,
            "page_url": references[0]["url"],
        }
        | change,
    )
    error = failure(pilot, args(pilot, project, references=references))
    assert "Reference evidence must" in error


def test_sampled_media_evidence_can_cite_its_server_recorded_source_page(
    pilot, project
):
    references = refs()
    references[0]["evidence_ids"] = ["capture"]
    pilot[1].state.store.put(
        "reference_browser_evidence",
        "capture",
        {
            "owner": "tester",
            "project": project,
            "page_url": "https://cdn.example/film.mp4",
            "source_page_url": references[0]["url"],
        },
    )
    result = invoke(pilot, project, references=references)
    assert result["reference_direction"]["references"][0]["evidence_ids"] == ["capture"]


def test_offered_source_thumbnail_uses_owned_observation_and_stays_separate_from_choice(
    pilot, project
):
    store = pilot[1].state.store
    reference = refs()[0] | {
        "playback": {
            "url": "https://media.ordinary.co/video/home/observed.webm",
            "browser_request_id": "source-inspection",
        }
    }
    key = hashlib.sha256(
        ("tester:" + project + ":source-inspection").encode()
    ).hexdigest()
    store.put(
        "reference_browser_run",
        key,
        {
            "owner": "tester",
            "project": project,
            "status": "complete",
            "result": {
                "engine": "browser-harness",
                "project_id": project,
                "results": [
                    {
                        "action": "read",
                        "ok": True,
                        "page_url": reference["url"],
                        "videos": [
                            {"src": reference["playback"]["url"], "duration_seconds": 5}
                        ],
                    }
                ],
            },
        },
    )
    result = invoke(pilot, project, references=[reference])
    descriptor = result["reference_direction"]["link_cards"][0]["show_video_reference"]
    assert descriptor == {
        "name": "show_video_reference",
        "arguments": {
            "project_id": project,
            "reference_id": reference["id"],
            "round_id": result["reference_direction"]["round_id"],
        },
    }
    before = saved(pilot, project)
    playback = call(pilot, descriptor["name"], descriptor["arguments"])
    assert playback["media"]["source_url"] == reference["url"]
    assert playback["media"]["reference_display"] == "thumbnail"
    assert "url" not in playback["media"] and "embed_url" not in playback["media"]
    assert playback["coverage"] == "source_link"
    assert playback["playback_status"] == "not_requested"
    assert saved(pilot, project) == before
    assert playback["follow_project"] is False
    assert result["reference_direction"]["status"] == "offered"


def test_offer_cannot_attach_an_unobserved_playback_url(pilot, project):
    reference = refs()[0] | {
        "playback": {
            "url": "https://media.ordinary.co/video/home/invented.webm",
            "browser_request_id": "unrecorded-inspection",
        }
    }
    before = saved(pilot, project)
    error = failure(pilot, args(pilot, project, references=[reference]))
    assert "completed browser request" in error
    assert saved(pilot, project) == before


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
    with pytest.raises(ValueError, match="Download the selected"):
        require_production_intake(state, "narrate", {})
    mark_downloaded(state)
    require_production_intake(state, "narrate", {})
    mark_downloaded(state)
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


def test_reference_offer_waits_for_the_creation_approach(pilot, project):
    state = saved(pilot, project)
    state["intake"]["creation_approach"] = {"version": 1, "status": "needed"}
    pilot[1].state.store.put("creative", project, state)
    assert intake_context(state)["phase"] == "approach"
    assert "video type" in failure(pilot, args(pilot, project, references=refs()))
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
        invoke(
            pilot,
            project,
            references=many_refs(2, offset=index * 2),
            request_id=f"offer-{index}",
        )
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


def test_comparison_records_rejected_candidates_without_bloating_context(
    pilot, project
):
    search = research(refs())
    rejected = deepcopy(search["candidates"][0])
    rejected["reference"].update(id="busy", url="https://artist.example/busy")
    rejected.update(
        disposition="reject", fit="Space theme", limitations="Labels too crowded"
    )
    search["candidates"].append(rejected)
    result = invoke(pilot, project, references=refs(), search=search)
    summary = result["reference_direction"]["search_summary"]
    assert summary["candidate_count"] == 3
    assert summary["search_queries"] == search["search_queries"]
    assert summary["selection_reason"] == search["selection_reason"]
    assert summary["recorded_at"]
    assert [item["id"] for item in summary["recommended_evidence"]] == [
        "diagram",
        "editorial",
    ]
    assert "candidates" not in summary
    stored = saved(pilot, project)["intake"]["reference_direction"]["rounds"][-1][
        "search"
    ]
    assert stored["candidates"][-1]["disposition"] == "reject"
    reloaded = call(pilot, "get_video_project", dict(project_id=project))
    resumed = reloaded["creative"]["intake"]["reference_direction"]["search_summary"]
    assert resumed["other_candidates"][0]["limitations"] == "Labels too crowded"
    assert resumed["selection_reason"] == search["selection_reason"]


def test_offer_requires_new_comparison_and_does_not_fill_from_registry(pilot, project):
    before = saved(pilot, project)
    assert "live search" in failure(
        pilot, args(pilot, project, references=refs(), search=None)
    )
    assert saved(pilot, project) == before
    invoke(pilot, project, references=refs())
    invoke(pilot, project, "refine", user_message="Use a less formal approach")
    before = saved(pilot, project)
    assert "live search" in failure(
        pilot,
        args(
            pilot,
            project,
            references=many_refs(1),
            search=None,
            request_id="new-search",
        ),
    )
    assert saved(pilot, project) == before


@pytest.mark.parametrize(
    "change", ["missing", "extra", "inspection", "provenance", "duplicate"]
)
def test_offer_and_candidate_comparison_must_agree(pilot, project, change):
    search = research(refs())
    if change == "missing":
        search["candidates"][0]["disposition"] = "reserve"
    elif change == "extra":
        other = deepcopy(search["candidates"][0])
        other["reference"].update(id="other", url="https://artist.example/other")
        search["candidates"].append(other)
    elif change == "inspection":
        search["candidates"][0]["reference"]["inspection"] = "page"
    elif change == "provenance":
        other = deepcopy(search["candidates"][0])
        other["reference"].update(
            id="other", url="https://artist.example/other", source_id="unapproved"
        )
        other["disposition"] = "reject"
        search["candidates"].append(other)
    else:
        search["candidates"].append(deepcopy(search["candidates"][0]))
    before = saved(pilot, project)
    failure(pilot, args(pilot, project, references=refs(), search=search))
    assert saved(pilot, project) == before


def test_comparison_is_part_of_exact_retry_and_cannot_change_on_selection(
    pilot, project
):
    parameters = args(pilot, project, references=refs())
    call(pilot, "record_video_references", parameters)
    before = saved(pilot, project)
    parameters["search"]["selection_reason"] = "A different comparison"
    assert "different reference action" in failure(pilot, parameters)
    assert "action offer or append only" in failure(
        pilot,
        args(
            pilot,
            project,
            "select",
            selected_ids=["diagram"],
            user_message="Choose the diagram",
            search=research(refs()),
        ),
    )
    assert saved(pilot, project) == before


def test_pre_search_receipt_retry_remains_idempotent(pilot, project):
    before = saved(pilot, project)
    references = [Reference.model_validate(item).model_dump() for item in refs()]
    payload = dict(
        creative_revision=before["revision"],
        action="offer",
        references=references,
        selected_ids=[],
        direction="",
        user_message="",
    )
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    before["revision"] += 1
    before["intake"]["reference_direction"].update(
        status="offered",
        rounds=[dict(id="old-round", references=references, status="offered")],
        receipts=[dict(request_id="old-request", digest=digest)],
    )
    pilot[1].state.store.put("creative", project, before)
    result = call(
        pilot,
        "record_video_references",
        dict(
            project_id=project,
            creative_revision=payload["creative_revision"],
            request_id="old-request",
            action="offer",
            references=references,
        ),
    )
    assert result["repeated"]
    assert result["reference_direction"]["search_summary"] is None
    assert saved(pilot, project) == before


def test_index_screening_is_not_recorded_as_page_or_video_inspection(pilot, project):
    search = research(refs())
    screened = deepcopy(search["candidates"][0])
    screened["reference"].update(
        id="index-only", url="https://artist.example/indexed", inspection="metadata"
    )
    screened.update(
        disposition="reject",
        evidence_note="Read search index synopsis only",
        limitations="Wrong audience; never opened or played",
    )
    search["candidates"].append(screened)
    invoke(pilot, project, references=refs(), search=search)
    stored = saved(pilot, project)["intake"]["reference_direction"]["rounds"][-1][
        "search"
    ]
    assert stored["candidates"][-1]["reference"]["inspection"] == "metadata"


def test_sequential_candidates_show_immediately_then_form_one_final_question(
    pilot, project
):
    first_args = args(pilot, project, references=many_refs(1), more_expected=True)
    first = call(pilot, "record_video_references", first_args)
    first_context = first["reference_direction"]
    round_id = first_context["round_id"]
    assert first_context["status"] == "collecting"
    assert "question" not in first_context
    assert first_context["new_reference_ids"] == ["reference-0"]
    assert len(first_context["new_link_cards"]) == 1
    assert (
        first_context["new_link_cards"][0]["show_video_reference"]["arguments"][
            "round_id"
        ]
        == round_id
    )
    presentation_key = first_context["link_cards"][0]["presentation_key"]
    with pytest.raises(ValueError):
        require_production_intake(
            saved(pilot, project), "step", {"production_stage": "excerpt"}
        )
    second_args = args(
        pilot,
        project,
        "append",
        references=many_refs(1, 1),
        round_id=round_id,
        more_expected=True,
    )
    second = call(pilot, "record_video_references", second_args)
    assert second["reference_direction"]["round_id"] == round_id
    assert second["reference_direction"]["status"] == "collecting"
    assert second["reference_direction"]["new_reference_ids"] == ["reference-1"]
    assert (
        second["reference_direction"]["link_cards"][0]["presentation_key"]
        == presentation_key
    )
    assert "question" not in second["reference_direction"]
    repeated = call(pilot, "record_video_references", second_args)
    assert repeated["repeated"]
    assert repeated["creative_revision"] == second["creative_revision"]
    assert repeated["reference_direction"]["new_reference_ids"] == ["reference-1"]
    final = invoke(
        pilot,
        project,
        "append",
        references=many_refs(1, 2),
        round_id=round_id,
        request_id="last-append",
    )
    context = final["reference_direction"]
    assert context["round_id"] == round_id and context["status"] == "offered"
    assert context["new_reference_ids"] == ["reference-2"]
    assert len(context["question"]["questions"][0]["options"]) == 5
    assert len(context["search_batches"]) == 3
    assert [batch["candidate_count"] for batch in context["search_batches"]] == [
        1,
        1,
        1,
    ]
    assert len(saved(pilot, project)["intake"]["reference_direction"]["rounds"]) == 1


def test_collection_can_finish_without_filler_and_finish_retry_is_exact(pilot, project):
    first = invoke(pilot, project, references=many_refs(1), more_expected=True)
    finish = first["reference_direction"]["finish_with"]
    parameters = finish["arguments"] | {"request_id": "finish-one"}
    complete = call(pilot, finish["name"], parameters)
    assert complete["reference_direction"]["status"] == "offered"
    assert complete["reference_direction"]["new_link_cards"] == []
    assert len(complete["reference_direction"]["references"]) == 1
    assert call(pilot, finish["name"], parameters)["repeated"]


@pytest.mark.parametrize(
    "change",
    [
        "missing-round",
        "stale-round",
        "duplicate-id",
        "duplicate-url",
        "overflow",
        "no-research",
        "different-retry",
    ],
)
def test_invalid_append_does_not_mutate_current_batch(pilot, project, change):
    first = invoke(pilot, project, references=many_refs(2), more_expected=True)
    round_id = first["reference_direction"]["round_id"]
    parameters = args(
        pilot,
        project,
        "append",
        references=many_refs(1, 2),
        round_id=round_id,
        more_expected=True,
    )
    if change == "missing-round":
        parameters.pop("round_id")
    elif change == "stale-round":
        parameters["round_id"] = "another-round"
    elif change in {"duplicate-id", "duplicate-url"}:
        field = "id" if change == "duplicate-id" else "url"
        parameters["references"][0][field] = many_refs(1)[0][field]
        parameters["search"] = research(parameters["references"])
    elif change == "overflow":
        parameters["references"] = many_refs(4, 2)
        parameters["search"] = research(parameters["references"])
    elif change == "no-research":
        parameters.pop("search")
    else:
        call(pilot, "record_video_references", parameters)
        parameters["more_expected"] = False
    before = saved(pilot, project)
    failure(pilot, parameters)
    assert saved(pilot, project) == before


def test_fifth_candidate_finishes_collection_and_forbids_sixth(pilot, project):
    first = invoke(pilot, project, references=many_refs(4), more_expected=True)
    round_id = first["reference_direction"]["round_id"]
    last = invoke(
        pilot,
        project,
        "append",
        references=many_refs(1, 4),
        round_id=round_id,
        more_expected=True,
    )
    assert last["reference_direction"]["status"] == "offered"
    assert len(last["reference_direction"]["question"]["questions"][0]["options"]) == 7
    failure(
        pilot,
        args(
            pilot,
            project,
            "append",
            references=many_refs(1, 5),
            round_id=round_id,
            request_id="sixth",
        ),
    )


def test_user_can_choose_early_without_waiting_for_remaining_sources(pilot, project):
    first = invoke(pilot, project, references=many_refs(1), more_expected=True)
    round_id = first["reference_direction"]["round_id"]
    selected = invoke(
        pilot,
        project,
        "select",
        selected_ids=["reference-0"],
        round_id=round_id,
        user_message="Use this one",
    )
    assert selected["reference_direction"]["status"] == "accepted"
    with pytest.raises(ValueError, match="Download the selected"):
        require_production_intake(saved(pilot, project), "step", {"production_stage": "excerpt"})
    require_production_intake(
        mark_downloaded(saved(pilot, project)), "step", {"production_stage": "excerpt"}
    )
    failure(
        pilot,
        args(pilot, project, "append", references=many_refs(1, 1), round_id=round_id),
    )


def test_another_batch_needs_actual_request_preserves_preferences_and_excludes_old_work(
    pilot, project
):
    first = invoke(
        pilot, project, references=many_refs(2), direction="Warm organic paper textures"
    )
    context = first["reference_direction"]
    option = context["question"]["questions"][0]["options"][-2]
    assert option["label"] == "Find another batch"
    assert option["record_with"]["arguments"]["action"] == "another_batch"
    parameters = option["record_with"]["arguments"] | {
        "request_id": "another",
        "user_message": "Find another batch",
    }
    before = saved(pilot, project)
    failure(pilot, parameters | {"user_message": ""})
    assert saved(pilot, project) == before
    refreshed = call(pilot, option["record_with"]["name"], parameters)
    context = refreshed["reference_direction"]
    assert context["status"] == "refining" and "question" not in context
    assert context["direction"] == "Warm organic paper textures"
    assert context["creation_approach"]["label"] == "Manim diagrams"
    assert context["excluded_reference_urls"] == [item["url"] for item in many_refs(2)]
    assert "do not ask them to invent a critique" in context["next_action"]
    failure(pilot, args(pilot, project, references=many_refs(1), request_id="recycled"))
    next_offer = invoke(
        pilot,
        project,
        references=many_refs(1, 2),
        more_expected=True,
        request_id="fresh-batch",
    )
    assert (
        next_offer["reference_direction"]["round_id"]
        != first["reference_direction"]["round_id"]
    )
    assert (
        next_offer["reference_direction"]["direction"] == "Warm organic paper textures"
    )
    assert next_offer["reference_direction"]["new_reference_ids"] == ["reference-2"]


def test_stale_round_does_not_select_same_id_reused_for_another_work(pilot, project):
    first = invoke(pilot, project, references=many_refs(1))
    old_round = first["reference_direction"]["round_id"]
    invoke(
        pilot,
        project,
        "another_batch",
        user_message="Find another batch",
        round_id=old_round,
    )
    new_ref = many_refs(1, 1)[0] | {"id": "reference-0"}
    invoke(pilot, project, references=[new_ref], request_id="new-offer")
    before = saved(pilot, project)
    assert "outdated" in failure(
        pilot,
        args(
            pilot,
            project,
            "select",
            round_id=old_round,
            selected_ids=["reference-0"],
            user_message="First one",
        ),
    )
    assert saved(pilot, project) == before


def test_old_offer_retry_never_relabels_a_later_reused_id_as_new(pilot, project):
    parameters = args(pilot, project, references=many_refs(1), more_expected=True)
    first = call(pilot, "record_video_references", parameters)
    invoke(
        pilot,
        project,
        "another_batch",
        user_message="Find another batch",
        round_id=first["reference_direction"]["round_id"],
    )
    replacement = many_refs(1, 1)[0] | {"id": "reference-0"}
    invoke(
        pilot,
        project,
        references=[replacement],
        request_id="replacement",
        more_expected=True,
    )
    before = saved(pilot, project)
    retry = call(pilot, "record_video_references", parameters)
    assert retry["repeated"]
    assert retry["reference_direction"]["new_link_cards"] == []
    assert retry["reference_direction"]["new_reference_ids"] == []
    assert saved(pilot, project) == before


def test_social_receipt_field_does_not_allow_fabricated_engagement():
    reference = refs()[0]
    with pytest.raises(ValueError):
        Reference.model_validate(reference | {"engagement": {"views": 1000000}})
    with pytest.raises(ValueError):
        Reference.model_validate(reference | {"social_receipt_id": "x" * 121})
    assert "social_receipt_id" not in Reference.model_validate(reference).model_dump()


def test_social_receipt_is_hydrated_from_server_and_bound_to_exact_post(pilot, project):
    store = pilot[1].state.store
    url = "https://www.youtube.com/watch?v=AbCdEfGh123"
    metadata = {
        "platform": "youtube",
        "post_id": "AbCdEfGh123",
        "canonical_url": url,
        "creator": {"name": "Studio", "url": "https://www.youtube.com/@studio"},
        "engagement": {
            "views": {
                "value": 2345,
                "display": "2,345",
                "evidence": "2,345 views",
                "source": "visible_text",
            },
            "likes": None,
        },
        "engagement_status": "partially_observed",
        "observed_at": "2026-10-02T20:00:00Z",
    }
    store.put(
        "social_reference",
        "social-1",
        {"owner": "tester", "project": project, "metadata": metadata},
    )
    reference = refs()[0] | {"url": url, "social_receipt_id": "social-1"}
    offered = invoke(pilot, project, references=[reference])
    hydrated = offered["reference_direction"]["references"][0]
    assert hydrated["social"] == metadata
    assert offered["reference_direction"]["link_cards"][0]["social"] == metadata
    assert "owner" not in hydrated["social"]


@pytest.mark.parametrize("mismatch", ["owner", "project", "post"])
def test_social_receipt_cannot_be_transplanted(pilot, project, mismatch):
    store = pilot[1].state.store
    url = "https://www.youtube.com/watch?v=AbCdEfGh123"
    receipt = {
        "owner": "tester",
        "project": project,
        "metadata": {"canonical_url": url},
    }
    if mismatch == "post":
        receipt["metadata"]["canonical_url"] = (
            "https://www.youtube.com/watch?v=OtherVid123"
        )
    else:
        receipt[mismatch] = "someone-else"
    store.put("social_reference", "social-1", receipt)
    before = saved(pilot, project)
    failure(
        pilot,
        args(
            pilot,
            project,
            references=[refs()[0] | {"url": url, "social_receipt_id": "social-1"}],
        ),
    )
    assert saved(pilot, project) == before


def test_rejected_social_work_cannot_return_as_a_short_or_tracking_link(pilot, project):
    first = refs()[0] | {"url": "https://www.youtube.com/watch?v=AbCdEfGh123"}
    invoke(pilot, project, references=[first])
    invoke(pilot, project, "another_batch", user_message="Find another batch")
    before = saved(pilot, project)
    alias = first | {
        "id": "other",
        "url": "https://youtu.be/AbCdEfGh123?utm_source=feed",
    }
    assert "rejected" in failure(
        pilot, args(pilot, project, references=[alias], request_id="alias")
    )
    assert saved(pilot, project) == before


def test_needed_reference_guidance_is_sequential_social_and_source_honest(
    pilot, project
):
    context = reference_context(saved(pilot, project), project)
    action = context["next_action"]
    assert "YouTube, TikTok and X" in action
    assert "Search sequentially" in action
    assert "parallel" not in action
    assert "social_receipt_id" in action
    assert "before searching for the next" in action
    assert "Find another batch" in action and "Give my input" in action
    assert "unknown counts are unavailable" in action
    tools = {tool["name"]: tool for tool in rpc(pilot, "tools/list", {})["tools"]}
    description = tools["record_video_references"]["description"]
    assert "YouTube, TikTok and X sequentially" in description
    assert "social_receipt_id" in description
    assert "one short fit explanation" in description
    assert "Find another batch" in description
