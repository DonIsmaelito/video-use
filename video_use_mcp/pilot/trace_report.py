"""Export an owner-only, read-only timeline of persisted pilot tasks.

This is execution telemetry, not a transcript of the host assistant. Tool polling,
chat turns, host token usage and internal reasoning are not recorded by the pilot.
"""

import argparse
import json
import os
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
    for project in projects:
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
        "limitations": [
            "Task counts are not total MCP tool calls. Reads, polling and host tool discovery are absent.",
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
        lines += [""]
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
    args = parser.parse_args()
    load_dotenv(args.env, interpolate=False)
    store = Store(Config.env())
    try:
        report = collect(
            store, str(args.project) if args.project else None, args.include_logs
        )
        write_report(report, args.output)
        print("Execution trace saved to", args.output)
    except Exception as exc:
        # Provider exceptions can embed credentials; print only the class.
        print("Trace export failed:", type(exc).__name__)
        raise SystemExit(1) from None
    finally:
        store.http.close()


if __name__ == "__main__":
    main()
