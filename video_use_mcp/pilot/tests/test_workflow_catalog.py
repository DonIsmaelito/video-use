"""Mixed media briefs stay flexible without promising absent providers."""

import json

import pytest

from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.workflow import catalog, workflow_catalog, workflow_summary

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def call(pilot, name, arguments):
    result = rpc(pilot, "tools/call", dict(name=name, arguments=arguments))
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_mixed_request_retains_user_direction_and_avoids_approval_gate(pilot):
    result = call(
        pilot,
        "start_video",
        dict(
            title="Quarterly update",
            brief="Turn this investor deck and its CSV into a narrated update",
            category="document_video",
            supporting_categories=["data_story", "brand", "data_story"],
            preferences="Keep our original navy charts and skip style questions",
        ),
    )
    state = result["creative"]
    assert state["supporting_categories"] == ["data_story", "brand"]
    assert (
        state["preferences"] == "Keep our original navy charts and skip style questions"
    )
    assert not result["workflow"]["choices"]
    assert [item["category"] for item in result["complementary_workflows"]] == [
        "data_story",
        "brand",
    ]
    assert not state.get("awaiting_feedback")
    assert "Do not invent" in " ".join(
        result["complementary_workflows"][1]["limitations"]
    )
    revised = call(
        pilot,
        "start_video",
        dict(
            project_id=result["project_id"],
            title="Quarterly update",
            brief="Make the same deck into a shorter cut",
            category="document_video",
        ),
    )
    assert (
        revised["creative"]["supporting_categories"] == state["supporting_categories"]
    )
    assert revised["creative"]["revision"] == state["revision"] + 1
    assert revised["creative"]["preferences"] == state["preferences"]
    assert (
        "building_blocks" in revised["workflow"] and "steps" not in revised["workflow"]
    )


def test_category_change_removes_stale_choices_and_custom_stays_open(pilot):
    original = call(
        pilot,
        "start_video",
        dict(
            title="A new idea",
            brief="Explain sound",
            category="explainer",
            supporting_categories=["data_story"],
        ),
    )
    pid = original["project_id"]
    call(pilot, "show_video_choices", dict(project_id=pid))
    call(
        pilot, "choose_video_style", dict(project_id=pid, choice="diagram", revision=1)
    )
    changed = call(
        pilot,
        "start_video",
        dict(
            project_id=pid,
            title="Another idea",
            brief="Create an unusual mixed media piece",
            category="custom",
        ),
    )
    assert "selected" not in changed["creative"]
    assert "offered" not in changed["creative"]
    assert not changed["creative"]["supporting_categories"]
    assert not changed["workflow"]["choices"]
    assert changed["capabilities"]["generative_video"] is False
    assert changed["capabilities"]["campaign_delivery"] is False


def test_catalog_has_real_references_without_mutable_shared_state():
    available = catalog()
    discovered = workflow_catalog()
    for entry in discovered:
        workflow = workflow_summary(entry["category"])
        assert all(choice in available for choice in workflow["choices"])
    original = workflow_summary("audio_first")
    original["inputs"].append("Mutated by a caller")
    original["choices"].append("not-a-real-style")
    discovered[0]["inputs"].clear()
    assert "Mutated by a caller" not in workflow_summary("audio_first")["inputs"]
    assert "not-a-real-style" not in workflow_summary("audio_first")["choices"]
    assert workflow_catalog()[0]["inputs"]


def test_excessive_composition_is_rejected_before_project_creation(pilot):
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="start_video",
            arguments=dict(
                title="Everything",
                brief="Mixed work",
                category="custom",
                supporting_categories=[
                    "explainer",
                    "brand",
                    "data_story",
                    "social_clips",
                ],
            ),
        ),
    )
    assert result["isError"]
    assert not any(
        "INSERT INTO public.vp_projects" in call.args[0]
        for call in pilot[1].state.store.sql.call_args_list
    )


@pytest.mark.parametrize(
    "reference_ids,recommended",
    [
        (["product_3d", "diagram"], ""),
        (["diagram", "product_3d", "editorial"], "product_3d"),
    ],
)
def test_custom_workflows_can_offer_relevant_catalog_references(
    pilot, reference_ids, recommended
):
    started = call(
        pilot,
        "start_video",
        dict(
            title="A mixed piece",
            brief="Compare three ways to illustrate an idea",
            category="custom",
        ),
    )
    pid = started["project_id"]
    assert not started["workflow"]["choices"]
    shown = call(
        pilot,
        "show_video_choices",
        dict(project_id=pid, reference_ids=reference_ids, recommended=recommended),
    )
    assert [option["id"] for option in shown["choices"]["options"]] == reference_ids
    assert shown["choices"]["recommended"] == (recommended or reference_ids[0])
    saved = pilot[1].state.store.get("creative", pid)
    assert saved["offered"] == reference_ids
    selected = call(
        pilot,
        "choose_video_style",
        dict(
            project_id=pid, choice="product_3d", revision=shown["choices"]["revision"]
        ),
    )
    assert selected["creative"]["selected"] == "product_3d"


@pytest.mark.parametrize(
    "reference_ids,recommended",
    [
        ([], ""),
        (["diagram"], ""),
        (["diagram", "diagram"], ""),
        (["diagram", "invented"], ""),
        (["diagram", "editorial", "demo_focus", "product_3d"], ""),
        (["diagram", "editorial"], "product_3d"),
    ],
)
def test_bad_reference_overrides_leave_existing_offer_unchanged(
    pilot, reference_ids, recommended
):
    started = call(
        pilot,
        "start_video",
        dict(title="A mixed piece", brief="Use relevant references", category="custom"),
    )
    pid = started["project_id"]
    call(
        pilot,
        "show_video_choices",
        dict(project_id=pid, reference_ids=["diagram", "product_3d"]),
    )
    before = pilot[1].state.store.get("creative", pid)
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="show_video_choices",
            arguments=dict(
                project_id=pid,
                reference_ids=reference_ids,
                recommended=recommended,
            ),
        ),
    )
    assert result["isError"]
    assert pilot[1].state.store.get("creative", pid) == before
