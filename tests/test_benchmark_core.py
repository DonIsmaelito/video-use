from __future__ import annotations

import math
import json

from benchmarks.core import (
    PHASES,
    TimedEvent,
    aggregate_runs,
    analyze_events,
    classify_command,
    estimate_codex_cost,
    load_timed_events,
)


PRICE = {
    "input_usd_per_million": 4.0,
    "cached_input_usd_per_million": 0.4,
    "cache_write_input_usd_per_million": 5.0,
    "output_usd_per_million": 20.0,
    "long_context_threshold_tokens": 272_000,
    "long_context_input_multiplier": 2.0,
    "long_context_output_multiplier": 1.5,
}


def event(at: float, payload: dict, turn: int = 1) -> TimedEvent:
    return TimedEvent(turn_index=turn, monotonic_s=at, event=payload)


def test_jsonl_analysis_is_deterministic_and_prices_output_once() -> None:
    records = [
        event(0.0, {"type": "benchmark.process.started"}),
        event(0.05, {"type": "thread.started", "thread_id": "thread-1"}),
        event(0.1, {"type": "turn.started"}),
        event(0.2, {
            "type": "item.started",
            "item": {"id": "cmd-1", "type": "command_execution", "command": "ffmpeg -i a.mov -o clip.mp4"},
        }),
        event(0.5, {
            "type": "item.completed",
            "item": {
                "id": "cmd-1",
                "type": "command_execution",
                "command": "ffmpeg -i a.mov -o clip.mp4",
                "status": "completed",
                "exit_code": 0,
            },
        }),
        event(0.6, {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1000,
                "cached_input_tokens": 200,
                "output_tokens": 100,
                "reasoning_output_tokens": 40,
            },
        }),
        event(0.7, {"type": "future.event", "unrecognized": True}),
    ]

    first = analyze_events(records, process_start_s=0.0, model_price=PRICE)
    second = analyze_events(records, process_start_s=0.0, model_price=PRICE)

    assert first == second
    assert first["timing"]["agent_wall_time_s"] == 0.7
    assert first["timing"]["time_to_first_item_s"] == 0.2
    assert first["tokens"]["reasoning_output_tokens"] == 40
    assert math.isclose(first["estimated_codex_cost_usd"], 0.00528)
    assert first["operations"]["rendering"] == {"count": 1, "duration_s": 0.3}
    assert set(first["operations"]) == set(PHASES)
    assert first["steps"]["commands"] == 1
    assert first["steps"]["event_types"]["future.event"] == 1


def test_timed_jsonl_parser_keeps_unknown_events(tmp_path) -> None:
    path = tmp_path / "events.timed.jsonl"
    path.write_text(json.dumps({
        "turn_index": 2,
        "monotonic_s": 12.5,
        "event": {"type": "new.event.kind", "future_field": {"a": 1}},
    }) + "\n", encoding="utf-8")
    parsed = load_timed_events(path)
    assert parsed == [event(12.5, {"type": "new.event.kind", "future_field": {"a": 1}}, turn=2)]


def test_cost_separates_cached_cache_write_and_long_context() -> None:
    usage = {
        "input_tokens": 300_000,
        "cached_input_tokens": 100_000,
        "cache_write_input_tokens": 50_000,
        "output_tokens": 10_000,
        "reasoning_output_tokens": 8_000,
        "total_tokens": 310_000,
    }
    cost = estimate_codex_cost(usage, PRICE)
    expected = 150_000 / 1_000_000 * 4 * 2
    expected += 100_000 / 1_000_000 * 0.4 * 2
    expected += 50_000 / 1_000_000 * 5 * 2
    expected += 10_000 / 1_000_000 * 20 * 1.5
    assert cost["long_context_pricing_applied"] is True
    assert math.isclose(cost["total_usd"], expected)


