import pytest

from video_use_mcp.pilot.cost_report import estimate, project_report

RATES = {"cpu_hour_cost_sandbox": "0.1419", "mem_gib_hour_cost_sandbox": "0.024"}


def snapshot():
    return {
        "projects": [
            {"id": "p", "title": "Card", "sandbox_id": "sb-test", "touched": 100}
        ],
        "tasks": [
            {"project": "p", "status": "running", "amount": 600, "settled": False}
        ],
        "lifetimes": [],
        "speech": [],
        "objects": [],
    }


def test_core_hour_rates_and_resource_limits():
    assert estimate(3600, RATES) == pytest.approx(
        {
            "usd_at_requested_resources": 0.3798,
            "usd_at_resource_limits": 0.7596,
        }
    )


def test_reservations_are_not_added_to_wall_time_cost():
    result = project_report(snapshot(), RATES, 160, 0.08, None)[0]
    assert result["workspace_seconds_recorded"] == 60
    assert result["reserved_task_seconds"] == 600
    assert result["render_estimate"]["usd_at_requested_resources"] == pytest.approx(
        0.3798 / 60
    )
    assert result["transcription_estimate_usd"] == 0


def test_closed_workspace_replaces_active_time_and_unknown_speech_is_not_free():
    data = snapshot()
    before = project_report(data, RATES, 160, 0.08, None)[0]
    data["projects"][0]["sandbox_id"] = None
    data["lifetimes"] = [
        {"project": "p", "seconds": 60},
        {"project": "another-project", "seconds": 500},
    ]
    data["speech"] = [{"project": "p", "kind": "transcribe", "amount": 30}]
    after = project_report(data, RATES, 900, 0.08, None)[0]
    assert after["render_estimate"] == before["render_estimate"]
    assert after["transcription_estimate_usd"] is None
