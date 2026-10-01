"""Export an owner-only, read-only timeline of persisted pilot tasks.

This is execution telemetry, not a transcript of the host assistant. Tool calls
are recorded after the preview-card deployment; host token usage is unavailable.
"""

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

from .config import Config
from .store import Store


def collect(store, project_id=None, include_logs=False):
    projects = store.sql(
        "SELECT id,title,created FROM public.vp_projects "
        "WHERE ($1::uuid IS NULL OR id=$1::uuid) ORDER BY created",
        project_id,
    )
    if project_id and not projects:
        raise ValueError("Project not found")
    traces = [
        json.loads(store.vault.decrypt(r["value"].encode()))
        for r in store.sql(
            "SELECT value FROM public.vp_kv WHERE kind='trace' AND expires>extract(epoch from now()) ORDER BY expires DESC LIMIT 10000"
        )
    ]
    for project in projects:
        project["creative"] = store.get("creative", project["id"]) or {}
        project["continuation"] = store.get("progress", project["id"]) or {}
        project["production_timing"] = store.get("production_timing", project["id"])
        project["review_findings"] = store.get("review_findings", project["id"]) or []
        project["feedback"] = store.get("feedback", project["id"]) or {"items": []}
        project["tool_calls"] = sorted(
            [t for t in traces if t.get("project") == project["id"]],
            key=lambda t: t["at"],
        )
        project["tool_counts"] = dict(Counter(t["tool"] for t in project["tool_calls"]))
        tasks = store.sql(
            "SELECT id,operation,status,created,updated,error,result "
            "FROM public.vp_tasks WHERE project=$1 ORDER BY created,id",
            project["id"],
        )
        for task in tasks:
            result = task.get("result") or {}
            task["elapsed_seconds"] = (
                round(
                    (
                        datetime.fromisoformat(task["updated"])
                        - datetime.fromisoformat(task["created"])
                    ).total_seconds(),
                    2,
                )
                if task["status"] in ("succeeded", "failed", "cancelled")
                else None
            )
            task["command_exit_code"] = result.get("exit_code")
            task["output"] = {
                k: result[k]
                for k in (
                    "saved",
                    "video_path",
                    "width",
                    "height",
                    "duration",
                    "revision_id",
                    "video_id",
                    "source_id",
                    "review_object",
                    "creative_revision",
                    "preferences_changed",
                    "production_timing",
                    "audio_evidence",
                )
                if k in result
            }
            if include_logs:
                task["events"] = store.sql(
                    "SELECT created,message FROM public.vp_events "
                    "WHERE task=$1 ORDER BY id",
                    task["id"],
                )
            else:
                del task["result"]
        project["tasks"] = tasks
        project["task_counts"] = dict(Counter(t["status"] for t in tasks))
        project["operation_counts"] = dict(Counter(t["operation"] for t in tasks))
    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "projects": projects,
        "includes_logs": include_logs,
        "unassigned_tool_calls": [t for t in traces if not t.get("project")]
        if not project_id
        else [],
        "limitations": [
            "Tool metadata begins with the preview-card deployment and expires after 30 days. Discovery and host chat turns are not captured. Up to 10000 recent tool calls are included; calls without a project ID are listed separately.",
            "Elapsed time includes queueing, workspace setup and checkpoints, not just rendering.",
            "A succeeded run task can contain a nonzero command exit code; inspect both fields.",
            "Claude/ChatGPT turns, token usage, remaining subscription allowance and reasoning are not available here.",
            "Logs can contain user content. Keep this local owner report private.",
        ],
    }
    # Defense in depth if a provider exception or command echoed a configured key.
    serialized = json.dumps(report)
    for secret in (
        store.config.api_key,
        store.config.speech_key,
        store.config.encryption_key,
        store.config.invite_code,
    ):
        if secret:
            serialized = serialized.replace(json.dumps(secret)[1:-1], "[redacted]")
    return json.loads(serialized)


def write_report(report, output):
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = [
        "# Video use execution trace",
        "",
        "Observed: " + report["observed_at"],
        "",
    ]
    for project in report["projects"]:
        title = project["title"].replace("\n", " ").replace("|", "/")
        lines += [
            f"## {title}",
            "",
            f"Project: `{project['id']}`",
            "",
            "| Started UTC | Operation | Status | Elapsed seconds | Command exit | Detail |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
        for task in project["tasks"]:
            detail = task["error"] or json.dumps(task["output"], ensure_ascii=False)
            detail = detail.replace("|", "/").replace("\n", " ")
            seconds = task["elapsed_seconds"]
            exit_code = task["command_exit_code"]
            lines.append(
                f"| {task['created']} | {task['operation']} | {task['status']} "
                f"| {seconds if seconds is not None else 'in progress'} "
                f"| {exit_code if exit_code is not None else ''} | {detail} |"
            )
        lines += [
            "",
            "Tool calls: " + json.dumps(project.get("tool_counts", {})),
            "",
            "Creative context: "
            + json.dumps(project.get("creative", {}), ensure_ascii=False),
            "",
            "Saved next action: "
            + project.get("continuation", {}).get("next_action", "Not recorded"),
            "",
        ]
    lines += ["## Coverage", "", *("- " + x for x in report["limitations"]), ""]
    for name, content in (
        ("latest.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
        ("latest.md", "\n".join(lines)),
    ):
        pending = output / (name + ".tmp")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(content)
        pending.replace(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env.pilot-production")
    parser.add_argument("--project", type=UUID)
    parser.add_argument("--include-logs", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".pilot-traces"))
    parser.add_argument("--watch-seconds", type=int, default=0)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    load_dotenv(args.env, interpolate=False)
    store = Store(Config.env())
    try:
        deadline = time.monotonic() + max(0, args.watch_seconds)
        while True:
            report = collect(
                store, str(args.project) if args.project else None, args.include_logs
            )
            write_report(report, args.output)
            if args.watch_seconds:
                history = args.output / "history.jsonl"
                with history.open("a") as stream:
                    os.chmod(history, 0o600)
                    stream.write(json.dumps(report) + "\n")
            print("Execution trace saved to", args.output, flush=True)
            if time.monotonic() >= deadline:
                break
            time.sleep(
                min(max(5, args.interval), 60, max(0, deadline - time.monotonic()))
            )
    except Exception as exc:
        # Provider exceptions can embed credentials; print only the class.
        print("Trace export failed:", type(exc).__name__)
        raise SystemExit(1) from None
    finally:
        store.http.close()


if __name__ == "__main__":
    main()
