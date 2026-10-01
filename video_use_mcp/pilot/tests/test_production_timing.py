"""Committed render timing must describe the encoded output, not its rough plan."""

import asyncio
import json
import shlex
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from video_use_mcp.pilot.runtime import Manager, validate_production_timing

DIGEST = "a" * 64
ROUGH = [{"title": str(i), "seconds": s} for i, s in enumerate([5, 5, 5, 7, 6, 2])]
ACTUAL = [
    {"title": str(i), "seconds": s}
    for i, s in enumerate([4.11, 4.25, 3.71, 9.15, 5.48, 3.30])
]


def fixture():
    values = {("creative", "p"): {"revision": 2, "beats": deepcopy(ROUGH)}}
    store = Mock()
    store.get.side_effect = lambda kind, key: deepcopy(values.get((kind, key)))
    store.put.side_effect = lambda kind, key, value, **kwargs: values.__setitem__(
        (kind, key), deepcopy(value)
    )
    manager = Manager(store, SimpleNamespace(api_key="", speech_key=""))
    manager.save_object = AsyncMock(return_value={"id": "review-object"})
    manager.publish_preview = AsyncMock(
        return_value={"object_id": "preview-object", "media_type": "video/mp4"}
    )
    manager.checkpoint = AsyncMock()
    return manager, store, values


def sandbox(duration=30, fps="30/1"):
    async def run(command, timeout=180):
        if command.startswith("ffprobe"):
            return {
                "exit_code": 0,
                "stdout": json.dumps(
                    {
                        "format": {"duration": str(duration)},
                        "streams": [
                            {
                                "codec_type": "video",
                                "duration": str(duration),
                                "avg_frame_rate": fps,
                            }
                        ],
                    }
                ),
            }
        if command.startswith("sha256sum"):
            return {"exit_code": 0, "stdout": DIGEST + " final.mp4"}
        if command.startswith("python -c"):
            return {
                "exit_code": 0,
                "stdout": '{"sample_times":[0.2, 4.31, 8.56, 29.9]}',
            }
        return {"exit_code": 0, "stdout": "", "stderr": ""}

    return SimpleNamespace(
        safe_path=AsyncMock(side_effect=lambda path, **kwargs: "/workspace/" + path),
        run=AsyncMock(side_effect=run),
        write=AsyncMock(),
        download=AsyncMock(),
    )


def task(timing=None, **payload):
    return {
        "id": "t",
        "owner": "u",
        "project": "p",
        "usage_id": "usage",
        "operation": "step",
        "payload": {
            "stage": "review",
            "note": "Actual timed render",
            "command": "render",
            "review_path": "edit/final.mp4",
            "creative_revision": 2,
            "production_timing": timing
            or {"scenes": deepcopy(ACTUAL), "narration_offset": 0.5},
            **payload,
        },
    }


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"scenes": []},
        {"scenes": [{"title": "x", "seconds": -1}]},
        {"scenes": [{"title": "x", "seconds": float("nan")}]},
        {"scenes": [{"title": "x", "seconds": float("inf")}]},
        {"scenes": [{"title": "x", "seconds": True}]},
        {"scenes": [{"title": "", "seconds": 1}]},
        {"scenes": [{"title": "x", "seconds": 1, "start": 0}]},
        {"scenes": [{"title": "x", "seconds": 1}], "narration_offset": -0.1},
        {"scenes": [{"title": "x", "seconds": 1}], "narration_offset": float("nan")},
        {"scenes": [{"title": "x", "seconds": 1}] * 65},
    ],
)
def test_invalid_timing_rejected_before_quota_or_execution(invalid):
    manager, store, _ = fixture()
    store.sql.return_value = []
    with pytest.raises(ValueError):
        manager.submit(
            "u",
            "p",
            "step",
            task(invalid)["payload"] | {"production_timing": invalid},
            "draft",
        )
    store.reserve.assert_not_called()
    assert not manager.running


def test_timing_total_must_match_encoded_video_and_offset_stays_inside_it():
    manager, store, _ = fixture()
    for timing in [
        {"scenes": [{"title": "wrong total", "seconds": 20}]},
        {"scenes": ACTUAL, "narration_offset": 31},
    ]:
        with pytest.raises(ValueError):
            asyncio.run(
                manager.production_timing_metadata(
                    task(timing), sandbox(), {"revision": 2}
                )
            )
    assert not any(
        call.args[0] == "production_timing" for call in store.put.call_args_list
    )


