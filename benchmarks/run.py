#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks import SCHEMA_VERSION
from benchmarks.core import (
    TimedEvent,
    aggregate_runs,
    analyze_events,
    dependency_version,
    git_value,
    package_versions,
    read_json,
    resolve_env_path,
    sha256_file,
    sha256_text,
    write_json,
)
from benchmarks.validator import probe_media, validate_task_outputs


REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = Path(__file__).resolve().parent / "tasks"
TURN_SCHEMA = Path(__file__).resolve().parent / "schemas" / "turn-result.schema.json"
PRICE_FILE = Path(__file__).resolve().parent / "prices.json"
DEFAULT_BENCH_ROOT = Path("/Users/ismaelito/Movies/video-use-tests/benchmark-runs")
REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")


@dataclass
class ProcessCapture:
    returncode: int
    started_s: float
    ended_s: float
    events: list[TimedEvent]
    timed_out: bool
    interrupted: bool
    invalid_json_lines: int


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without executing shell syntax or overriding exports."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def prepend_project_venv(path: Path) -> None:
    """Make repository-managed tools available to preflight and Codex child processes."""
    bin_dir = path / ("Scripts" if os.name == "nt" else "bin")
    if not bin_dir.is_dir():
        return
    current = os.environ.get("PATH", "")
    entries = current.split(os.pathsep) if current else []
    if str(bin_dir) not in entries:
        os.environ["PATH"] = os.pathsep.join([str(bin_dir), *entries])


def prepend_tex_bin() -> None:
    """Expose system or user-local TeX without requiring a shell restart."""
    configured = os.environ.get("VIDEO_USE_TEX_BIN")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(Path("/Library/TeX/texbin"))
    local_root = Path.home() / ".local" / "share" / "video-use-basictex-2026"
    candidates.extend(sorted(local_root.glob(
        "BasicTeX-*-Start.pkg/Payload/usr/local/texlive/*basic/bin/universal-darwin"
    )))
    current = os.environ.get("PATH", "")
    entries = current.split(os.pathsep) if current else []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        candidate_value = str(candidate)
        entries = [entry for entry in entries if entry != candidate_value]
        entries.insert(0, candidate_value)
        break
    os.environ["PATH"] = os.pathsep.join(entries)


def available_tasks() -> dict[str, Path]:
    return {path.stem: path for path in sorted(TASKS_DIR.glob("*.json"))}


def load_task(name: str) -> dict[str, Any]:
    tasks = available_tasks()
    if name not in tasks:
        raise ValueError(f"unknown task {name!r}; choose from {', '.join(tasks)}")
    task = read_json(tasks[name])
    if task.get("id") != name:
        raise ValueError(f"task id {task.get('id')!r} does not match filename {name!r}")
    return task


