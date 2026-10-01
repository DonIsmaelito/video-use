"""Allowance snapshots count pending work and never manufacture availability."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.allowance import narration_allowance


def snapshot():
    return {
        "checked_at": "2026-10-01T19:04:00+00:00",
        "resets_at": "2026-10-02T00:00:00+00:00",
        "user": {"limit": 2000, "committed": 500, "reserved": 200},
        "shared": {"limit": 10000, "committed": 8500, "reserved": 700},
    }


def test_one_read_counts_reservations_and_shared_limit():
    row = snapshot()
    before = deepcopy(row)
    store = Mock()
    store.sql.return_value = [{"allowance": row}]
    result = narration_allowance(store, "user", requested_characters=801)
    store.sql.assert_called_once_with(
        "SELECT public.vp_narration_allowance($1::uuid) AS allowance", "user"
    )
    assert result["status"] == "known"
    assert result["user"]["remaining"] == 1300
    assert result["shared"]["remaining"] == 800
    assert result["remaining"] == 800 and result["fits_available"] is False
    assert result["resets_at"] == "2026-10-02T00:00:00+00:00"
    assert "not a reservation or provider bill" in result["estimate_basis"]
    assert row == before
    assert len(store.mock_calls) == 1


@pytest.mark.parametrize("characters,fits", [(0, True), (800, True), (801, False)])
def test_supplied_text_estimate_is_bounded_by_both_pools(characters, fits):
    store = Mock()
    store.sql.return_value = [{"allowance": snapshot()}]
    result = narration_allowance(store, "user", requested_characters=characters)
    assert result["fits_available"] is fits
    assert result["requested_characters"] == characters


def test_overdrawn_snapshot_never_reports_negative_capacity():
    row = snapshot()
    row["user"]["reserved"] = 2000
    store = Mock()
    store.sql.return_value = [{"allowance": row}]
    result = narration_allowance(store, "user")
    assert result["remaining"] == 0
    assert "No daily allowance remains" in result["next_action"]
    assert "Do not silently omit requested voiceover" in result["next_action"]


@pytest.mark.parametrize("rows", [[], [{}], [{"allowance": None}], [{"allowance": {}}]])
def test_missing_snapshot_is_unknown_not_zero(rows):
    store = Mock()
    store.sql.return_value = rows
    result = narration_allowance(store, "user", requested_characters=400)
    assert result["status"] == "unknown" and result["fits_available"] is None
    assert "remaining" not in result and "user" not in result


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["user"].update(committed=-1),
        lambda value: value["shared"].update(limit=True),
        lambda value: value.update(resets_at=value["checked_at"]),
        lambda value: value.update(checked_at="2026-10-01T01:00:00"),
    ],
)
def test_malformed_snapshot_is_unknown(mutate):
    value = snapshot()
    mutate(value)
    store = Mock()
    store.sql.return_value = [{"allowance": value}]
    assert narration_allowance(store, "user")["status"] == "unknown"


def test_failed_read_never_leaks_backend_error_or_stops_creation():
    store = Mock()
    store.sql.side_effect = RuntimeError("private SQL credential=example-secret")
    result = narration_allowance(store, "user")
    assert result["status"] == "unknown"
    assert "example-secret" not in str(result)
    assert "normal atomic allowance check still applies" in result["next_action"]


@pytest.mark.parametrize("count", [-1, 0.5, True, "400"])
def test_invalid_estimate_is_rejected_without_database_call(count):
    store = Mock()
    with pytest.raises(ValueError, match="nonnegative integer"):
        narration_allowance(store, "user", requested_characters=count)
    store.sql.assert_not_called()
