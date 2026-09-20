from __future__ import annotations

import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from gui.run_store import RunPinnedError, RunStore, build_run_summary
from gui.task_context import task_context_from_edl


def _record(run_id: str = "lane-2-example") -> dict:
    return {
        "log_format_version": 3,
        "run_id": run_id,
        "lane_id": 2,
        "status": "failed",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "prompt": "Build a concise technical explainer",
        "started_at": "2026-09-01T10:00:00+00:00",
        "finished_at": "2026-09-01T10:02:05+00:00",
        "events": [
            {
                "type": "agent_decision",
                "message": "use a diagram for the abstract concept",
            },
            {
                "type": "agent_trace",
                "agent_event": "tool",
                "message": "command completed",
            },
            {
                "type": "failed",
                "message": "render failed because an overlay was missing",
            },
        ],
    }


def test_store_persists_and_reloads_a_run_summary(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "data")
    run_dir = store.ensure_run("lane-2-example")
    edit_dir = run_dir / "agent-edit"
    edit_dir.mkdir()
    (edit_dir / "edl.json").write_text(
        json.dumps(
            {
                "sources": {"voice": "voice.mp4"},
                "ranges": [{"source": "voice", "start": 0, "end": 2}],
                "overlays": [{"file": "diagram.mp4"}],
                "deliverables": [{"id": "wide"}],
                "total_duration_s": 2,
                "task_context": {
                    "operation": "create",
                    "workflow": "animated explainer",
                    "media_origin": "generated",
                    "summary": "A concise diagram-led technical explanation.",
                },
            }
        )
    )

    store.save_record("lane-2-example", run_dir, _record())

    reloaded = RunStore(tmp_path / "data")
    assert reloaded.resolve("lane-2-example") == run_dir
    summary = reloaded.record_file("lane-2-example", "run_summary.md").read_text()
    assert "Wall time: 2m 5s" in summary
    assert "Timeline ranges: 1" in summary
    assert "Type: create · animated explainer" in summary
    assert "Media: generated" in summary
    assert "render failed because an overlay was missing" in summary
    assert reloaded.list_runs()[0]["status"] == "failed"
    assert reloaded.list_runs()[0]["task_context"]["workflow"] == "animated explainer"


def test_task_context_can_be_inferred_from_edl_evidence_without_prompt() -> None:
    context = task_context_from_edl(
        {
            "sources": {"master": "assets/original.mp4"},
            "ranges": [
                {
                    "source": "master",
                    "start": 0,
                    "end": 35,
                    "beat": "hook product demo payoff CTA",
                }
            ],
            "deliverables": [{"id": "social_vertical"}],
        },
        has_project=False,
    )

    assert context == {
        "operation": "create",
        "workflow": "social ad",
        "source": "edl_inferred",
    }


def test_ranked_montage_is_not_mislabeled_by_an_incidental_interview_note() -> None:
    context = task_context_from_edl(
        {
            "sources": {f"goal_{index}": f"goal_{index}.mp4" for index in range(4)},
            "ranges": [
                {
                    "source": f"goal_{index}",
                    "start": 0,
                    "end": 10,
                    "beat": f"GOAL {index}",
                    "reason": "cuts past an interview lead-in" if index == 1 else "goal",
                }
                for index in range(4)
            ],
        },
        has_project=False,
    )

    assert context["workflow"] == "montage"


def test_project_run_is_indexed_without_moving_it(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "data")
    project = tmp_path / "project"

    run_dir = store.ensure_run("lane-1-project", project)
    store.save_record("lane-1-project", run_dir, _record("lane-1-project"))

    assert run_dir == project / "edit" / "runs" / "lane-1-project"
    assert RunStore(tmp_path / "data").resolve("lane-1-project") == run_dir


def test_pin_export_and_delete_lifecycle(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "data")
    run_dir = store.ensure_run("lane-3-golden")
    (run_dir / "output.mp4").write_bytes(b"video")
    store.save_record("lane-3-golden", run_dir, _record("lane-3-golden"))

    pinned = store.set_pinned("lane-3-golden", True)
    assert pinned["pinned"] is True
    with pytest.raises(RunPinnedError):
        store.delete("lane-3-golden")

    bundle = store.export("lane-3-golden")
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    assert "lane-3-golden/output.mp4" in names
    assert "lane-3-golden/trace.json" in names
    assert "lane-3-golden/run_summary.md" in names

    store.set_pinned("lane-3-golden", False)
    store.delete("lane-3-golden")
    assert not run_dir.exists()
    assert not bundle.exists()
    with pytest.raises(FileNotFoundError):
        store.resolve("lane-3-golden")


def test_summary_stays_small_when_trace_messages_are_large(tmp_path: Path) -> None:
    record = _record()
    record["events"].append(
        {
            "type": "agent_trace",
            "agent_event": "agent",
            "streaming": False,
            "message": "long conclusion " * 2_000,
        }
    )

    summary = build_run_summary(record, tmp_path)

    assert len(summary) < 8_000
    assert "long conclusion" in summary


def test_four_completed_lanes_are_indexed_without_replacing_older_cards(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path / "data")

    def save(lane_id: int) -> None:
        run_id = f"lane-{lane_id}-concurrent"
        run_dir = store.ensure_run(run_id)
        store.save_record(
            run_id,
            run_dir,
            {
                "run_id": run_id,
                "lane_id": lane_id,
                "status": "ready",
                "prompt": f"query {lane_id}",
                "finished_at": f"2026-09-01T10:0{lane_id}:00+00:00",
                "artifact_storage": "r2",
                "poster_url": f"https://media.example.test/runs/{run_id}/poster.jpg",
                "artifacts": [
                    {
                        "id": "preview",
                        "url": f"https://media.example.test/runs/{run_id}/preview.mp4",
                        "primary": True,
                    }
                ],
                "events": [],
            },
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(save, range(1, 5)))

    history = RunStore(tmp_path / "data").list_history()
    assert [item["run_id"] for item in history] == [
        "lane-4-concurrent",
        "lane-3-concurrent",
        "lane-2-concurrent",
        "lane-1-concurrent",
    ]