def test_actual_scene_timing_overrides_same_total_rough_plan_in_same_step():
    manager, store, values = fixture()
    sb = sandbox()
    before = deepcopy(values[("creative", "p")])
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        result = asyncio.run(manager.perform(task(), sb))
    review = next(
        call.args[0]
        for call in sb.run.await_args_list
        if call.args[0].startswith("python -c")
    )
    parts = shlex.split(review)
    assert json.loads(parts[parts.index("--beats-json") + 1]) == ACTUAL
    assert result["timing_source"] == "production_timing"
    assert result["_production_timing"]["duration"] == 30
    assert result["_production_timing"]["sha256"] == DIGEST
    assert result["_production_timing"]["narration_offset"] == 0.5
    assert result["_production_timing"]["source"] == "reported_render_timeline"
    assert values[("creative", "p")] == before  # no plan/revision rewrite
    assert ("production_timing", "p") not in values  # checkpoint has not committed yet


@pytest.mark.parametrize("failure", [None, "command", "checkpoint", "preferences"])
def test_timing_commits_only_after_successful_render_and_checkpoint(failure):
    manager, store, values = fixture()
    prior = {"sha256": "old", "scenes": [{"title": "previous", "seconds": 10}]}
    values[("production_timing", "p")] = prior
    pending = {"sha256": DIGEST, "scenes": ACTUAL, "creative_revision": 2}
    manager.session = AsyncMock(return_value=object())
    manager.perform = AsyncMock(
        return_value={
            "exit_code": 1 if failure == "command" else 0,
            "_production_timing": pending,
        }
    )

    async def checkpoint(*args):
        assert values[("production_timing", "p")] == prior
        if failure == "checkpoint":
            raise ValueError("checkpoint unavailable")
        if failure == "preferences":
            values[("creative", "p")]["revision"] = 3

    manager.checkpoint.side_effect = checkpoint
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        asyncio.run(manager.execute(task(), 30))
    if failure is None:
        assert values[("production_timing", "p")] == pending
        successes = [
            call
            for call in store.sql.call_args_list
            if "status='succeeded'" in call.args[0]
        ]
        result = json.loads(successes[-1].args[2])
        assert result["production_timing"] == pending
        assert "_production_timing" not in result
        assert values[("creative", "p")]["revision"] == 2
    else:
        assert values[("production_timing", "p")] == prior
    assert not any(call.args[0] == "creative" for call in store.put.call_args_list)


@pytest.mark.parametrize("matching,revision", [(True, 2), (False, 2), (True, 1)])
def test_later_review_uses_committed_timing_only_for_exact_video_and_revision(
    matching, revision
):
    manager, store, values = fixture()
    values[("production_timing", "p")] = {
        "sha256": DIGEST if matching else "b" * 64,
        "scenes": ACTUAL,
        "creative_revision": revision,
    }
    sb = sandbox()
    request = task() | {
        "operation": "review",
        "payload": {"video_path": "edit/final.mp4"},
    }
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        result = asyncio.run(manager.perform(request, sb))
    command = shlex.split(
        next(
            call.args[0]
            for call in sb.run.await_args_list
            if call.args[0].startswith("python -c")
        )
    )
    assert json.loads(command[command.index("--beats-json") + 1]) == (
        ACTUAL if matching and revision == 2 else ROUGH
    )
    assert result["timing_source"] == (
        "production_timing" if matching and revision == 2 else "creative_plan"
    )


def test_normalizing_timing_preserves_requested_numbers_and_does_not_mutate_input():
    source = {
        "scenes": [{"title": "  Opening  ", "seconds": 1.25}],
        "narration_offset": 0,
    }
    before = deepcopy(source)
    assert validate_production_timing(source) == {
        "scenes": [{"title": "Opening", "seconds": 1.25}],
        "narration_offset": 0.0,
    }
    assert source == before
    assert validate_production_timing(None) is None


def test_production_timing_binds_real_encoded_video_duration_and_digest(tmp_path):
    import hashlib
    import shutil
    import subprocess

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg required")
    video = tmp_path / "actual.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=64x36:r=10:d=1.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    manager, _, _ = fixture()

    async def run(command, timeout=30):
        if command.startswith("sha256sum"):
            return {
                "exit_code": 0,
                "stdout": hashlib.sha256(video.read_bytes()).hexdigest()
                + " actual.mp4",
            }
        result = subprocess.run(
            shlex.split(command), capture_output=True, text=True, check=True
        )
        return {"exit_code": result.returncode, "stdout": result.stdout}

    sb = SimpleNamespace(
        safe_path=AsyncMock(return_value=str(video)), run=AsyncMock(side_effect=run)
    )
    timing = {
        "scenes": [
            {"title": "Opening", "seconds": 0.7},
            {"title": "Close", "seconds": 0.5},
        ],
        "narration_offset": 0.1,
    }
    result = asyncio.run(
        manager.production_timing_metadata(task(timing), sb, {"revision": 2})
    )
    assert result["duration"] == pytest.approx(1.2)
    assert result["scene_duration_total"] == pytest.approx(1.2)
    assert result["sha256"] == hashlib.sha256(video.read_bytes()).hexdigest()
    assert result["narration_offset"] == 0.1
    assert result["creative_revision"] == 2
