from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import re
import shlex
import statistics
import subprocess
from copy import deepcopy
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from benchmarks import SCHEMA_VERSION


TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)

PHASES = (
    "inventory",
    "transcription_cache",
    "transcript_packing",
    "strategy",
    "edl_creation",
    "animation",
    "tts",
    "rendering",
    "verification",
    "finalization",
)

PHASE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "transcription_cache",
        (
            "transcribe.py",
            "transcribe_batch.py",
            "speech-to-text",
            "jensen_test1.json",
            "transcripts/",
        ),
    ),
    ("transcript_packing", ("pack_transcripts.py", "takes_packed.md", "packed.md")),
    ("verification", ("timeline_view.py", "volumedetect", "ffprobe", " -f null")),
    ("tts", ("elevenlabs_tts.py", "text-to-speech", "narration.mp3")),
    ("animation", ("manim", "hyperframes", "remotion", "script.py", "scene.py")),
    ("rendering", ("render.py", "ffmpeg", "final.mp4", "preview.mp4")),
    ("edl_creation", ("edl.json", "master.srt", "deliverables/", ".srt")),
    ("inventory", ("find ", "rg --files", "ls ", "stat ", "wc ", "file ")),
)


@dataclass(frozen=True)
class TimedEvent:
    turn_index: int
    monotonic_s: float
    event: dict[str, Any]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def load_timed_events(path: Path) -> list[TimedEvent]:
    events: list[TimedEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                wrapper = json.loads(line)
                events.append(TimedEvent(
                    turn_index=int(wrapper["turn_index"]),
                    monotonic_s=float(wrapper["monotonic_s"]),
                    event=wrapper["event"],
                ))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid timed event at {path}:{line_number}: {exc}") from exc
    return events


def classify_command(command: str) -> str:
    lowered = command.lower()
    for phase, needles in PHASE_PATTERNS:
        if any(needle in lowered for needle in needles):
            return phase
    return "finalization"


def _item_from_event(event: dict[str, Any]) -> dict[str, Any]:
    item = event.get("item")
    if isinstance(item, dict):
        return item
    payload = event.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("item"), dict):
        return payload["item"]
    return {}


def _event_type(event: dict[str, Any]) -> str:
    outer = str(event.get("type", "unknown"))
    payload = event.get("payload")
    if outer == "event_msg" and isinstance(payload, dict):
        return str(payload.get("type", outer))
    return outer


def _command_from_item(item: dict[str, Any]) -> str:
    command = item.get("command") or item.get("input") or ""
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    if isinstance(command, dict):
        return json.dumps(command, sort_keys=True)
    return str(command)


def _item_type(item: dict[str, Any]) -> str:
    return str(item.get("type") or item.get("name") or "unknown")


def _is_failed_item(item: dict[str, Any]) -> bool:
    status = str(item.get("status", "")).lower()
    exit_code = item.get("exit_code")
    return status in {"failed", "error", "cancelled"} or (
        isinstance(exit_code, int) and exit_code != 0
    )


def command_fingerprint(command: str) -> str:
    """Return a stable retry/rerender fingerprint without retaining full paths."""
    phase = classify_command(command)
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    targets: list[str] = []
    for index, part in enumerate(parts):
        if part in {"-o", "--output"} and index + 1 < len(parts):
            targets.append(Path(parts[index + 1]).name)
        elif Path(part).suffix.lower() in {".mp4", ".mov", ".webm", ".json", ".srt"}:
            targets.append(Path(part).name)
    if targets:
        identity = "|".join(targets[-2:])
    elif parts:
        identity = Path(parts[0]).name
    else:
        identity = "unknown"
    return f"{phase}:{identity}"


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    usage = usage or {}
    normalized = {key: int(usage.get(key, 0) or 0) for key in TOKEN_KEYS}
    if not normalized["reasoning_output_tokens"]:
        normalized["reasoning_output_tokens"] = int(usage.get("reasoning_tokens", 0) or 0)
    if not normalized["total_tokens"]:
        normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"]
    return normalized


