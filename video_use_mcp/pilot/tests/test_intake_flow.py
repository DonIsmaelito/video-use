"""Full MCP paths for the three requested browser collaboration modes."""

import pytest

from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_workflow import call
from video_use_mcp.pilot.runtime import require_production_intake

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def start(pilot, profile=None):
    return call(
        pilot,
        "start_video",
        dict(
            title="Rain",
            brief="Explain how rain forms",
            category="explainer",
            **({"output_profile": profile} if profile else {}),
        ),
    )


def answer(pilot, data, answers, request_id="click"):
    question = data["question"]
    labels = {
        q["id"]: {o["id"]: o["label"] for o in q["options"]}
        for q in question["questions"]
    }
    return call(
        pilot,
        "record_video_answers",
        dict(
            **question["record_with"]["arguments"],
            request_id=request_id,
            user_message=". ".join(labels[q][value] for q, value in answers.items()),
            answers=answers,
        ),
    )


def mode(pilot, selected):
    result = start(pilot, {"duration_seconds": 30, "viewing_destination": "YouTube"})
    return answer(pilot, result, {"involvement": selected})


def state(pilot, pid):
    return pilot[1].state.store.get("creative", pid)


def publish(pilot, pid, object_id="sample", duration=6):
    pilot[1].state.store.put(
        "progress",
        pid,
        {
            "updates": [
                {
                    "at": "2026-10-01T20:00:00Z",
                    "stage": "motion",
                    "note": "Opening sample",
                    "preview": {
                        "object_id": object_id,
                        "media_type": "video/mp4",
                        "duration": duration,
                    },
                }
            ]
        },
    )


def error(pilot, name, **args):
    result = rpc(pilot, "tools/call", dict(name=name, arguments=args))
    assert result.get("isError"), result
    return result["content"][0]["text"]


def test_new_request_asks_mode_then_only_missing_basics(pilot):
    result = start(pilot, {"duration_seconds": 30})
    assert [q["id"] for q in result["question"]["questions"]] == ["involvement"]
    assert not result["question"]["recorded_answers"]
    assert "widget" not in result
    assert "next_tool" not in result["intake"]
    pid = result["project_id"]
    with pytest.raises(ValueError, match="intake"):
        require_production_intake(state(pilot, pid), "narrate", {})
    chosen = answer(pilot, result, {"involvement": "key_moments"})
    assert chosen["intake"]["phase"] == "basics"
    assert chosen["intake"]["missing_basics"] == ["viewing_destination"]
    tool = chosen["intake"]["next_tool"]
    basics = call(pilot, tool["name"], tool["arguments"])
    ready = answer(pilot, basics, {"viewing_destination": "vertical"})
    assert ready["intake"]["output_profile"] == {
        "duration_seconds": 30,
        "viewing_destination": "vertical",
    }
    require_production_intake(state(pilot, pid), "step", {})


def test_hands_off_rejects_optional_style_and_draft_but_allows_production(pilot):
    selected = mode(pilot, "delegate")
    pid = selected["project_id"]
    require_production_intake(state(pilot, pid), "step", {})
    require_production_intake(state(pilot, pid), "export", {})
    assert "Hands off" in error(pilot, "show_video_choices", project_id=pid)
    publish(pilot, pid)
    assert "Hands off" in error(pilot, "show_video_preview", project_id=pid)
    assert call(pilot, "video_preview_updates", dict(project_id=pid))["media"] is None
    assert selected["intake"]["phase"] == "production"