def test_phase_classification_retry_and_rerender_detection() -> None:
    assert classify_command("jq . edit/transcripts/jensen_test1.json") == "transcription_cache"
    assert classify_command("python pack_transcripts.py") == "transcript_packing"
    assert classify_command("python scene.py -p") == "animation"
    assert classify_command("ffprobe deliverables/clip.mp4") == "verification"

    records = [event(0.0, {"type": "benchmark.process.started"})]
    for index, (status, exit_code) in enumerate(
        (("failed", 1), ("completed", 0), ("completed", 0)), start=1
    ):
        start = float(index)
        item = {
            "id": f"render-{index}",
            "type": "command_execution",
            "command": "ffmpeg -i source.mov -o final.mp4",
        }
        records.append(event(start, {"type": "item.started", "item": item}))
        records.append(event(start + 0.25, {
            "type": "item.completed",
            "item": {**item, "status": status, "exit_code": exit_code},
        }))
    records.append(event(4.0, {"type": "turn.completed", "usage": {}}))
    metrics = analyze_events(records, process_start_s=0.0, model_price=PRICE)
    assert metrics["iterations"] == {
        "command_failures": 1,
        "successful_retries": 1,
        "render_attempts": 3,
        "rerenders": 2,
        "self_eval_passes": 0,
    }


def make_run(index: int, wall_time: float, passed: bool) -> dict:
    return {
        "schema_version": 1,
        "run_id": f"run-{index}",
        "task": {"id": "fixture", "version": 1, "prompt_sha256": "abc"},
        "environment": {"model": "gpt-5.6-sol", "reasoning_effort": "high"},
        "status": "complete",
        "timing": {"agent_wall_time_s": wall_time, "benchmark_wall_time_s": wall_time + 1},
        "tokens": {
            "input_tokens": 100 * index,
            "cached_input_tokens": 10,
            "output_tokens": 20,
            "reasoning_output_tokens": 5,
            "total_tokens": 120 * index,
        },
        "cost": {
            "codex_api_equivalent_usd": 0.1 * index,
            "elevenlabs_estimated_usd": 0.01,
            "total_estimated_usd": 0.1 * index + 0.01,
        },
        "steps": {"completed_items": index, "subagents_spawned": 0},
        "stops": {"expected_approval": 1, "unexpected_input": 0, "blocked": 0},
        "iterations": {
            "command_failures": 0,
            "successful_retries": 0,
            "render_attempts": 1,
            "rerenders": 0,
            "self_eval_passes": 1,
        },
        "outputs": {"clip_count": 1, "total_duration_s": 60.0, "artifacts": [{"path": "/raw/video.mp4"}]},
        "normalized": {
            "cost_per_clip_usd": 0.1 * index,
            "cost_per_output_minute_usd": 0.1 * index,
            "tokens_per_clip": 120 * index,
            "tokens_per_output_minute": 120 * index,
            "steps_per_clip": index,
            "steps_per_output_minute": index,
            "latency_per_clip_s": wall_time,
            "latency_per_output_minute_s": wall_time,
        },
        "validation": {"passed": passed, "errors": [], "warnings": []},
    }


def test_three_run_aggregation_includes_all_values_and_sanitizes_paths() -> None:
    runs = [
        make_run(1, 30.0, True),
        make_run(2, 10.0, False),
        make_run(3, 20.0, True),
    ]
    runs[0]["environment"].update({
        "workspace": "/Users/test/raw/workspace",
        "source_path": "/Users/test/raw/video.mp4",
    })
    runs[1]["validation"]["errors"] = ["failed at /Users/test/raw/video.mp4"]
    aggregate = aggregate_runs(runs)
    assert aggregate["run_count"] == 3
    assert aggregate["successful_runs"] == 2
    assert math.isclose(aggregate["success_rate"], 2 / 3)
    assert aggregate["metrics"]["timing.agent_wall_time_s"] == {
        "median": 20.0,
        "min": 10.0,
        "max": 30.0,
    }
    assert "artifacts" not in aggregate["runs"][0]["outputs"]
    assert "artifacts" in runs[0]["outputs"]
    assert "workspace" not in aggregate["runs"][0]["environment"]
    assert aggregate["runs"][1]["validation"]["errors"] == ["failed at <external-path>"]