def estimate_codex_cost(
    usage: dict[str, int],
    price: dict[str, Any],
) -> dict[str, float]:
    input_tokens = usage["input_tokens"]
    cached_tokens = min(usage["cached_input_tokens"], input_tokens)
    cache_write_tokens = usage.get("cache_write_input_tokens", 0)
    uncached_tokens = max(0, input_tokens - cached_tokens - cache_write_tokens)
    threshold = int(price.get("long_context_threshold_tokens", 0) or 0)
    is_long = bool(threshold and input_tokens > threshold)
    input_multiplier = float(price.get("long_context_input_multiplier", 1.0)) if is_long else 1.0
    output_multiplier = float(price.get("long_context_output_multiplier", 1.0)) if is_long else 1.0
    per_million = 1_000_000.0
    uncached_usd = uncached_tokens / per_million * float(price["input_usd_per_million"]) * input_multiplier
    cached_usd = cached_tokens / per_million * float(price["cached_input_usd_per_million"]) * input_multiplier
    cache_write_usd = cache_write_tokens / per_million * float(
        price.get("cache_write_input_usd_per_million", price["input_usd_per_million"])
    ) * input_multiplier
    output_usd = usage["output_tokens"] / per_million * float(price["output_usd_per_million"]) * output_multiplier
    return {
        "uncached_input_usd": uncached_usd,
        "cached_input_usd": cached_usd,
        "cache_write_input_usd": cache_write_usd,
        "output_usd": output_usd,
        "total_usd": uncached_usd + cached_usd + cache_write_usd + output_usd,
        "long_context_pricing_applied": is_long,
    }


def _usage_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    if _event_type(event) == "turn.completed" and isinstance(event.get("usage"), dict):
        return event["usage"]
    payload = event.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "token_count":
        info = payload.get("info")
        if isinstance(info, dict):
            value = info.get("last_token_usage")
            return value if isinstance(value, dict) else None
    return None


