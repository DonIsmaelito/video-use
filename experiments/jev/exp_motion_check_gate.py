"""Experiment M2: check gate. After each `motion_slot.py check`, decide from the text output whether
to proceed to render, fix the source, fix the environment, or inspect further. Label = what the LLM did next.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from common import Jev, choice, read_jsonl, stats, write_result, clip

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\[[0-9]*G|\r")
GATE = {
    "proceed_to_render": "The check output shows no blocking problem; start or continue the render.",
    "fix_source": "The authored scene or composition has a real problem (lint error, layout overlap, missing id, contrast) that must be edited first.",
    "fix_environment": "The check itself could not run properly because of a missing browser, library, module or tool; repair the environment first.",
    "inspect_or_rerun": "The output is inconclusive or truncated; read a log, list files, or re-run the check before deciding.",
}
MAP = {"render": "proceed_to_render", "edit_source_or_script": "fix_source", "fix_environment": "fix_environment", "inspect_or_read": "inspect_or_rerun", "run_check": "inspect_or_rerun"}


def summarize(out: str) -> dict:
    t = ANSI.sub("", out)
    f = {}
    m = re.search(r"(\d+) error\(s\), (\d+) warning\(s\)", t); f["lint_errors"], f["lint_warnings"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    m = re.search(r"Runtime\s+\S*\s*(\d+) error", t); f["runtime_errors"] = int(m.group(1)) if m else None
    m = re.search(r"Layout\s+\S*\s*(\d+) issues? across (\d+) sample", t); f["layout_issues"], f["layout_samples"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    f["check_passed"] = "Check passed" in t
    f["check_failed"] = "Check failed" in t or "returned non-zero exit status" in t
    f["mentions_browser_or_library"] = bool(re.search(r"chrome|browser|shared librar|lib[a-z0-9]+\.so|MODULE_NOT_FOUND|ModuleNotFound", t, re.I))
    return f


def main() -> None:
    rows = [r for r in read_jsonl("motion_check_runs.jsonl") if r["next_action"] in MAP]
    jev = Jev(log_path="results/jev_decisions.jsonl")
    items = []
    for r in rows:
        state = {"command": clip(ANSI.sub("", r["command"]), 300), "exit_code": r["exit_code"], "parsed": summarize(r["output_tail"] + r["output_head"]), "output_tail": clip(ANSI.sub("", r["output_tail"]), 1200)}
        items.append((state, {"gate": choice("An agent just ran the motion-slot check on its browser-rendered animation. Decide what it should do next from this output.", GATE)}))
    results = jev.ask_many(items, workers=6, tag="M2")
    out_rows, conf, lat = [], defaultdict(Counter), []
    ok = n = 0
    for r, res in zip(rows, results):
        if isinstance(res, Exception):
            out_rows.append({"run": r["run"], "error": str(res)}); continue
        a = res.choice("gate"); actual = MAP[r["next_action"]]
        lat.append(res.latency_ms); n += 1; ok += a.choice == actual; conf[actual][a.choice] += 1
        out_rows.append({"run": r["run"], "event_id": r["event_id"], "exit_code": r["exit_code"], "actual": actual, "jev": a.choice, "p": round(a.p_choice, 2), "margin": round(a.choice_margin, 2), "agent_seconds_before_next": r["agent_seconds_before_next"], "jev_latency_ms": round(res.latency_ms), "parsed": summarize(r["output_tail"])})
    think = [r["agent_seconds_before_next"] for r in rows if r["agent_seconds_before_next"] is not None and 0 <= r["agent_seconds_before_next"] < 600]
    summary = {"instances": n, "agree": ok, "acc": round(ok / n, 3) if n else None, "confusion": {k: dict(v) for k, v in conf.items()}, "jev_latency_ms": stats(lat), "agent_seconds_before_next_command": stats(think)}
    md = [f"# M2 check gate (motion design)\n", f"Instances: {n} `motion_slot.py check` runs with a classifiable next action.", f"- agreement with the LLM's actual next step: {ok}/{n} = {summary['acc']}", f"- Jev latency ms: {stats(lat)}", f"- LLM think time after the check output (s): {stats(think)}", "\n## Confusion (rows = actual, cols = Jev)\n"] + [f"- {k}: {dict(v)}" for k, v in conf.items()]
    write_result("M2_check_gate", summary, out_rows, "\n".join(md) + "\n")


if __name__ == "__main__":
    main()