def apply_task_overrides(
    task: dict[str, Any],
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Return a task copy with run-scoped agent settings overridden."""
    resolved = dict(task)
    if model:
        resolved["model"] = model
    if reasoning_effort:
        resolved["reasoning_effort"] = reasoning_effort
    return resolved


def elevenlabs_remaining_credits(api_key: str, *, timeout_s: float = 10.0) -> int:
    """Return prepaid ElevenLabs credits without exposing the credential."""
    request = urllib.request.Request(
        "https://api.elevenlabs.io/v1/user/subscription",
        headers={"xi-api-key": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not verify ElevenLabs quota: {exc}") from exc
    try:
        used = int(payload["character_count"])
        limit = int(payload["character_limit"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("ElevenLabs subscription response omitted credit usage") from exc
    return max(0, limit - used)


def preflight(task: dict[str, Any], codex_bin: str) -> dict[str, Path]:
    errors: list[str] = []
    resolved: dict[str, Path] = {}
    executables = list(task.get("preflight", {}).get("executables", []))
    if "codex" in executables:
        executables.remove("codex")
        if not (Path(codex_bin).is_file() or shutil.which(codex_bin)):
            errors.append(f"missing executable: {codex_bin}")
    for executable in executables:
        if not shutil.which(executable):
            errors.append(f"missing executable: {executable}")
    for name in task.get("preflight", {}).get("environment", []):
        if not os.environ.get(name):
            errors.append(f"missing environment variable: {name}")

    minimum_credits = task.get("preflight", {}).get("elevenlabs_min_remaining_credits")
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if minimum_credits is not None and api_key:
        try:
            remaining_credits = elevenlabs_remaining_credits(api_key)
            if remaining_credits < int(minimum_credits):
                errors.append(
                    "insufficient ElevenLabs credits: "
                    f"{remaining_credits} remaining, at least {int(minimum_credits)} required"
                )
        except RuntimeError as exc:
            errors.append(str(exc))

    if task.get("source"):
        try:
            source = resolve_env_path(task["source"])
            resolved["source"] = source
            if not source.is_file():
                errors.append(f"source video not found: {source}")
            elif task["source"].get("expected_duration_s") is not None:
                probe = probe_media(source)
                actual_duration = float(probe.get("duration_s", 0.0)) if probe.get("ok") else 0.0
                expected_duration = float(task["source"]["expected_duration_s"])
                tolerance = float(task["source"].get("duration_tolerance_s", 1.0))
                if not probe.get("ok") or abs(actual_duration - expected_duration) > tolerance:
                    errors.append(
                        f"source duration {actual_duration:.3f}s does not match "
                        f"{expected_duration:.3f}s (+/- {tolerance:.3f}s)"
                    )
        except ValueError as exc:
            errors.append(str(exc))
    if task.get("transcript"):
        try:
            transcript = resolve_env_path(task["transcript"])
            resolved["transcript"] = transcript
            if not transcript.is_file():
                errors.append(
                    f"cached transcript not found: {transcript}; prepare it before the measured run"
                )
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise RuntimeError("preflight failed:\n  - " + "\n  - ".join(errors))
    return resolved


def prepare_workspace(
    task: dict[str, Any],
    workspace: Path,
    resolved: dict[str, Path],
) -> tuple[str, dict[str, Any]]:
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "deliverables").mkdir()
    source_target = ""
    transcript_target = ""
    if "source" in resolved:
        source_target_path = workspace / str(task["source"]["workspace_name"])
        source_target_path.symlink_to(resolved["source"])
        source_target = str(source_target_path)
    if "transcript" in resolved:
        transcript_target_path = workspace / str(task["transcript"]["workspace_relative"])
        transcript_target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved["transcript"], transcript_target_path)
        transcript_target = str(transcript_target_path)

    prompt = str(task["prompt"]).format(
        repo_root=REPO_ROOT,
        workspace=workspace,
        source=source_target,
        transcript=transcript_target,
    )
    resolved_task = {
        "id": task["id"],
        "version": task["version"],
        "prompt_sha256": sha256_text(str(task["prompt"])),
        "resolved_prompt_sha256": sha256_text(prompt),
        "definition_sha256": sha256_text(
            json.dumps(task, sort_keys=True, separators=(",", ":"))
        ),
        "model": task["model"],
        "reasoning_effort": task["reasoning_effort"],
        "outputs": task["outputs"],
    }
    write_json(workspace / "benchmark_task.json", resolved_task)
    (workspace / "benchmark_prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    return prompt, resolved_task


def _capture_jsonl_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    raw_path: Path,
    timed_path: Path,
    stderr_path: Path,
    turn_index: int,
    timeout_s: float,
) -> ProcessCapture:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    started_s = time.monotonic()
    started_event = TimedEvent(
        turn_index=turn_index,
        monotonic_s=started_s,
        event={"type": "benchmark.process.started"},
    )
    events: list[TimedEvent] = [started_event]
    invalid_lines = 0
    lock = threading.Lock()
    timed_path.write_text(json.dumps({
        "turn_index": turn_index,
        "monotonic_s": started_s,
        "wall_time": _utc_now(),
        "event": started_event.event,
    }, sort_keys=True) + "\n", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def read_stdout() -> None:
        nonlocal invalid_lines
        assert process.stdout is not None
        with raw_path.open("w", encoding="utf-8") as raw_handle, timed_path.open(
            "a", encoding="utf-8"
        ) as timed_handle:
            for line in process.stdout:
                raw_handle.write(line)
                raw_handle.flush()
                now = time.monotonic()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines += 1
                    continue
                record = TimedEvent(turn_index=turn_index, monotonic_s=now, event=event)
                with lock:
                    events.append(record)
                wrapper = {
                    "turn_index": turn_index,
                    "monotonic_s": now,
                    "wall_time": _utc_now(),
                    "event": event,
                }
                timed_handle.write(json.dumps(wrapper, sort_keys=True) + "\n")
                timed_handle.flush()

    def read_stderr() -> None:
        assert process.stderr is not None
        with stderr_path.open("w", encoding="utf-8") as handle:
            for line in process.stderr:
                handle.write(line)
                handle.flush()

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    interrupted = False
    try:
        returncode = process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.terminate()
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        process.terminate()
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
    stdout_thread.join(timeout=10)
    stderr_thread.join(timeout=10)
    ended_s = time.monotonic()
    completion = TimedEvent(
        turn_index=turn_index,
        monotonic_s=ended_s,
        event={
            "type": "benchmark.process.completed",
            "returncode": returncode,
            "timed_out": timed_out,
            "interrupted": interrupted,
        },
    )
    events.append(completion)
    with timed_path.open("a", encoding="utf-8") as timed_handle:
        timed_handle.write(json.dumps({
            "turn_index": turn_index,
            "monotonic_s": ended_s,
            "wall_time": _utc_now(),
            "event": completion.event,
        }, sort_keys=True) + "\n")
    return ProcessCapture(
        returncode=returncode,
        started_s=started_s,
        ended_s=ended_s,
        events=events,
        timed_out=timed_out,
        interrupted=interrupted,
        invalid_json_lines=invalid_lines,
    )


def _thread_id(events: list[TimedEvent]) -> str | None:
    for record in events:
        event = record.event
        if event.get("type") == "thread.started" and event.get("thread_id"):
            return str(event["thread_id"])
        if event.get("thread_id") and event.get("type") in {"task_started", "turn.started"}:
            return str(event["thread_id"])
    return None


def _turn_result(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or value.get("status") not in {
        "needs_approval", "needs_input", "complete", "blocked"
    }:
        return None
    return value


def _codex_common(task: dict[str, Any], codex_bin: str, result_path: Path) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-m", str(task["model"]),
        "-c", f'model_reasoning_effort="{task["reasoning_effort"]}"',
        "-c", 'approval_policy="never"',
        "-c", 'sandbox_mode="workspace-write"',
        "-c", "sandbox_workspace_write.network_access=true",
        "--output-schema", str(TURN_SCHEMA),
        "-o", str(result_path),
    ]


def _initial_command(
    task: dict[str, Any], codex_bin: str, workspace: Path, result_path: Path, prompt: str
) -> list[str]:
    command = _codex_common(task, codex_bin, result_path)
    command.extend(["-C", str(workspace), "-s", "workspace-write", prompt])
    return command


def _resume_command(
    task: dict[str, Any], codex_bin: str, result_path: Path, thread_id: str, prompt: str
) -> list[str]:
    command = _codex_common(task, codex_bin, result_path)
    command.insert(2, "resume")
    command.extend([thread_id, prompt])
    return command


def _collect_tts_metrics(workspace: Path, usd_per_1000: float | None) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in workspace.glob("**/*.tts_metrics.json"):
        try:
            records.append(read_json(path))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    character_units = sum(
        float(
            record.get("character_cost")
            if record.get("character_cost") is not None
            else record.get("estimated_character_units", record.get("text_characters", 0))
        )
        for record in records
    )
    estimated = character_units / 1000.0 * usd_per_1000 if usd_per_1000 is not None else None
    return {
        "requests": len(records),
        "failed_requests": sum(not bool(record.get("succeeded", True)) for record in records),
        "text_characters": sum(int(record.get("text_characters", 0)) for record in records),
        "character_cost_units": character_units,
        "latency_s": sum(float(record.get("latency_s", 0.0)) for record in records),
        "estimated_usd": estimated,
    }


def _environment_metadata(
    task: dict[str, Any], workspace: Path, resolved: dict[str, Path], codex_bin: str
) -> dict[str, Any]:
    source = resolved.get("source")
    transcript = resolved.get("transcript")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
    return {
        "model": task["model"],
        "reasoning_effort": task["reasoning_effort"],
        "codex_version": dependency_version([codex_bin, "--version"]),
        "ffmpeg_version": dependency_version(["ffmpeg", "-version"]),
        "ffprobe_version": dependency_version(["ffprobe", "-version"]),
        "manim_version": dependency_version(["manim", "--version"]),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "git_commit": git_value(REPO_ROOT, "rev-parse", "HEAD"),
        "git_branch": git_value(REPO_ROOT, "branch", "--show-current"),
        "git_dirty": bool(git_value(REPO_ROOT, "status", "--porcelain")),
        "skill_commit": git_value(REPO_ROOT, "rev-list", "-1", "HEAD", "--", "SKILL.md"),
        "skill_sha256": sha256_file(REPO_ROOT / "SKILL.md"),
        "source_sha256": sha256_file(source) if source else None,
        "transcript_sha256": sha256_file(transcript) if transcript else None,
        "elevenlabs_voice_id_sha256": sha256_text(voice_id) if voice_id else None,
        "dependency_versions": package_versions(
            ("requests", "numpy", "pillow", "librosa", "matplotlib", "manim")
        ),
        "source_path": str(source) if source else None,
        "workspace": str(workspace),
    }


def run_once(
    task: dict[str, Any],
    *,
    run_index: int,
    group_dir: Path,
    resolved: dict[str, Path],
    codex_bin: str,
    model_price: dict[str, Any],
    elevenlabs_usd_per_1000: float | None,
    task_timeout_s: float | None,
) -> dict[str, Any]:
    run_id = f"run-{run_index:02d}-{uuid.uuid4().hex[:8]}"
    run_dir = group_dir / run_id
    workspace = run_dir / "workspace"
    prompt, task_identity = prepare_workspace(task, workspace, resolved)
    environment_metadata = _environment_metadata(task, workspace, resolved, codex_bin)
    benchmark_started_s = time.monotonic()
    child_environment = os.environ.copy()
    child_environment.update({
        "VIDEO_USE_BENCHMARK_RUN_ID": run_id,
        "VIDEO_USE_REPO_ROOT": str(REPO_ROOT),
    })

    events: list[TimedEvent] = []
    thread_id: str | None = None
    next_prompt = prompt
    expected_approval = 0
    unexpected_input = 0
    blocked_stops = 0
    interrupted_stops = 0
    invalid_results = 0
    process_failures = 0
    invalid_json_lines = 0
    final_status = "max_turns"
    first_process_start: float | None = None
    turn_results: dict[int, dict[str, Any]] = {}
    timeout = float(task_timeout_s if task_timeout_s is not None else task["timeout_seconds"])
    deadline_s = benchmark_started_s + timeout

    for turn_index in range(1, int(task["max_turns"]) + 1):
        remaining_s = deadline_s - time.monotonic()
        if remaining_s <= 0:
            final_status = "timeout"
            break
        result_path = run_dir / f"turn-{turn_index:02d}-result.json"
        if turn_index == 1:
            command = _initial_command(task, codex_bin, workspace, result_path, next_prompt)
        else:
            if not thread_id:
                final_status = "missing_thread_id"
                break
            command = _resume_command(task, codex_bin, result_path, thread_id, next_prompt)
        capture = _capture_jsonl_process(
            command,
            cwd=workspace,
            environment=child_environment,
            raw_path=run_dir / f"turn-{turn_index:02d}-events.raw.jsonl",
            timed_path=run_dir / f"turn-{turn_index:02d}-events.timed.jsonl",
            stderr_path=run_dir / f"turn-{turn_index:02d}-stderr.log",
            turn_index=turn_index,
            timeout_s=remaining_s,
        )
        if first_process_start is None:
            first_process_start = capture.started_s
        events.extend(capture.events)
        invalid_json_lines += capture.invalid_json_lines
        thread_id = thread_id or _thread_id(capture.events)
        if capture.interrupted:
            interrupted_stops += 1
            final_status = "interrupted"
            break
        if capture.returncode != 0 or capture.timed_out:
            process_failures += 1
            final_status = "timeout" if capture.timed_out else "process_error"
            break
        result = _turn_result(result_path)
        if result is None:
            invalid_results += 1
            final_status = "invalid_turn_result"
            break
        turn_results[turn_index] = result
        status = result["status"]
        if status == "complete":
            final_status = "complete"
            break
        if status == "blocked":
            blocked_stops += 1
            final_status = "blocked"
            break
        if status == "needs_approval" and expected_approval == 0:
            expected_approval += 1
            next_prompt = str(task["approval_response"])
        else:
            unexpected_input += 1
            next_prompt = str(task["input_fallback"])

    if first_process_start is None:
        first_process_start = benchmark_started_s
    agent_metrics = analyze_events(
        events,
        process_start_s=first_process_start,
        model_price=model_price,
    )
    for turn_summary in agent_metrics["timing"]["turns"]:
        reported = turn_results.get(int(turn_summary["turn_index"]), {})
        turn_summary["reported_phase"] = reported.get("phase")
        turn_summary["reported_status"] = reported.get("status")
    agent_metrics["steps"]["invalid_json_lines"] = invalid_json_lines
    validation_started_s = time.monotonic()
    validation = validate_task_outputs(workspace, task)
    validation_wall_time_s = time.monotonic() - validation_started_s
    tts = _collect_tts_metrics(workspace, elevenlabs_usd_per_1000)
    benchmark_ended_s = time.monotonic()
    benchmark_wall_time_s = benchmark_ended_s - benchmark_started_s
    agent_metrics["timing"]["benchmark_wall_time_s"] = benchmark_wall_time_s
    agent_metrics["timing"]["validation_wall_time_s"] = validation_wall_time_s
    agent_metrics["timing"]["harness_overhead_s"] = max(
        0.0,
        benchmark_wall_time_s - agent_metrics["timing"]["agent_wall_time_s"],
    )

    codex_cost = float(agent_metrics["estimated_codex_cost_usd"])
    total_cost = codex_cost + tts["estimated_usd"] if tts["estimated_usd"] is not None else (
        codex_cost if tts["requests"] == 0 else None
    )
    clip_count = int(validation["clip_count"])
    output_duration_s = float(validation["total_duration_s"])
    output_minutes = output_duration_s / 60.0
    tokens = agent_metrics["tokens"]
    steps = agent_metrics["steps"]

    def per(value: float | int | None, denominator: float) -> float | None:
        if value is None or denominator <= 0:
            return None
        return float(value) / denominator

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "task": task_identity,
        "agent": {"adapter": "codex-exec-jsonl", "adapter_version": 1},
        "environment": environment_metadata,
        "status": final_status,
        "timing": agent_metrics["timing"],
        "tokens": tokens,
        "cost": {
            "label": "API-equivalent estimate; not ChatGPT subscription billing",
            "price_version": read_json(PRICE_FILE)["version"],
            "codex_api_equivalent_usd": codex_cost,
            "elevenlabs_estimated_usd": tts["estimated_usd"],
            "elevenlabs_character_cost_units": tts["character_cost_units"],
            "elevenlabs_requests": tts["requests"],
            "elevenlabs_failed_requests": tts["failed_requests"],
            "elevenlabs_latency_s": tts["latency_s"],
            "total_estimated_usd": total_cost,
        },
        "steps": steps,
        "stops": {
            "expected_approval": expected_approval,
            "unexpected_input": unexpected_input,
            "blocked": blocked_stops,
            "interrupted": interrupted_stops,
            "invalid_results": invalid_results,
            "process_failures": process_failures,
        },
        "operations": agent_metrics["operations"],
        "iterations": agent_metrics["iterations"],
        "outputs": {
            "clip_count": clip_count,
            "total_duration_s": output_duration_s,
            "artifacts": validation["artifacts"],
        },
        "normalized": {
            "cost_per_clip_usd": per(total_cost, clip_count),
            "cost_per_output_minute_usd": per(total_cost, output_minutes),
            "tokens_per_clip": per(tokens["total_tokens"], clip_count),
            "tokens_per_output_minute": per(tokens["total_tokens"], output_minutes),
            "steps_per_clip": per(steps["completed_items"], clip_count),
            "steps_per_output_minute": per(steps["completed_items"], output_minutes),
            "latency_per_clip_s": per(agent_metrics["timing"]["agent_wall_time_s"], clip_count),
            "latency_per_output_minute_s": per(agent_metrics["timing"]["agent_wall_time_s"], output_minutes),
        },
        "validation": {
            "passed": validation["passed"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        },
    }
    write_json(run_dir / "summary.json", summary)
    return summary


def _price_rate(cli_value: float | None, price_book: dict[str, Any]) -> float | None:
    if cli_value is not None:
        return cli_value
    raw = os.environ.get("ELEVENLABS_USD_PER_1000_CHARACTERS", "")
    if raw:
        return float(raw)
    value = price_book.get("elevenlabs", {}).get("tts_usd_per_1000_characters")
    return float(value) if value is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run measured Video Use agent benchmarks")
    parser.add_argument("--task", required=True, choices=sorted(available_tasks()))
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument(
        "--model",
        default=None,
        help="Override the task model for this run without changing its definition file",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=REASONING_EFFORTS,
        default=None,
        help="Override reasoning effort for this run without changing its definition file",
    )
    parser.add_argument("--bench-root", type=Path, default=Path(os.environ.get("VIDEO_USE_BENCH_ROOT", DEFAULT_BENCH_ROOT)))
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Override the total timeout for each complete task run",
    )
    parser.add_argument("--elevenlabs-usd-per-1000-characters", type=float, default=None)
    parser.add_argument("--export-baseline", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate prerequisites without invoking Codex")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.timeout_seconds is not None and args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")
    if (
        args.elevenlabs_usd_per_1000_characters is not None
        and args.elevenlabs_usd_per_1000_characters < 0
    ):
        parser.error("--elevenlabs-usd-per-1000-characters cannot be negative")

    load_dotenv(REPO_ROOT / ".env")
    prepend_project_venv(REPO_ROOT / ".venv")
    prepend_tex_bin()
    task = apply_task_overrides(
        load_task(args.task),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
    )
    try:
        resolved = preflight(task, args.codex_bin)
    except RuntimeError as exc:
        parser.exit(2, f"{exc}\n")
    price_book = read_json(PRICE_FILE)
    model_price = price_book["models"].get(task["model"])
    if model_price is None:
        parser.error(f"no price entry for model {task['model']}")
    try:
        tts_rate = _price_rate(args.elevenlabs_usd_per_1000_characters, price_book)
    except ValueError:
        parser.error("ElevenLabs price rate must be numeric")
    if tts_rate is not None and tts_rate < 0:
        parser.error("ElevenLabs price rate cannot be negative")

    if args.dry_run:
        print(json.dumps({
            "task": task["id"],
            "version": task["version"],
            "repeat": args.repeat,
            "model": task["model"],
            "reasoning_effort": task["reasoning_effort"],
            "bench_root": str(args.bench_root.resolve()),
            "resolved_inputs": {key: str(value) for key, value in resolved.items()},
            "elevenlabs_rate_configured": tts_rate is not None,
            "paid_work_started": False,
        }, indent=2))
        return

    group_name = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{task['id']}"
    group_dir = args.bench_root.expanduser().resolve() / task["id"] / group_name
    group_dir.mkdir(parents=True, exist_ok=False)
    runs: list[dict[str, Any]] = []
    for run_index in range(1, args.repeat + 1):
        print(f"[{run_index}/{args.repeat}] running {task['id']}", flush=True)
        try:
            summary = run_once(
                task,
                run_index=run_index,
                group_dir=group_dir,
                resolved=resolved,
                codex_bin=args.codex_bin,
                model_price=model_price,
                elevenlabs_usd_per_1000=tts_rate,
                task_timeout_s=args.timeout_seconds,
            )
        except KeyboardInterrupt:
            summary = {
                "schema_version": SCHEMA_VERSION,
                "run_id": f"run-{run_index:02d}-interrupted",
                "task": {"id": task["id"], "version": task["version"], "prompt_sha256": None},
                "agent": {"adapter": "codex-exec-jsonl", "adapter_version": 1},
                "environment": {"model": task["model"], "reasoning_effort": task["reasoning_effort"]},
                "status": "interrupted",
                "stops": {"interrupted": 1},
                "validation": {"passed": False, "errors": ["benchmark interrupted"], "warnings": []},
            }
            write_json(group_dir / f"run-{run_index:02d}-interrupted.json", summary)
        except Exception as exc:
            summary = {
                "schema_version": SCHEMA_VERSION,
                "run_id": f"run-{run_index:02d}-harness-error",
                "task": {"id": task["id"], "version": task["version"], "prompt_sha256": None},
                "agent": {"adapter": "codex-exec-jsonl", "adapter_version": 1},
                "environment": {"model": task["model"], "reasoning_effort": task["reasoning_effort"]},
                "status": "harness_error",
                "validation": {"passed": False, "errors": [str(exc)], "warnings": []},
            }
            write_json(group_dir / f"run-{run_index:02d}-harness-error.json", summary)
        runs.append(summary)
        if summary["status"] == "interrupted":
            break

    aggregate = aggregate_runs(runs)
    write_json(group_dir / "baseline.json", aggregate)
    if args.export_baseline:
        write_json(args.export_baseline.resolve(), aggregate)
    print(f"baseline: {group_dir / 'baseline.json'}")
    print(f"success rate: {aggregate['successful_runs']}/{aggregate['run_count']}")


if __name__ == "__main__":
    main()