def analyze_events(
    events: Iterable[TimedEvent],
    *,
    process_start_s: float,
    model_price: dict[str, Any],
) -> dict[str, Any]:
    ordered = sorted(events, key=lambda record: record.monotonic_s)
    started_items: dict[tuple[int, str], TimedEvent] = {}
    item_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    phase_counts: Counter[str] = Counter()
    phase_duration: defaultdict[str, float] = defaultdict(float)
    failures = 0
    retries = 0
    render_attempts = 0
    rerenders = 0
    self_eval_passes = 0
    subagents = 0
    failed_fingerprints: set[str] = set()
    rendered_fingerprints: Counter[str] = Counter()
    turn_usage: dict[int, dict[str, int]] = {}
    turn_bounds: defaultdict[int, list[float]] = defaultdict(list)
    first_item_s: float | None = None

    for record in ordered:
        event = record.event
        kind = _event_type(event)
        event_counts[kind] += 1
        turn_bounds[record.turn_index].append(record.monotonic_s)
        item = _item_from_event(event)
        item_id = str(item.get("id", ""))
        item_type = _item_type(item)

        if kind == "item.started" and item_id:
            started_items[(record.turn_index, item_id)] = record
            if first_item_s is None:
                first_item_s = record.monotonic_s

        if kind == "item.completed" and item:
            item_counts[item_type] += 1
            command = _command_from_item(item)
            searchable = command or json.dumps(item, sort_keys=True)
            if command:
                phase = classify_command(command)
            elif record.turn_index == 1 and item_type in {"agent_message", "reasoning"}:
                phase = "strategy"
            else:
                phase = classify_command(searchable)
            phase_counts[phase] += 1
            started = started_items.get((record.turn_index, item_id))
            if started:
                phase_duration[phase] += max(0.0, record.monotonic_s - started.monotonic_s)
            failed = _is_failed_item(item)
            fingerprint = command_fingerprint(command) if command else f"{phase}:{item_type}"
            if failed:
                failures += 1
                failed_fingerprints.add(fingerprint)
            elif fingerprint in failed_fingerprints:
                retries += 1
                failed_fingerprints.remove(fingerprint)
            is_render = phase == "rendering" or (
                phase == "animation" and "manim" in command.lower()
            )
            if is_render:
                render_attempts += 1
                rendered_fingerprints[fingerprint] += 1
                if rendered_fingerprints[fingerprint] > 1:
                    rerenders += 1
            if "timeline_view.py" in command.lower():
                self_eval_passes += 1
            if (
                item_type in {"agent_tool_call", "subagent", "agent"}
                or "spawn_agent" in searchable.lower()
            ):
                subagents += 1

        usage = _usage_from_event(event)
        if usage is not None:
            turn_usage[record.turn_index] = normalize_usage(usage)

    total_usage = {key: 0 for key in TOKEN_KEYS}
    turn_summaries: list[dict[str, Any]] = []
    total_cost = 0.0
    agent_wall_time_s = 0.0
    for turn_index in sorted(turn_bounds):
        bounds = turn_bounds[turn_index]
        usage = turn_usage.get(turn_index, normalize_usage(None))
        for key in TOKEN_KEYS:
            total_usage[key] += usage[key]
        cost = estimate_codex_cost(usage, model_price)
        total_cost += cost["total_usd"]
        duration_s = max(bounds) - min(bounds) if bounds else 0.0
        agent_wall_time_s += duration_s
        turn_summaries.append({
            "turn_index": turn_index,
            "duration_s": duration_s,
            "tokens": usage,
            "estimated_codex_cost": cost,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "timing": {
            "agent_wall_time_s": agent_wall_time_s,
            "turn_count": len(turn_summaries),
            "time_to_first_item_s": (
                max(0.0, first_item_s - process_start_s) if first_item_s is not None else None
            ),
            "turns": turn_summaries,
        },
        "tokens": total_usage,
        "estimated_codex_cost_usd": total_cost,
        "steps": {
            "completed_items": sum(item_counts.values()),
            "commands": item_counts["command_execution"],
            "tool_calls": sum(
                item_counts[item_type]
                for item_type in (
                    "mcp_tool_call",
                    "web_search",
                    "tool_call",
                    "agent_tool_call",
                    "collab_tool_call",
                    "dynamic_tool_call",
                )
            ),
            "file_changes": item_counts["file_change"],
            "reasoning_items": item_counts["reasoning"],
            "item_types": dict(sorted(item_counts.items())),
            "event_types": dict(sorted(event_counts.items())),
            "subagents_spawned": subagents,
        },
        "operations": {
            phase: {
                "count": phase_counts[phase],
                "duration_s": phase_duration[phase],
            }
            for phase in PHASES
        },
        "iterations": {
            "command_failures": failures,
            "successful_retries": retries,
            "render_attempts": render_attempts,
            "rerenders": rerenders,
            "self_eval_passes": self_eval_passes,
        },
    }


def numeric_stats(values: list[float]) -> dict[str, float] | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not finite:
        return None
    return {
        "median": statistics.median(finite),
        "min": min(finite),
        "max": max(finite),
    }


def nested_get(value: dict[str, Any], dotted_path: str) -> Any:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


AGGREGATE_METRICS = (
    "timing.agent_wall_time_s",
    "timing.benchmark_wall_time_s",
    "timing.harness_overhead_s",
    "timing.validation_wall_time_s",
    "timing.turn_count",
    "tokens.input_tokens",
    "tokens.cached_input_tokens",
    "tokens.cache_write_input_tokens",
    "tokens.output_tokens",
    "tokens.reasoning_output_tokens",
    "tokens.total_tokens",
    "cost.codex_api_equivalent_usd",
    "cost.elevenlabs_estimated_usd",
    "cost.elevenlabs_character_cost_units",
    "cost.elevenlabs_requests",
    "cost.elevenlabs_failed_requests",
    "cost.elevenlabs_latency_s",
    "cost.total_estimated_usd",
    "steps.completed_items",
    "steps.commands",
    "steps.tool_calls",
    "steps.file_changes",
    "steps.reasoning_items",
    "steps.subagents_spawned",
    "stops.expected_approval",
    "stops.unexpected_input",
    "stops.blocked",
    "stops.interrupted",
    "iterations.command_failures",
    "iterations.successful_retries",
    "iterations.render_attempts",
    "iterations.rerenders",
    "iterations.self_eval_passes",
    "outputs.clip_count",
    "outputs.total_duration_s",
    "normalized.cost_per_clip_usd",
    "normalized.cost_per_output_minute_usd",
    "normalized.tokens_per_clip",
    "normalized.tokens_per_output_minute",
    "normalized.steps_per_clip",
    "normalized.steps_per_output_minute",
    "normalized.latency_per_clip_s",
    "normalized.latency_per_output_minute_s",
)


def aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        raise ValueError("cannot aggregate an empty run list")
    reference_run = next(
        (run for run in runs if run.get("task", {}).get("prompt_sha256")),
        runs[0],
    )
    task = reference_run["task"]
    metrics: dict[str, Any] = {}
    aggregate_metrics = list(AGGREGATE_METRICS)
    for phase in PHASES:
        aggregate_metrics.extend((f"operations.{phase}.count", f"operations.{phase}.duration_s"))
    for metric in aggregate_metrics:
        values = [nested_get(run, metric) for run in runs]
        metrics[metric] = numeric_stats([value for value in values if isinstance(value, (int, float))])
    successes = sum(bool(run.get("validation", {}).get("passed")) for run in runs)
    input_keys = (
        "source_sha256",
        "transcript_sha256",
        "elevenlabs_voice_id_sha256",
    )
    inputs: dict[str, Any] = {}
    inputs_consistent = True
    for key in input_keys:
        values = [
            run.get("environment", {}).get(key)
            for run in runs
            if run.get("environment", {}).get(key) is not None
        ]
        inputs[key] = values[0] if values else None
        inputs_consistent = inputs_consistent and len(set(values)) <= 1
    implementation_keys = ("git_commit", "skill_commit", "skill_sha256")
    implementation: dict[str, Any] = {}
    implementation_consistent = True
    for key in implementation_keys:
        values = [
            run.get("environment", {}).get(key)
            for run in runs
            if run.get("environment", {}).get(key) is not None
        ]
        implementation[key] = values[0] if values else None
        implementation_consistent = implementation_consistent and len(set(values)) <= 1
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "video-use-agent-baseline",
        "agent": runs[0].get("agent", {"adapter": "unknown", "adapter_version": 1}),
        "task": task,
        "inputs": inputs,
        "inputs_consistent_across_runs": inputs_consistent,
        "implementation": implementation,
        "implementation_consistent_across_runs": implementation_consistent,
        "model": runs[0]["environment"]["model"],
        "reasoning_effort": runs[0]["environment"]["reasoning_effort"],
        "price_version": next(
            (
                run.get("cost", {}).get("price_version")
                for run in runs
                if run.get("cost", {}).get("price_version") is not None
            ),
            None,
        ),
        "run_count": len(runs),
        "successful_runs": successes,
        "success_rate": successes / len(runs),
        "metrics": metrics,
        "runs": [sanitize_run_summary(run) for run in runs],
    }


