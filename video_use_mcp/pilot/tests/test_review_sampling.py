"""The browser review uses the saved story timings without another host call."""

import asyncio
import json
import shlex
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from video_use_mcp.pilot.runtime import Manager


@pytest.mark.parametrize("has_plan", [False, True])
def test_review_passes_saved_beats_and_returns_compact_sampling_times(has_plan):
    beats = [
        {"title": "Sun's energy", "seconds": 5},
        {"title": "Electricity", "seconds": 4},
    ]
    store = Mock()
    store.get.side_effect = (
        lambda kind, key: {"beats": beats} if has_plan and kind == "creative" else None
    )
    manager = Manager(store, SimpleNamespace())
    manager.save_object = AsyncMock(return_value={"id": "review-object"})
    sb = SimpleNamespace(
        safe_path=AsyncMock(return_value="/workspace/edit/solar's final.mp4"),
        run=AsyncMock(
            side_effect=[
                {"exit_code": 0, "stdout": "exact-video-hash final.mp4"},
                {
                    "exit_code": 0,
                    "stdout": json.dumps(
                        {
                            "video": "/workspace/edit/solar's final.mp4",
                            "sample_times": [0.2, 3, 5.2, 7.4, 8.86666666667],
                            "contact_sheet": "/workspace/edit/verify/output-review.png",
                        }
                    ),
                },
            ]
        ),
        download=AsyncMock(),
    )
    task = {
        "owner": "u",
        "project": "p",
        "id": "t",
        "operation": "review",
        "payload": {"video_path": "edit/solar's final.mp4"},
    }
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        result = asyncio.run(manager.perform(task, sb))

    command = shlex.split(sb.run.await_args_list[1].args[0])
    assert command[3] == "/workspace/edit/solar's final.mp4"
    assert json.loads(command[command.index("--beats-json") + 1]) == (
        beats if has_plan else []
    )
    assert result["sample_times"] == [0.2, 3, 5.2, 7.4, 8.867]
    assert result["sha256"] == "exact-video-hash"
    assert result["review_object"] == "review-object"
    assert (
        "contact_sheet" not in result
    )  # private filesystem paths are not useful to the host


def test_review_remains_deliverable_without_optional_sampling_report():
    store = Mock()
    store.get.return_value = None
    manager = Manager(store, SimpleNamespace())
    manager.save_object = AsyncMock(return_value={"id": "review-object"})
    sb = SimpleNamespace(
        safe_path=AsyncMock(return_value="/workspace/edit/final.mp4"),
        run=AsyncMock(
            side_effect=[
                {"exit_code": 0, "stdout": "exact-video-hash final.mp4"},
                {"exit_code": 0, "stdout": ""},
            ]
        ),
        download=AsyncMock(),
    )
    task = {
        "owner": "u",
        "project": "p",
        "id": "t",
        "operation": "review",
        "payload": {"video_path": "edit/final.mp4"},
    }
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        result = asyncio.run(manager.perform(task, sb))
    assert result["review_object"] == "review-object"
    assert "sample_times" not in result