def test_hands_on_style_excerpt_refine_and_acceptance(pilot):
    selected = mode(pilot, "hands_on")
    pid = selected["project_id"]
    choices = call(pilot, "show_video_choices", dict(project_id=pid))
    with pytest.raises(ValueError, match="intake"):
        require_production_intake(
            state(pilot, pid), "step", {"production_stage": "excerpt"}
        )
    call(
        pilot,
        "choose_video_style",
        dict(project_id=pid, revision=choices["choices"]["revision"], choice="diagram"),
    )
    require_production_intake(
        state(pilot, pid), "step", {"production_stage": "excerpt"}
    )
    with pytest.raises(ValueError, match="excerpt acceptance"):
        require_production_intake(
            state(pilot, pid), "step", {"production_stage": "full_video"}
        )
    publish(pilot, pid)
    player = call(pilot, "show_video_preview", dict(project_id=pid))
    checkpoint = call(
        pilot, player["next_tool"]["name"], player["next_tool"]["arguments"]
    )
    refined = answer(pilot, checkpoint, {"excerpt_review": "refine"})
    assert refined["intake"]["excerpt_review"]["status"] == "changes_requested"
    with pytest.raises(ValueError):
        require_production_intake(state(pilot, pid), "export", {})
    reshown = call(
        pilot,
        "show_video_checkpoint",
        dict(
            project_id=pid,
            creative_revision=refined["creative_revision"],
            object_id="sample",
        ),
    )
    assert reshown["question"]["status"] == "answered"
    assert "already requested refinement" in reshown["next_action"]
    assert "widget" not in reshown
    publish(pilot, pid, "revised-sample")
    checkpoint = call(
        pilot,
        "show_video_checkpoint",
        dict(
            project_id=pid,
            creative_revision=state(pilot, pid)["revision"],
            object_id="revised-sample",
        ),
    )
    accepted = answer(pilot, checkpoint, {"excerpt_review": "continue"})
    assert accepted["intake"]["excerpt_review"]["object_id"] == "revised-sample"
    require_production_intake(
        state(pilot, pid), "step", {"production_stage": "full_video"}
    )
    require_production_intake(state(pilot, pid), "export", {})
    retry = answer(pilot, checkpoint, {"excerpt_review": "continue"})
    assert (
        retry["repeated"]
        and retry["creative_revision"] == accepted["creative_revision"]
    )
    reopened = call(
        pilot,
        "show_video_checkpoint",
        dict(
            project_id=pid,
            creative_revision=accepted["creative_revision"],
            object_id="revised-sample",
        ),
    )
    assert "already accepted" in reopened["next_action"]
    assert reopened["intake"]["phase"] == "production"
    assert reopened["question"]["status"] == "answered"
    assert "widget" not in reopened


def test_sample_cannot_be_accepted_after_new_media_or_changed_preferences(pilot):
    selected = mode(pilot, "hands_on")
    pid = selected["project_id"]
    publish(pilot, pid)
    checkpoint = call(
        pilot,
        "show_video_checkpoint",
        dict(
            project_id=pid,
            creative_revision=state(pilot, pid)["revision"],
            object_id="sample",
        ),
    )
    publish(pilot, pid, "newer")
    error(
        pilot,
        "save_video_widget",
        project_id=pid,
        widget_id=checkpoint["question"]["id"],
        revision=1,
        request_id="stale",
        answers={"excerpt_review": "continue"},
    )
    assert state(pilot, pid)["intake"]["excerpt_review"]["status"] == "pending"
    error(
        pilot,
        "show_video_checkpoint",
        project_id=pid,
        creative_revision=state(pilot, pid)["revision"],
        object_id="sample",
    )
    publish(pilot, pid, "too-long", 30)
    assert "20 seconds" in error(
        pilot,
        "show_video_checkpoint",
        project_id=pid,
        creative_revision=state(pilot, pid)["revision"],
        object_id="too-long",
    )


def test_existing_request_retains_mode_and_new_request_starts_fresh(pilot):
    result = mode(pilot, "delegate")
    pid = result["project_id"]
    resumed = call(
        pilot,
        "start_video",
        dict(
            project_id=pid, title="Rain", brief="Make it brighter", category="explainer"
        ),
    )
    assert resumed["intake"]["mode"] == "delegate"
    assert "widget" not in resumed
    fresh = start(pilot)
    assert fresh["project_id"] != pid and fresh["intake"]["phase"] == "mode"
