"""Experiment S2: inside a chosen answer-unit, decide the internal cuts with Jev.

For every internal silence >= 0.4 s ask gap.safe_cut; for every phrase ask phrase.disposable; for the unit's
end ask edge.keep_reaction when a laugh or short host reaction follows. Compare with the cut lists the LLM
wrote for the same passages (T1: eleven ranges in the "job vs task" answer; T4: ten ranges in the
"plumbers" answer), after shifting by the measured transcript offset.

Baseline: T1 spent 2.6 model-minutes writing its EDL and scripts; T4 1.4; the boundary verification
that caught edge leaks in T3/T5 came after a render (1-3 minutes each).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from common import Jev, noul, stats, write_result
from speech_units import guest_speaker, load_phrases

LLM = json.load(open(Path(__file__).resolve().parent / "data" / "jensen_llm_edls.json"))
PASSAGES = {"T1_job_vs_task": LLM["T1"][0][1], "T4_plumbers": LLM["T4"][0][1]}


def removed_regions(ranges: list) -> list[tuple[float, float]]:
    rs = sorted(ranges)
    return [(rs[i - 1][1], rs[i][0]) for i in range(1, len(rs))]


def main() -> None:
    transcript = Path(sys.argv[1]); offset = float(sys.argv[2])
    phrases = load_phrases(transcript); guest = guest_speaker(phrases)
    jev = Jev(log_path="results/jev_decisions.jsonl")
    all_rows, md = [], ["# S2 internal cuts with Jev vs the LLM's EDL ranges\n"]
    summary = {}
    for name, ranges in PASSAGES.items():
        a, b = min(r[0] for r in ranges) + offset, max(r[1] for r in ranges) + offset
        window = [p for p in phrases if p["end"] > a - 1 and p["start"] < b + 1]
        llm_removed = [(x + offset, y + offset) for x, y in removed_regions(ranges)]
        items, meta = [], []
        for i, p in enumerate(window):
            prev = window[i - 1] if i else None; nxt = window[i + 1] if i + 1 < len(window) else None
            state = {"phrase": p["text"], "previous": prev["text"] if prev else None, "next": nxt["text"] if nxt else None, "speaker_is_guest": p.get("speaker_id") == guest, "duration_s": round(p["end"] - p["start"], 2)}
            items.append((state, {"disposable": noul("This phrase is a false start, filler-only, a verbatim repetition, or a host interjection that can be removed from the clip without losing meaning.")})); meta.append(("phrase", p["start"], p["end"], p["text"]))
            if prev and p["start"] - prev["end"] >= 0.4:
                gap = round(p["start"] - prev["end"], 2)
                state = {"gap_seconds": gap, "words_before": " ".join(prev["text"].split()[-8:]), "words_after": " ".join(p["text"].split()[:8]), "same_speaker": prev.get("speaker_id") == p.get("speaker_id")}
                items.append((state, {"safe_cut": noul("Removing this silence entirely (butting the words before and after together, with a 30 ms audio fade) would sound like a natural sentence and lose nothing.")})); meta.append(("gap", prev["end"], p["start"], f"{gap}s"))
        t0 = time.perf_counter(); results = jev.ask_many(items, workers=8, tag="S2"); wall = time.perf_counter() - t0
        rows = []
        for (kind, s, e, txt), res in zip(meta, results):
            if isinstance(res, Exception): rows.append({"kind": kind, "start": s, "end": e, "error": str(res)}); continue
            key = "disposable" if kind == "phrase" else "safe_cut"; p = res.answers[key].noul
            llm_cut = any(s < y and e > x for x, y in llm_removed)  # overlaps a region the LLM removed
            rows.append({"passage": name, "kind": kind, "start": round(s, 2), "end": round(e, 2), "text": txt[:80], "p": round(p, 2), "jev_cut": p >= 0.6, "llm_cut": llm_cut, "latency_ms": round(res.latency_ms)})
        gaps = [r for r in rows if r["kind"] == "gap" and "p" in r]; phs = [r for r in rows if r["kind"] == "phrase" and "p" in r]
        def prf(rs):
            tp = sum(r["jev_cut"] and r["llm_cut"] for r in rs); fp = sum(r["jev_cut"] and not r["llm_cut"] for r in rs); fn = sum((not r["jev_cut"]) and r["llm_cut"] for r in rs)
            return {"n": len(rs), "tp": tp, "fp": fp, "fn": fn, "precision": round(tp / max(tp + fp, 1), 2), "recall": round(tp / max(tp + fn, 1), 2)}
        summary[name] = {"window_new_time": [round(a, 1), round(b, 1)], "llm_ranges": len(ranges), "llm_removed_regions": len(llm_removed), "gaps": prf(gaps), "phrases": prf(phs), "jev_calls": len(items), "wall_s": round(wall, 1), "latency_ms": stats([r["latency_ms"] for r in rows if "latency_ms" in r])}
        md.append(f"## {name}: window {summary[name]['window_new_time']}, LLM wrote {len(ranges)} ranges ({len(llm_removed)} removed regions)")
        md.append(f"- gaps >= 0.4 s: {summary[name]['gaps']}\n- phrases: {summary[name]['phrases']}\n- {len(items)} Jev calls in {wall:.1f} s; latency {summary[name]['latency_ms']}\n")
        for r in sorted(rows, key=lambda r: r["start"]):
            if "p" in r: md.append(f"  - {r['kind']:6s} [{r['start']:.2f}-{r['end']:.2f}] p={r['p']} jev_cut={r['jev_cut']} llm_cut={r['llm_cut']} {r['text']!r}")
        all_rows += rows
    write_result("S2_speech_cuts", summary, all_rows, "\n".join(md) + "\n")


if __name__ == "__main__":
    main()
