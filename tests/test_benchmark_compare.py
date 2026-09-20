from __future__ import annotations

import pytest

from benchmarks.compare import compare_reports


def report(*, task_version: int = 1, success: float, median: float) -> dict:
    return {
        "task": {"id": "jensen-tiktok", "version": task_version},
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "success_rate": success,
        "metrics": {"timing.agent_wall_time_s": {"median": median, "min": median, "max": median}},
    }


def test_compare_reports_absolute_percentage_and_validation_floor() -> None:
    comparison = compare_reports(
        report(success=1.0, median=100.0),
        report(success=2 / 3, median=80.0),
    )
    row = comparison["metrics"]["timing.agent_wall_time_s"]
    assert row["absolute_change"] == -20.0
    assert row["percent_change"] == -20.0
    assert comparison["eligible_as_improvement"] is False


def test_compare_rejects_incompatible_task_versions() -> None:
    with pytest.raises(ValueError, match="different task definitions"):
        compare_reports(
            report(task_version=1, success=1.0, median=100.0),
            report(task_version=2, success=1.0, median=90.0),
        )
