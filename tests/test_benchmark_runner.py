from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from benchmarks.run import (
    apply_task_overrides,
    load_dotenv,
    preflight,
    prepend_project_venv,
    prepend_tex_bin,
    run_once,
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


def fake_task() -> dict:
    return {
        "id": "fake-task",
        "version": 1,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "max_turns": 6,
        "timeout_seconds": 10,
        "approval_response": "Approved",
        "input_fallback": "Use your best judgment from the material and stated requirements.",
        "prompt": "Inspect {repo_root} and work in {workspace}",
        "outputs": {
            "glob": "deliverables/*.mp4",
            "min_count": 0,
            "validation": {},
        },
    }


def run_fake(tmp_path, monkeypatch, *, statuses: str = "needs_approval,complete") -> dict:
    fake_codex = Path(__file__).parent / "fixtures" / "fake_codex.py"
    fake_codex.chmod(0o755)
    monkeypatch.setenv("FAKE_CODEX_COUNTER_FILE", str(tmp_path / "counter.txt"))
    monkeypatch.setenv("FAKE_CODEX_ARGS_FILE", str(tmp_path / "args.jsonl"))
    monkeypatch.setenv("FAKE_CODEX_STATUSES", statuses)
    group_dir = tmp_path / "group"
    group_dir.mkdir()
    return run_once(
        fake_task(),
        run_index=1,
        group_dir=group_dir,
        resolved={},
        codex_bin=str(fake_codex),
        model_price=PRICE,
        elevenlabs_usd_per_1000=None,
        task_timeout_s=None,
    )


def test_runner_approves_strategy_and_resumes_same_session(tmp_path, monkeypatch) -> None:
    summary = run_fake(tmp_path, monkeypatch)

    assert summary["status"] == "complete"
    assert summary["validation"]["passed"] is True
    assert summary["stops"]["expected_approval"] == 1
    assert summary["stops"]["unexpected_input"] == 0
    assert summary["tokens"]["input_tokens"] == 300
    assert summary["tokens"]["cached_input_tokens"] == 75
    assert summary["tokens"]["output_tokens"] == 30
    assert [turn["reported_phase"] for turn in summary["timing"]["turns"]] == [
        "planning",
        "production",
    ]
    assert [turn["reported_status"] for turn in summary["timing"]["turns"]] == [
        "needs_approval",
        "complete",
    ]
    run_dir = next(path for path in (tmp_path / "group").iterdir() if path.is_dir())
    raw_lines = (run_dir / "turn-01-events.raw.jsonl").read_text().splitlines()
    assert raw_lines[0].startswith('{"type": "thread.started"')
    assert all("benchmark.process" not in line for line in raw_lines)
    assert (run_dir / "turn-02-events.raw.jsonl").is_file()
    invocations = [
        json.loads(line)
        for line in (tmp_path / "args.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(invocations) == 2
    assert "resume" not in invocations[0]
    assert "resume" in invocations[1]
    for invocation in invocations:
        config_pairs = [
            invocation[index + 1]
            for index, argument in enumerate(invocation[:-1])
            if argument in {"-c", "--config"}
        ]
        assert 'sandbox_mode="workspace-write"' in config_pairs


def test_runner_counts_unexpected_input_and_blocked_stop(tmp_path, monkeypatch) -> None:
    summary = run_fake(tmp_path, monkeypatch, statuses="needs_input,blocked")
    assert summary["status"] == "blocked"
    assert summary["stops"]["expected_approval"] == 0
    assert summary["stops"]["unexpected_input"] == 1
    assert summary["stops"]["blocked"] == 1


def test_runner_counts_a_second_approval_as_unexpected(tmp_path, monkeypatch) -> None:
    summary = run_fake(
        tmp_path,
        monkeypatch,
        statuses="needs_approval,needs_approval,complete",
    )
    assert summary["status"] == "complete"
    assert summary["stops"]["expected_approval"] == 1
    assert summary["stops"]["unexpected_input"] == 1


def test_task_agent_settings_can_be_overridden_without_mutating_definition() -> None:
    task = fake_task()
    overridden = apply_task_overrides(
        task,
        model="gpt-5.6-luna",
        reasoning_effort="high",
    )

    assert overridden["model"] == "gpt-5.6-luna"
    assert overridden["reasoning_effort"] == "high"
    assert task["model"] == "gpt-5.6-sol"


def test_dotenv_loading_preserves_exported_values(tmp_path, monkeypatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "ELEVENLABS_API_KEY=from-file\nexport ELEVENLABS_VOICE_ID='voice-from-file'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEVENLABS_API_KEY", "already-exported")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    load_dotenv(dotenv)
    assert os.environ["ELEVENLABS_API_KEY"] == "already-exported"
    assert os.environ["ELEVENLABS_VOICE_ID"] == "voice-from-file"


def test_project_venv_is_prepended_once(tmp_path, monkeypatch) -> None:
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    prepend_project_venv(venv)
    prepend_project_venv(venv)
    assert os.environ["PATH"].split(os.pathsep) == [str(venv / "bin"), "/usr/bin", "/bin"]


def test_configured_tex_bin_is_prepended(tmp_path, monkeypatch) -> None:
    tex_bin = tmp_path / "texbin"
    tex_bin.mkdir()
    monkeypatch.setenv("VIDEO_USE_TEX_BIN", str(tex_bin))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    prepend_tex_bin()
    assert os.environ["PATH"].split(os.pathsep)[0] == str(tex_bin)


def test_preflight_rejects_insufficient_elevenlabs_quota(monkeypatch) -> None:
    task = fake_task()
    task["preflight"] = {
        "environment": ["ELEVENLABS_API_KEY"],
        "elevenlabs_min_remaining_credits": 1000,
    }
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setattr("benchmarks.run.elevenlabs_remaining_credits", lambda _: 312)

    with pytest.raises(RuntimeError, match="312 remaining, at least 1000 required"):
        preflight(task, "codex")


def test_preflight_accepts_sufficient_elevenlabs_quota(monkeypatch) -> None:
    task = fake_task()
    task["preflight"] = {
        "environment": ["ELEVENLABS_API_KEY"],
        "elevenlabs_min_remaining_credits": 1000,
    }
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setattr("benchmarks.run.elevenlabs_remaining_credits", lambda _: 1200)

    assert preflight(task, "codex") == {}
