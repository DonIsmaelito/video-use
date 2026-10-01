"""Completed movies surface to viewers while review contact sheets stay internal."""

import asyncio
from copy import deepcopy
import json
from unittest.mock import AsyncMock, patch

import pytest

from video_use_mcp.pilot.tests.test_production_timing import fixture, sandbox, task


def test_review_only_step_publishes_movie_as_draft_and_keeps_sheet_internal():
    manager, _, _ = fixture()
    sb = sandbox()
    current = task()
    with patch("video_use_mcp.pilot.runtime.record_progress") as progress:
        result = asyncio.run(manager.perform(current, sb))
    manager.publish_preview.assert_awaited_once_with("u", "p", sb, "edit/final.mp4")
    assert result["preview"]["object_id"] == "preview-object"
    assert result["review_object"] == "review-object"
    first = progress.call_args_list[0]
    assert first.args[2] == "draft"
    assert first.args[-1]["media_type"] == "video/mp4"
    assert all(
        call.args[-1] != {"object_id": "review-object"}
        for call in progress.call_args_list
    )


def test_assembly_report_drives_measured_timing_without_mutating_request():
    manager, store, _ = fixture()
    sb = sandbox(duration=4)
    report = {
        "quality": "draft",
        "width": 960,
        "height": 540,
        "fps": 15,
        "duration": 4,
        "frame_count": 60,
        "scenes": [
            {"scene_id": "a", "seconds": 1.2},
            {"scene_id": "b", "seconds": 2.8},
        ],
        "audio_normalization": {"preset": "web"},
        "production_timing": {
            "scenes": [{"title": "a", "seconds": 1.2}, {"title": "b", "seconds": 2.8}],
            "narration_offset": 0.5,
        },
    }
    sb.read = AsyncMock(return_value=json.dumps(report).encode())
    current = task(
        assembly_report="edit/assemblies/a.assembly.json", preview_path="edit/final.mp4"
    )
    current["payload"].pop("production_timing")
    before = deepcopy(current)
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        result = asyncio.run(manager.perform(current, sb))
    assert current == before
    assert result["assembly"]["output"] == "edit/final.mp4"
    assert (
        result["_production_timing"]["scenes"] == report["production_timing"]["scenes"]
    )
    assert result["timing_source"] == "production_timing"
    # Durability is committed by execute only after success and checkpoint.
    assert not any(
        call.args[0] == "production_timing" for call in store.put.call_args_list
    )


def test_bad_assembly_timing_fails_before_preview_or_commit():
    manager, store, _ = fixture()
    sb = sandbox(duration=4)
    sb.read = AsyncMock(
        return_value=json.dumps(
            {"production_timing": {"scenes": [{"title": "wrong", "seconds": 1}]}}
        ).encode()
    )
    current = task(assembly_report="report.json", preview_path="edit/final.mp4")
    current["payload"].pop("production_timing")
    with pytest.raises(ValueError, match="encoded video"):
        asyncio.run(manager.perform(current, sb))
    manager.publish_preview.assert_not_awaited()
    assert not any(
        call.args[0] == "production_timing" for call in store.put.call_args_list
    )
