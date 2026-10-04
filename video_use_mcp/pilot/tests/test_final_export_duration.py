"""Final delivery checks actual video duration and the encoded output's scope."""

import asyncio
import json
import shlex
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from video_use_mcp.pilot.tests.test_review_findings_export import export_fixture
from video_use_mcp.pilot.tests.test_cards import PID
from video_use_mcp.pilot.tests.test_intake_runtime import creative
from video_use_mcp.pilot.tests.test_production_timing import (
    DIGEST,
    fixture as timing_fixture,
    sandbox as timing_sandbox,
    task as timing_task,
)


def export_with_duration(tmp_path, requested=30, actual=30, *, frame_rate="30/1"):
    store, manager, sb, task = export_fixture(tmp_path)
    state = {
        "revision": 1,
        "intake": {"output_profile": {"duration_seconds": requested}},
    }
    store.put("creative", PID, state)
    store.put("render_revision", PID, 1)

    async def run(command, timeout=30):
        if command.startswith("ffprobe"):
            return {
                "exit_code": 0,
                "stdout": json.dumps(
                    {
                        "streams": [
                            {
                                "duration": str(actual),
                                "avg_frame_rate": frame_rate,
                                "time_base": "1/15360",
                            }
                        ],
                        "format": {"duration": "30"},
                    }
                ),
            }
        return {"exit_code": 0, "stdout": "encoded-sha  final.mp4"}

    sb.run.side_effect = run
    return store, manager, sb, task


def assert_no_export(manager, sb):
    sb.download.assert_not_awaited()
    manager.save_object.assert_not_awaited()
    manager.checkpoint.assert_not_awaited()


@pytest.mark.parametrize("actual", [6, 20, 29, 31, 60])
def test_material_duration_mismatch_cannot_be_exported(tmp_path, actual):
    store, manager, sb, task = export_with_duration(tmp_path, actual=actual)
    # A plan or reported timeline cannot substitute for the measured video.
    store.put("production_timing", PID, {"duration": 30, "scenes": [{"seconds": 30}]})
    with pytest.raises(ValueError, match="current requested duration is 30s"):
        asyncio.run(manager.perform(task, sb))
    sb.inspect_video.assert_not_awaited()
    assert_no_export(manager, sb)
    assert not any(
        "INSERT INTO public.vp_revisions" in c.args[0] for c in store.sql.call_args_list
    )


@pytest.mark.parametrize(
    "actual,frame_rate",
    [(30, "30/1"), (29.6, "30/1"), (30.13, "30/1"), (29.97, "30000/1001")],
)
def test_approximate_target_allows_narration_and_frame_rounding(
    tmp_path, actual, frame_rate
):
    store, manager, sb, task = export_with_duration(
        tmp_path, actual=actual, frame_rate=frame_rate
    )
    result = asyncio.run(manager.perform(task, sb))
    checked = result["final_duration_check"]
    assert checked["requested_seconds"] == 30
    assert checked["video_seconds"] == actual
    assert checked["tolerance_seconds"] == pytest.approx(0.600001)
    assert checked["source"] == "encoded_video_stream"
    metadata = json.loads(
        next(
            c.args[-1]
            for c in store.sql.call_args_list
            if "INSERT INTO public.vp_revisions" in c.args[0]
        )
    )
    assert metadata["final_duration_check"] == checked


def test_latest_user_duration_replaces_old_target_and_plan(tmp_path):
    store, manager, sb, task = export_with_duration(tmp_path, requested=6, actual=6)
    state = store.get("creative", PID)
    state["beats"] = [{"title": "Old thirty-second plan", "seconds": 30}]
    store.put("creative", PID, state)
    result = asyncio.run(manager.perform(task, sb))
    assert result["final_duration_check"]["requested_seconds"] == 6


def test_known_excerpt_cannot_export_after_sample_approval(tmp_path):
    store, manager, sb, task = export_with_duration(tmp_path, requested=6, actual=6)
    state = creative("hands_on", review="approved")
    state["intake"]["output_profile"]["duration_seconds"] = 6
    store.put("creative", PID, state)
    store.put(
        "production_output",
        PID + ":encoded-sha",
        {
            "sha256": "encoded-sha",
            "production_stage": "excerpt",
            "creative_revision": 1,
        },
    )
    with pytest.raises(ValueError, match="produced as a sample"):
        asyncio.run(manager.perform(task, sb))
    assert_no_export(manager, sb)


def test_different_excerpt_bytes_do_not_block_full_output(tmp_path):
    store, manager, sb, task = export_with_duration(tmp_path)
    store.put(
        "production_output",
        PID + ":old-sample-sha",
        {
            "sha256": "old-sample-sha",
            "production_stage": "excerpt",
        },
    )
    assert asyncio.run(manager.perform(task, sb))["video_id"] == "video-object"


