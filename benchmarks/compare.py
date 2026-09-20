#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.core import read_json


def _identity(report: dict[str, Any]) -> tuple[Any, ...]:
    task = report.get("task", {})
    return (
        task.get("id"),
        task.get("version"),
        task.get("definition_sha256"),
        task.get("prompt_sha256"),
        report.get("model"),
        report.get("reasoning_effort"),
        report.get("agent", {}).get("adapter"),
        report.get("agent", {}).get("adapter_version"),
        report.get("price_version"),
        json.dumps(report.get("inputs", {}), sort_keys=True),
    )


def compare_reports(
    baseline: dict[str, Any], candidate: dict[str, Any], *, allow_incompatible: bool = False
) -> dict[str, Any]:
    compatible = (
        _identity(baseline) == _identity(candidate)
        and bool(baseline.get("inputs_consistent_across_runs", True))
        and bool(candidate.get("inputs_consistent_across_runs", True))
        and bool(baseline.get("implementation_consistent_across_runs", True))
        and bool(candidate.get("implementation_consistent_across_runs", True))
    )
    if not compatible and not allow_incompatible:
        raise ValueError(
            "reports use different task definitions, inputs, models, reasoning effort, "
            "agent adapters, or price versions; "
            "pass --allow-incompatible to inspect them anyway"
        )
    rows: dict[str, Any] = {}
    metric_names = sorted(set(baseline.get("metrics", {})) | set(candidate.get("metrics", {})))
    for name in metric_names:
        before_stats = baseline.get("metrics", {}).get(name) or {}
        after_stats = candidate.get("metrics", {}).get(name) or {}
        before = before_stats.get("median")
        after = after_stats.get("median")
        absolute = None
        percent = None
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            absolute = after - before
            if before != 0:
                percent = absolute / before * 100.0
        rows[name] = {
            "baseline_median": before,
            "candidate_median": after,
            "absolute_change": absolute,
            "percent_change": percent,
        }
    baseline_success = float(baseline.get("success_rate", 0.0))
    candidate_success = float(candidate.get("success_rate", 0.0))
    eligible = compatible and candidate_success >= baseline_success
    if not compatible:
        reason = "reports are not directly comparable"
    elif candidate_success >= baseline_success:
        reason = "candidate artifact-validation success rate is not lower than baseline"
    else:
        reason = "candidate artifact-validation success rate regressed"
    return {
        "schema_version": 1,
        "compatible": compatible,
        "task": candidate.get("task"),
        "baseline_success_rate": baseline_success,
        "candidate_success_rate": candidate_success,
        "eligible_as_improvement": eligible,
        "eligibility_reason": reason,
        "metrics": rows,
    }


def _format(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two Video Use benchmark baselines")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--allow-incompatible", action="store_true")
    args = parser.parse_args()
    comparison = compare_reports(
        read_json(args.baseline),
        read_json(args.candidate),
        allow_incompatible=args.allow_incompatible,
    )
    if args.as_json:
        print(json.dumps(comparison, indent=2, sort_keys=True))
        return
    print(f"compatible: {comparison['compatible']}")
    print(f"success rate: {_format(comparison['baseline_success_rate'])} -> {_format(comparison['candidate_success_rate'])}")
    print(f"eligible as improvement: {comparison['eligible_as_improvement']}")
    print()
    print(f"{'metric':52} {'baseline':>12} {'candidate':>12} {'change %':>12}")
    for name, row in comparison["metrics"].items():
        print(
            f"{name:52} {_format(row['baseline_median']):>12} "
            f"{_format(row['candidate_median']):>12} {_format(row['percent_change']):>12}"
        )


if __name__ == "__main__":
    main()
