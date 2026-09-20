from __future__ import annotations

import json

from benchmarks.run import _collect_tts_metrics


def test_tts_collection_sums_append_only_attempts(tmp_path) -> None:
    records = [
        {
            "text_characters": 100,
            "character_cost": 10,
            "estimated_character_units": 10,
            "latency_s": 1.5,
            "succeeded": True,
        },
        {
            "text_characters": 50,
            "character_cost": None,
            "estimated_character_units": 0,
            "latency_s": 0.5,
            "succeeded": False,
        },
    ]
    for index, record in enumerate(records):
        (tmp_path / f"narration.{index}.tts_metrics.json").write_text(json.dumps(record))

    metrics = _collect_tts_metrics(tmp_path, usd_per_1000=2.0)
    assert metrics == {
        "requests": 2,
        "failed_requests": 1,
        "text_characters": 150,
        "character_cost_units": 10.0,
        "latency_s": 2.0,
        "estimated_usd": 0.02,
    }