def sanitize_run_summary(run: dict[str, Any]) -> dict[str, Any]:
    """Keep comparison data while excluding raw paths, messages, and request IDs."""
    allowed = {
        "schema_version",
        "run_id",
        "task",
        "agent",
        "environment",
        "status",
        "timing",
        "tokens",
        "cost",
        "steps",
        "stops",
        "operations",
        "iterations",
        "outputs",
        "normalized",
        "validation",
    }
    sanitized = {key: deepcopy(value) for key, value in run.items() if key in allowed}
    environment = sanitized.get("environment")
    if isinstance(environment, dict):
        environment.pop("workspace", None)
        environment.pop("source_path", None)
    outputs = sanitized.get("outputs")
    if isinstance(outputs, dict):
        outputs.pop("artifacts", None)
    validation = sanitized.get("validation")
    if isinstance(validation, dict):
        absolute_path = re.compile(
            r"/(?:Users|home|tmp|private|var|Volumes)/[^\s,'\"\]\)]+"
        )
        for key in ("errors", "warnings"):
            messages = validation.get(key)
            if isinstance(messages, list):
                validation[key] = [
                    absolute_path.sub("<external-path>", str(message))
                    for message in messages
                ]
    return sanitized


def git_value(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dependency_version(command: list[str]) -> str:
    try:
        output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=15)
        return output.splitlines()[0].strip() if output else "unknown"
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "missing"


def package_versions(names: Iterable[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "missing"
    return versions


def resolve_env_path(config: dict[str, Any]) -> Path:
    env_name = config.get("env")
    raw = os.environ.get(str(env_name), "") if env_name else ""
    if not raw:
        raw = str(config.get("default", ""))
    if not raw:
        raise ValueError(f"path is not configured; set {env_name}")
    return Path(raw).expanduser().resolve()