def test_pending_checkpoint_still_blocks_export_before_media_io(tmp_path):
    store, manager, sb, task = export_with_duration(tmp_path)
    store.put("creative", PID, creative("hands_on", review="pending"))
    with pytest.raises(ValueError, match="explicit excerpt acceptance"):
        asyncio.run(manager.perform(task, sb))
    sb.run.assert_not_awaited()
    assert_no_export(manager, sb)


@pytest.mark.parametrize(
    "state",
    [
        None,
        {"revision": 1},
        {
            "revision": 1,
            "intake": {"output_profile": {}, "delegated_basics": ["duration"]},
        },
    ],
)
def test_legacy_or_delegated_duration_keeps_existing_export_flow(tmp_path, state):
    store, manager, sb, task = export_fixture(tmp_path)
    if state is not None:
        store.put("creative", PID, state)
        store.put("render_revision", PID, 1)
    result = asyncio.run(manager.perform(task, sb))
    assert result["video_id"] == "video-object"
    assert "final_duration_check" not in result
    assert all(not c.args[0].startswith("ffprobe") for c in sb.run.await_args_list)


@pytest.mark.parametrize(
    "probe",
    [
        {"streams": []},
        {"streams": [{"duration": "nan"}]},
        {"streams": [{"duration": "0"}]},
        {"format": {"duration": "30"}, "streams": [{"duration": "N/A"}]},
    ],
)
def test_unmeasurable_video_track_cannot_be_replaced_by_container_duration(
    tmp_path, probe
):
    _, manager, sb, _ = export_with_duration(tmp_path)
    sb.run.side_effect = None
    sb.run.return_value = {"exit_code": 0, "stdout": json.dumps(probe)}
    with pytest.raises(ValueError, match="Could not verify.*video-track duration"):
        asyncio.run(
            manager.final_duration_metadata(
                sb,
                "final.mp4",
                {
                    "intake": {"output_profile": {"duration_seconds": 30}},
                },
            )
        )


@pytest.mark.parametrize("failure", [None, "checkpoint", "preferences"])
def test_output_scope_commits_only_after_successful_checkpoint(failure):
    manager, store, values = timing_fixture()
    pending = {"sha256": DIGEST, "production_stage": "excerpt", "creative_revision": 2}
    manager.session = AsyncMock(return_value=object())
    manager.perform = AsyncMock(return_value={"_production_output": pending})

    async def checkpoint(*args):
        assert ("production_output", "p:" + DIGEST) not in values
        if failure == "checkpoint":
            raise ValueError("Checkpoint failed")
        if failure == "preferences":
            values[("creative", "p")]["revision"] = 3

    manager.checkpoint.side_effect = checkpoint
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        asyncio.run(manager.execute(timing_task(), 30))
    assert values.get(("production_output", "p:" + DIGEST)) == (
        pending if failure is None else None
    )


@pytest.mark.parametrize("with_timing", [True, False])
def test_render_scope_is_bound_to_reviewed_bytes_with_or_without_timeline(with_timing):
    manager, _, _ = timing_fixture()
    task = timing_task(production_stage="excerpt")
    if not with_timing:
        task["payload"].pop("production_timing")
    with patch("video_use_mcp.pilot.runtime.record_progress"):
        result = asyncio.run(manager.perform(task, timing_sandbox()))
    assert result["_production_output"] == {
        "project": "p",
        "sha256": DIGEST,
        "video_path": "edit/final.mp4",
        "production_stage": "excerpt",
        "creative_revision": 2,
        "task_id": "t",
    }


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_real_short_video_with_long_audio_cannot_pass_final_duration(tmp_path):
    path = tmp_path / "six second video with thirty second audio.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x36:r=10:d=6",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-t",
            "30",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
    )
    probe = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
    )
    assert float(probe["format"]["duration"]) == pytest.approx(30)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert float(video["duration"]) == pytest.approx(6)
    _, manager, _, _ = export_fixture(tmp_path / "store")

    async def run(command, timeout=30):
        result = subprocess.run(
            shlex.split(command), capture_output=True, text=True, timeout=timeout
        )
        return {"exit_code": result.returncode, "stdout": result.stdout}

    sb = SimpleNamespace(run=AsyncMock(side_effect=run))
    with pytest.raises(ValueError, match="encoded video is 6.000s"):
        asyncio.run(
            manager.final_duration_metadata(
                sb,
                str(path),
                {
                    "intake": {"output_profile": {"duration_seconds": 30}},
                },
            )
        )
