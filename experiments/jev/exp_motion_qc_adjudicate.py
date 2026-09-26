"""Experiment M3: layout-QC adjudication. When `layout_qc.py` reports element overlaps, decide from the
violation text (plus any rectangles the agent printed) whether it is a real collision to fix in the source,
a bounding-box artifact to allow in the check, or an unrelated tooling error. Label = the LLM's next action.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from common import Jev, choice, read_jsonl, stats, write_result, clip

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\[[0-9]*G|\r")
VERDICT = {
    "real_collision_edit_source": "Two visible elements genuinely overlap on screen; the animation source must be changed (move, resize, retime).",
    "measurement_artifact_adjust_check": "The overlap is only between bounding boxes of shapes that do not visibly collide (rays, rings, diagonal bars, transparent padding); adjust the allow-list or measurement, not the design.",
    "tooling_error_not_a_design_verdict": "The QC did not actually evaluate the design: missing manifest, module or path error, empty measurement, traceback unrelated to overlaps.",
}


def label(r: dict) -> str | None:
    nxt = (r["next_command"] or "").lower()
    if re.search(r"allow|measure\.cjs|qc\.cjs|layout_manifest|selectors|ignore", nxt) and re.search(r"cat > |sed -i|python - <<", nxt):
        return "measurement_artifact_adjust_check"
    if r["next_action"] == "edit_source_or_script":
        return "real_collision_edit_source"
    if r["next_action"] == "fix_environment" or "FileNotFoundError" in r["output_tail"] or "No such file" in r["output_tail"]:
        return "tooling_error_not_a_design_verdict"
    return None


def main() -> None:
    rows = [r for r in read_jsonl("motion_layout_qc.jsonl") if r["exit_code"] != 0 and ("layout_qc" in r["command"] or "LayoutQCError" in r["output_tail"] or "overlap at" in r["output_tail"])]
    jev = Jev(log_path="results/jev_decisions.jsonl")
    items = []
    for r in rows:
        t = ANSI.sub("", r["output_tail"])
        viol = re.findall(r"- elements? '([^']+)' and '([^']+)' overlap at ([0-9.]+)s", t)
        state = {"violations": [{"a": a, "b": b, "t": float(s)} for a, b, s in viol][:20], "n_violations": len(viol), "traceback_tail": clip(t, 900), "command": clip(ANSI.sub("", r["command"]), 300)}
        items.append((state, {"verdict": choice("A layout QC tool reported these results for a browser-rendered or Manim animation. Element ids hint at their shapes (ray, ring, disk, arrow, label, body). Decide what the agent should do.", VERDICT)}))
    results = jev.ask_many(items, workers=6, tag="M3")
    out_rows, conf, lat = [], defaultdict(Counter), []
    ok = n = 0
    for r, res in zip(rows, results):
        if isinstance(res, Exception):
            out_rows.append({"run": r["run"], "error": str(res)}); continue
        a = res.choice("verdict"); lab = label(r); lat.append(res.latency_ms)
        if lab:
            n += 1; ok += a.choice == lab; conf[lab][a.choice] += 1
        out_rows.append({"run": r["run"], "event_id": r["event_id"], "label": lab, "jev": a.choice, "p": round(a.p_choice, 2), "margin": round(a.choice_margin, 2), "violations": re.findall(r"elements? '[^']+' and '[^']+' overlap at [0-9.]+s", ANSI.sub("", r["output_tail"]))[:6], "next_command": (r["next_command"] or "")[:100], "agent_seconds_before_next": r["agent_seconds_before_next"], "jev_latency_ms": round(res.latency_ms)})
    think = [r["agent_seconds_before_next"] for r in rows if r["agent_seconds_before_next"] is not None and 0 <= r["agent_seconds_before_next"] < 600]
    summary = {"instances": len(rows), "labelled": n, "agree": ok, "acc": round(ok / n, 3) if n else None, "confusion": {k: dict(v) for k, v in conf.items()}, "jev_latency_ms": stats(lat), "agent_seconds_before_next_command": stats(think)}
    md = ["# M3 layout-QC adjudication (motion design)\n", f"Instances: {len(rows)} failing layout-QC commands, {n} with a label derived from the LLM's next action.", f"- agreement: {ok}/{n} = {summary['acc']}", f"- Jev latency ms: {stats(lat)}", f"- LLM think time after the QC failure (s): {stats(think)}", "\n## Confusion (rows = label, cols = Jev)\n"] + [f"- {k}: {dict(v)}" for k, v in conf.items()] + ["\n## Rows\n"] + [f"- {o.get('run')} label={o.get('label')} jev={o.get('jev')} p={o.get('p')} viol={o.get('violations')[:2] if o.get('violations') else None} next={o.get('next_command')!r}" for o in out_rows]
    write_result("M3_qc_adjudicate", summary, out_rows, "\n".join(md) + "\n")


if __name__ == "__main__":
    main()
