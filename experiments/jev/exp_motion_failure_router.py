"""Experiment M1: failure-class router for motion-design runs.

For every failed command in the observer traces (103 instances across 21 runs), ask Jev two things
from the command, exit code and output tail only:
  failure_class -> which of 8 failure kinds this is (silver label: regex over the same output)
  next_action   -> what the agent should do next (label: what the LLM actually did next)
Baseline: the LLM's think time before its next command after each failure (from trace timestamps).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from common import Jev, choice, noul, read_jsonl, stats, write_result, clip

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\[[0-9]*G|\r")

CLASSES = {
    "browser_binary_missing": "The headless browser or its download is missing or cannot launch (Chrome, chrome-headless-shell, 'browser ensure', hyperframes binary not found).",
    "missing_shared_library_or_system_package": "A native shared library or OS package is missing (error while loading shared libraries, lib*.so, pkg-config packages not found, apt packages).",
    "missing_module_or_tool": "A Node or Python module or a CLI tool is not installed (ModuleNotFoundError, MODULE_NOT_FOUND, Cannot find module, command not found).",
    "wrong_path_or_missing_file": "The command pointed at a file or directory that does not exist yet (No such file or directory, FileNotFoundError, cannot access), usually a path or ordering mistake.",
    "script_hang_or_timeout": "The command timed out, hung, or was interrupted (Waiting failed, timeout exceeded, killed, exit 130/143).",
    "layout_or_frame_qc_failure": "An automated layout or frame-safety check on the authored animation failed (LayoutQCError, elements overlap at t, mobject leaves the frame, final-state mobjects overlap, reserved caption rail).",
    "lint_error_in_authored_content": "The authored HTML/JS/composition failed lint or a content check (lint errors, media_missing_id, contrast warnings, 'Check failed').",
    "other_or_unclear": "None of the above, or the output does not show why it failed.",
}
ACTIONS = {
    "fix_environment": "Install or download something, set library/PATH variables, fetch a browser, create a venv.",
    "edit_source_or_script": "Edit the authored scene, composition, helper script or config, then continue.",
    "inspect_or_read": "Read a log, tail output, list files, or read documentation before deciding.",
    "run_check": "Run or re-run a check, lint, QC, measurement or ffprobe.",
    "render": "Start or restart a render or encode.",
}
SILVER = [
    ("browser_binary_missing", r"Failed to download chrome|Chrome cannot launch|Failed to launch the browser|browser ensure|chrome-headless-shell|hyperframes: No such file"),
    ("missing_shared_library_or_system_package", r"error while loading shared libraries|lib[a-z0-9]+\.so|libnss3|libnspr4|libcups|pkg-config|Package '[^']+', required by"),
    ("script_hang_or_timeout", r"Waiting failed|[Tt]imeout|timed out|exceeded|SIGTERM|SIGKILL"),
    ("layout_or_frame_qc_failure", r"LayoutQCError|overlap at|leaves the frame|mobjects overlap|frame-safety|reserved caption rail"),
    ("missing_module_or_tool", r"ModuleNotFoundError|MODULE_NOT_FOUND|command not found|Cannot find module|No module named"),
    ("lint_error_in_authored_content", r"'lint', '\.'|media_missing_id|Check failed|error\(s\), \d+ warning|✗ "),
    ("wrong_path_or_missing_file", r"No such file or directory|FileNotFoundError|cannot access"),
]


def silver_label(rec: dict) -> str:
    text = ANSI.sub("", rec["output_tail"] + " " + rec["output_head"])
    if rec["exit_code"] in (130, 143):
        return "script_hang_or_timeout"
    for name, pat in SILVER:
        if re.search(pat, text):
            return name
    return "other_or_unclear"


def main() -> None:
    rows = read_jsonl("motion_failed_commands.jsonl")
    jev = Jev(log_path="results/jev_decisions.jsonl")
    items = []
    for r in rows:
        state = {
            "command": clip(ANSI.sub("", r["command"]), 400),
            "exit_code": r["exit_code"],
            "output_tail": clip(ANSI.sub("", r["output_tail"]), 1100),
            "note": "This is the result of one shell command run by an agent that is building a browser-rendered motion-design video in a Linux container.",
        }
        qs = {
            "failure_class": choice("Classify why this command failed, using only the command, exit code and output shown.", CLASSES),
            "next_action": choice("What should the agent do next to make progress after this failure?", ACTIONS),
            "retry_same": noul("Running exactly the same command again, unchanged, would succeed."),
        }
        items.append((state, qs))
    results = jev.ask_many(items, workers=6, tag="M1")
    out_rows = []
    ok_class = ok_action = n_class = n_action = 0
    conf_class = defaultdict(Counter)
    conf_action = defaultdict(Counter)
    lat = []
    for r, res in zip(rows, results):
        if isinstance(res, Exception):
            out_rows.append({"run": r["run"], "event_id": r["event_id"], "error": str(res)})
            continue
        fc = res.choice("failure_class")
        na = res.choice("next_action")
        rs = res.noul("retry_same").noul
        silver = silver_label(r)
        actual = r["next_action"]
        lat.append(res.latency_ms)
        if silver != "other_or_unclear":
            n_class += 1
            ok_class += fc.choice == silver
            conf_class[silver][fc.choice] += 1
        if actual in ACTIONS:
            n_action += 1
            ok_action += na.choice == actual
            conf_action[actual][na.choice] += 1
        out_rows.append({
            "run": r["run"], "event_id": r["event_id"], "command": r["command"][:120], "exit_code": r["exit_code"],
            "silver_class": silver, "jev_class": fc.choice, "p_class": round(fc.p_choice, 2), "margin_class": round(fc.choice_margin, 2),
            "actual_next": actual, "jev_next": na.choice, "p_next": round(na.p_choice, 2), "margin_next": round(na.choice_margin, 2),
            "retry_same_p": round(rs, 2), "next_is_same_command": r["next_is_same_command"],
            "agent_seconds_before_next": r["agent_seconds_before_next"], "jev_latency_ms": round(res.latency_ms),
        })
    think = [r["agent_seconds_before_next"] for r in rows if r["agent_seconds_before_next"] is not None and 0 <= r["agent_seconds_before_next"] < 600]
    # gated accuracy: only count when Jev's top probability and margin clear a gate
    gated = [o for o in out_rows if "jev_next" in o and o["actual_next"] in ACTIONS and o["p_next"] >= 0.45 and o["margin_next"] >= 0.15]
    gated_ok = sum(o["jev_next"] == o["actual_next"] for o in gated)
    same = [o for o in out_rows if "retry_same_p" in o]
    retry_pred_when_same = [o["retry_same_p"] for o in same if o["next_is_same_command"]]
    retry_pred_when_diff = [o["retry_same_p"] for o in same if not o["next_is_same_command"]]
    summary = {
        "instances": len(rows), "jev_errors": sum(1 for o in out_rows if "error" in o),
        "failure_class_vs_silver": {"n": n_class, "agree": ok_class, "acc": round(ok_class / n_class, 3) if n_class else None},
        "next_action_vs_agent": {"n": n_action, "agree": ok_action, "acc": round(ok_action / n_action, 3) if n_action else None},
        "next_action_gated(p>=0.45,margin>=0.15)": {"n": len(gated), "agree": gated_ok, "acc": round(gated_ok / len(gated), 3) if gated else None, "coverage": round(len(gated) / max(n_action, 1), 3)},
        "retry_same_p_when_agent_retried_same": stats(retry_pred_when_same), "retry_same_p_when_agent_changed": stats(retry_pred_when_diff),
        "jev_latency_ms": stats(lat), "agent_seconds_before_next_command": stats(think),
        "confusion_class": {k: dict(v) for k, v in conf_class.items()}, "confusion_action": {k: dict(v) for k, v in conf_action.items()},
    }
    md = ["# M1 failure-class router (motion design)\n", f"Instances: {len(rows)} failed commands from 21 observer runs (gpt-6-astra low).\n"]
    md.append(f"- failure_class agreement with regex silver labels: {ok_class}/{n_class} = {summary['failure_class_vs_silver']['acc']}")
    md.append(f"- next_action agreement with what the LLM actually did next: {ok_action}/{n_action} = {summary['next_action_vs_agent']['acc']}")
    md.append(f"- next_action gated (p>=0.45, margin>=0.15): {gated_ok}/{len(gated)} = {summary['next_action_gated(p>=0.45,margin>=0.15)']['acc']} at coverage {summary['next_action_gated(p>=0.45,margin>=0.15)']['coverage']}")
    md.append(f"- retry_same probability when the agent did retry the identical command: {stats(retry_pred_when_same)}")
    md.append(f"- retry_same probability when the agent changed something: {stats(retry_pred_when_diff)}")
    md.append(f"- Jev latency ms: {stats(lat)}")
    md.append(f"- LLM think time before next command after a failure (s): {stats(think)}\n")
    md.append("## Confusion: next_action (rows = agent's actual, cols = Jev)\n")
    for k, v in conf_action.items():
        md.append(f"- {k}: {dict(v)}")
    md.append("\n## Confusion: failure_class (rows = silver, cols = Jev)\n")
    for k, v in conf_class.items():
        md.append(f"- {k}: {dict(v)}")
    write_result("M1_failure_router", summary, out_rows, "\n".join(md) + "\n")


if __name__ == "__main__":
    main()
