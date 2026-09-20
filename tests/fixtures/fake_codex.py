#!/usr/bin/env python3
"""Small codex-exec stand-in used only by the offline benchmark tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def emit(event: dict[str, object]) -> None:
    print(json.dumps(event), flush=True)


def main() -> None:
    if "--version" in sys.argv:
        print("fake-codex 1.0")
        return

    args_path = os.environ.get("FAKE_CODEX_ARGS_FILE")
    if args_path:
        with Path(args_path).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sys.argv[1:]) + "\n")

    counter_path = Path(os.environ["FAKE_CODEX_COUNTER_FILE"])
    count = int(counter_path.read_text() if counter_path.exists() else "0") + 1
    counter_path.write_text(str(count))
    output_index = sys.argv.index("-o") + 1
    result_path = Path(sys.argv[output_index])
    configured_statuses = os.environ.get("FAKE_CODEX_STATUSES", "needs_approval,complete").split(",")
    status = configured_statuses[min(count - 1, len(configured_statuses) - 1)]
    phase = "planning" if count == 1 else ("finalization" if status == "blocked" else "production")
    command = "rg --files" if count == 1 else "python render.py -o final.mp4"

    emit({"type": "thread.started", "thread_id": "fake-thread-id"})
    emit({"type": "turn.started"})
    emit({
        "type": "item.started",
        "item": {"id": f"command-{count}", "type": "command_execution", "command": command},
    })
    emit({
        "type": "item.completed",
        "item": {
            "id": f"command-{count}",
            "type": "command_execution",
            "command": command,
            "status": "completed",
            "exit_code": 0,
        },
    })
    emit({
        "type": "turn.completed",
        "usage": {
            "input_tokens": 100 * count,
            "cached_input_tokens": 25 * count,
            "output_tokens": 10 * count,
            "reasoning_output_tokens": 4 * count,
        },
    })
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({
        "status": status,
        "phase": phase,
        "summary": f"fake turn {count}",
        "questions": ["continue"] if status in {"needs_approval", "needs_input"} else [],
        "outputs": [],
    }))


if __name__ == "__main__":
    main()
