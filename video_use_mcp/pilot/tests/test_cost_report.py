import json

import pytest

from video_use_mcp.pilot.cost_report import estimate, project_report, write_report

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


def test_reference_browser_runtime_has_its_own_resource_estimate():
    data = snapshot()
    data["reference_lifetimes"] = [
        {"project": "p", "reservation": "closed-browser", "seconds": 60}
    ]
    data["reference_sessions"] = [
        {"project": "p", "reservation": "active-browser", "created": 130}
    ]
    result = project_report(data, RATES, 160, 0.08, None)[0]
    assert result["workspace_seconds_recorded"] == 60
    assert result["render_estimate"] == estimate(60, RATES)
    assert result["reference_browser_seconds_recorded"] == 90
    # Research requests one core and two GiB, independently of render resources.
    assert result["reference_browser_estimate_usd"] == pytest.approx(
        90 / 3600 * (0.1419 + 2 * 0.024)
    )
    assert result["reserved_task_seconds"] == 600


@pytest.mark.parametrize(
    "created,expected_seconds", [(100, 180), (900, 100), (1100, 0)]
)
def test_reference_session_time_is_capped_at_three_minutes(created, expected_seconds):
    data = snapshot()
    data["reference_sessions"] = [
        {"project": "p", "reservation": "browser", "created": created}
    ]
    result = project_report(data, RATES, 1000, 0.08, None)[0]
    assert result["reference_browser_seconds_recorded"] == expected_seconds
    assert result["reference_browser_estimate_usd"] == pytest.approx(
        expected_seconds / 3600 * 0.1899
    )


def test_settled_browser_and_surviving_lease_are_not_counted_twice():
    data = snapshot()
    data["reference_lifetimes"] = [
        {"project": "p", "reservation": "settled-browser", "seconds": 42.25}
    ]
    data["reference_sessions"] = [
        {"project": "p", "reservation": "settled-browser", "created": 10},
        {"project": "p", "reservation": "new-browser", "created": 140},
    ]
    result = project_report(data, RATES, 160, 0.08, None)[0]
    assert result["reference_browser_seconds_recorded"] == 62.25
    assert result["reference_browser_estimate_usd"] == pytest.approx(
        62.25 / 3600 * 0.1899
    )


def test_browser_lifetimes_leases_and_capture_bytes_are_project_scoped():
    data = snapshot()
    data["projects"].append(
        {"id": "other", "title": "Other project", "sandbox_id": None, "touched": 0}
    )
    data["reference_lifetimes"] = [
        {"project": "p", "reservation": "p-closed", "seconds": 10},
        {"project": "other", "reservation": "other-closed", "seconds": 100},
    ]
    data["reference_sessions"] = [
        {"project": "p", "reservation": "p-open", "created": 150},
        {"project": "other", "reservation": "other-open", "created": 100},
    ]
    data["reference_evidence"] = [
        {"project": "p", "bytes": 1200},
        {"project": "p", "bytes": 3500},
        {"project": "p"},  # Metadata alone is not image storage.
        {"project": "other", "bytes": 8000},
    ]
    data["objects"] = [{"project": "p", "bytes": 999}]
    first, second = project_report(data, RATES, 160, 0.08, None)
    assert first["reference_browser_seconds_recorded"] == 20
    assert second["reference_browser_seconds_recorded"] == 160
    assert first["reference_capture_bytes"] == 4700
    assert second["reference_capture_bytes"] == 8000
    assert first["stored_bytes"] == 999  # Captures remain separately reported.
    assert second["workspace_seconds_recorded"] == 0
    assert second["render_estimate"] == estimate(0, RATES)


def test_older_snapshots_report_zero_browser_usage_without_new_fields():
    result = project_report(snapshot(), RATES, 160, 0.08, None)[0]
    assert result["reference_browser_seconds_recorded"] == 0
    assert result["reference_browser_estimate_usd"] == 0
    assert result["reference_capture_bytes"] == 0


def test_markdown_shows_browser_cost_separately_from_render_and_speech(tmp_path):
    data = snapshot()
    data["projects"][0]["title"] = "Moon | navy\nfilm"
    data["reference_lifetimes"] = [
        {"project": "p", "reservation": "closed-browser", "seconds": 90}
    ]
    report = {
        "observed_at": "2026-10-02T12:00:00+00:00",
        "projects": project_report(data, RATES, 160, 0.08, None),
        "modal_reported_app_cost_usd": "1.23",
        "coordinator_minimum_usd_per_hour": "0.05",
        "coordinator_minimum_usd_per_30_days": "36",
        "limitations": ["Provider bills overlap project estimates; do not add them."],
    }
    write_report(report, tmp_path)
    lines = (tmp_path / "latest.md").read_text().splitlines()
    header = next(line for line in lines if line.startswith("| Project |"))
    row = next(line for line in lines if line.startswith("| Moon / navy film |"))
    cells = dict(
        zip(
            [cell.strip() for cell in header.strip("|").split("|")],
            [cell.strip() for cell in row.strip("|").split("|")],
        )
    )
    assert cells["Reference browser estimate USD"] == "0.0047"
    assert cells["Render estimate USD"] == "0.0063–0.0127"
    assert cells["Speech estimate USD"] == "0.0000"
    assert cells["Recorded workspace minutes"] == "1.00"
    assert json.loads((tmp_path / "latest.json").read_text()) == report
