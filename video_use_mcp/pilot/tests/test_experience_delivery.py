"""Creative tools expose check-ins and allowance before paid speech is submitted."""

from unittest.mock import Mock

from video_use_mcp.pilot.tests.test_workflow import call
from video_use_mcp.pilot.tests.test_widgets import BEATS
from video_use_mcp.pilot.tests.test_workflow_catalog import complete_intake

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_start_includes_current_allowance_without_starting_a_task(pilot, monkeypatch):
    allowance = Mock(return_value={"status": "known", "remaining": 91})
    monkeypatch.setattr("video_use_mcp.pilot.workflow.narration_allowance", allowance)
    result = call(
        pilot,
        "start_video",
        dict(title="Wi-Fi", brief="Explain Wi-Fi with voiceover", category="explainer"),
    )
    allowance.assert_called_once_with(pilot[1].state.store, "tester")
    assert result["narration_allowance"]["remaining"] == 91
    assert result["experience"]["check_in"]["trigger"] == "involvement_required"
    assert result["experience"]["check_in"]["continuation"] == "wait_for_mode_choice"
    assert result["experience"]["source"] == "awaiting_user"
    assert [q["id"] for q in result["widget"]["questions"]] == ["involvement"]
    assert not any(
        "INSERT INTO public.vp_tasks" in c.args[0]
        for c in pilot[1].state.store.sql.call_args_list
    )


def test_story_surfaces_capacity_shortfall_before_narration(pilot, monkeypatch):
    allowance = Mock(
        return_value={"status": "known", "remaining": 10, "fits_available": False}
    )
    monkeypatch.setattr("video_use_mcp.pilot.widgets.narration_allowance", allowance)
    started = call(
        pilot,
        "start_video",
        dict(title="Wi-Fi", brief="Explain Wi-Fi with voiceover", category="explainer"),
    )
    ready = complete_intake(pilot, started)
    result = call(
        pilot,
        "show_video_story",
        dict(
            project_id=started["project_id"],
            creative_revision=ready["creative"]["revision"],
            beats=BEATS,
        ),
    )
    script = "\n\n".join(beat["narration"] for beat in BEATS)
    allowance.assert_called_once_with(
        pilot[1].state.store, "tester", requested_characters=len(script)
    )
    check = result["experience"]["check_in"]
    assert check["blocking_scope"] == "affected_component"
    assert check["continuation"] == "continue_independent_work"
    assert not check["automatic_retry"]
    assert "show_video_brief" in result["next_action"]
    assert "Do not silently remove voiceover" in result["next_action"]
    assert result["creative"]["script"] == script


def test_unknown_capacity_is_not_reported_as_exhausted(pilot, monkeypatch):
    monkeypatch.setattr(
        "video_use_mcp.pilot.widgets.narration_allowance",
        Mock(return_value={"status": "unknown", "fits_available": None}),
    )
    started = call(
        pilot,
        "start_video",
        dict(title="Story", brief="A short narrated story", category="explainer"),
    )
    ready = complete_intake(pilot, started)
    result = call(
        pilot,
        "show_video_story",
        dict(
            project_id=started["project_id"],
            creative_revision=ready["creative"]["revision"],
            beats=BEATS,
        ),
    )
    assert "experience" not in result
    assert result["narration_allowance"]["status"] == "unknown"
