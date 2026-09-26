"""Experiment S1: moment selection over a whole long interview with Jev, no LLM.

Pipeline: Scribe JSON -> phrases -> answer-units (speech_units.py) -> three Jev questions per unit
(standalone, hook, payoff) asked in one request -> ranked shortlist. Evaluation: do the top-K units
overlap the windows the LLM agents picked in the 2026-08-30 benchmark runs and the 2026-09-02 harness
round (six distinct moments)? The benchmark footage was a different upload of the same interview, so the
time offset between the two transcripts is measured from anchor phrases first.

Baseline (from the Codex rollouts, model time attributed to transcript reading + candidate selection,
plus the filmstrip inspection of candidates): T1 3.1 + 1.6 min, T2 1.3 + 1.5 min, T3 0.2 + 2.2 min,
T4 1.5 + 2.6 min, T5 0.5 + 1.4 min; coverage was keyword grep plus 5-12 percent of the packed file.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from common import Jev, choice, noul, stats, write_result
from speech_units import build_units, guest_speaker, load_phrases, next_host_phrase

# LLM-picked windows in the ORIGINAL transcript's time base (seconds), from experiments/jev/data/jensen_llm_edls.json
TARGETS = {
    "electrons_to_tokens": (30.37, 100.2), "clip_238": (238.08, 259.22), "plumbers_radiologists": (780.58, 834.25),
    "cpu_cadillac_vs_gpu_f1": (1833.82, 1897.6), "ai_job_vs_task": (5312.31, 5388.88), "nvidia_without_ai": (5988.36, 6040.47),
}
# anchor phrases with their original-time-base positions (from the traces)
ANCHORS = [("valuations of a bunch of software companies", 0.60), ("something has to transform electrons to tokens", 32.14), ("I went to the hardest one, by the way", 782.85)]
HOOK = {"0": "generic setup, context or a question; nothing quotable", "1": "an ordinary point, mildly interesting", "2": "a clear, interesting claim or story beat in the first line", "3": "surprising, funny, provocative or quotable from the first sentence"}


def find_offset(phrases: list[dict]) -> tuple[float | None, list]:
    found = []
    for needle, old_t in ANCHORS:
        for p in phrases:
            if needle.lower() in p["text"].lower():
                found.append((needle, old_t, p["start"], round(p["start"] - old_t, 1)))
                break
    if not found:
        return None, found
    offs = [f[3] for f in found]
    return statistics.median(offs), found



def tournament(jev, ranked: list[dict], k: int = 8) -> tuple[list[dict], float]:
    """Stage 2: pairwise 'which is the more postable moment' over the top-k, round robin, margin-gated."""
    import itertools, time as _t
    top = ranked[:k]
    pairs = list(itertools.combinations(range(len(top)), 2))
    items = []
    for i, j in pairs:
        A, B = top[i], top[j]
        state = {"A": {"question": A["question"], "answer_start": A["text"][:220], "duration_s": A["duration_s"]}, "B": {"question": B["question"], "answer_start": B["text"][:220], "duration_s": B["duration_s"]}}
        items.append((state, {"stronger": choice("Which answer makes the more postable standalone TikTok clip: a clearer hook, a self-contained idea and a payoff?", {"A": "A is the stronger clip", "B": "B is the stronger clip"})}))
    t0 = _t.perf_counter(); res = jev.ask_many(items, workers=8, tag="S1-tournament"); wall = _t.perf_counter() - t0
    wins = [0.0] * len(top); decided = 0
    for (i, j), r in zip(pairs, res):
        if isinstance(r, Exception): continue
        a = r.choice("stronger")
        if a.choice_margin >= 0.2:
            decided += 1
            wins[i if a.choice == "A" else j] += 1
        else:  # low margin: split
            wins[i] += 0.5; wins[j] += 0.5
    order = sorted(range(len(top)), key=lambda i: -wins[i])
    out = [dict(top[i], tournament_wins=wins[i], tournament_rank=n + 1) for n, i in enumerate(order)]
    print(f"tournament: {len(pairs)} pairs, {decided} decided at margin>=0.2, {wall:.1f} s")
    return out, wall

def main() -> None:
    transcript = Path(sys.argv[1])
    phrases = load_phrases(transcript)
    guest = guest_speaker(phrases)
    units = [u for u in build_units(phrases, guest) if u['duration_s'] >= 8 and u['n_words'] >= 15]  # only clip-sized answers
    offset, anchors = find_offset(phrases)
    print(f"{len(phrases)} phrases, guest {guest}, {len(units)} units; offset {offset} from anchors {anchors}")
    jev = Jev(log_path="results/jev_decisions.jsonl")
    items = []
    for u in units:
        state = {
            "context": "A long-form podcast interview. We are choosing which answer to cut into a standalone short vertical social clip (20-90 s) for TikTok.",
            "question_from_host": u["question"], "answer_first_400_chars": u["text"][:400], "answer_last_200_chars": u["text"][-200:],
            "next_host_phrase": next_host_phrase(phrases, u, guest), "duration_s": u["duration_s"], "words_per_second": u["wps"],
            "continues_previous_answer": u["continues_previous"], "laugh_tokens": u["laughs"],
        }
        qs = {
            "standalone": noul("A viewer who has heard nothing before this answer would understand it and find it complete on its own."),
            "hook": choice("Rate how strong the opening of this answer is as the first line of a social clip.", HOOK),
            "payoff": noul("The answer ends on a complete thought, punchline or memorable claim rather than trailing off mid-argument."),
        }
        items.append((state, qs))
    t0 = time.perf_counter()
    results = jev.ask_many(items, workers=8, tag="S1")
    wall = time.perf_counter() - t0
    rows, lat = [], []
    for u, res in zip(units, results):
        if isinstance(res, Exception):
            rows.append({"id": u["id"], "error": str(res)}); continue
        s = res.noul("standalone").noul; pay = res.noul("payoff").noul; h = res.choice("hook")
        hook_val = sum(int(k) * v for k, v in h.probabilities.items()) / 3.0  # expected level, 0..1
        lat.append(res.latency_ms)
        rows.append({"id": u["id"], "start": u["start"], "end": u["end"], "duration_s": u["duration_s"], "standalone": round(s, 2), "hook": round(hook_val, 2), "hook_choice": h.choice, "payoff": round(pay, 2), "score": round((s + hook_val + pay) / 3, 3), "question": (u["question"] or "")[:80], "text": u["text"][:140], "in_tokens": res.input_tokens, "out_tokens": res.output_tokens})
    ranked = sorted([r for r in rows if "score" in r], key=lambda r: -r["score"])
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    # evaluation against the LLM picks
    evals = {}
    if offset is not None:
        for name, (a, b) in TARGETS.items():
            a2, b2 = a + offset, b + offset
            hits = [r for r in ranked if r["start"] < b2 and r["end"] > a2]
            evals[name] = {"window_new_time": [round(a2, 1), round(b2, 1)], "best_rank": min((r["rank"] for r in hits), default=None), "n_overlapping_units": len(hits), "top_hit": ({k: hits[0][k] for k in ("id", "start", "end", "score", "text")} if hits else None)}
    ranks = [e["best_rank"] for e in evals.values() if e["best_rank"]]
    final, t_wall = tournament(jev, ranked, k=10)
    for f in final:
        for r in ranked:
            if r["id"] == f["id"]: r["tournament_rank"] = f["tournament_rank"]; r["tournament_wins"] = f["tournament_wins"]
    t_ranks = {}
    if offset is not None:
        for name, (a, b) in TARGETS.items():
            a2, b2 = a + offset, b + offset
            t_ranks[name] = min((f["tournament_rank"] for f in final if f["start"] < b2 and f["end"] > a2), default=None)
    summary = {
        "transcript": str(transcript), "phrases": len(phrases), "units": len(units), "guest": guest, "offset_s": offset, "anchors": anchors,
        "jev_calls": len(items), "wall_s": round(wall, 1), "jev_latency_ms": stats(lat), "input_tokens_total": sum(r.get("in_tokens") or 0 for r in rows),
        "recall_at_10": (sum(1 for r in ranks if r <= 10) / len(TARGETS)) if evals else None, "recall_at_20": (sum(1 for r in ranks if r <= 20) / len(TARGETS)) if evals else None,
        "target_ranks": {k: v["best_rank"] for k, v in evals.items()}, "tournament_ranks_of_targets": t_ranks, "tournament_wall_s": round(t_wall, 1), "baseline_llm_minutes_select_plus_drill": {"T1": 4.7, "T2": 2.8, "T3": 2.4, "T4": 4.1, "T5": 1.9},
    }
    md = ["# S1 moment selection with Jev over the whole interview\n", f"Transcript: {transcript.name}; {len(phrases)} phrases, {len(units)} answer-units, guest speaker {guest}.",
          f"- Jev calls: {len(items)} (three questions each) in {wall:.1f} s wall with 8 workers; latency ms {stats(lat)}",
          f"- Time-base offset vs the benchmark transcript: {offset} s from anchors {anchors}",
          f"- Recall of the six LLM-picked moments in Jev's top 10: {summary['recall_at_10']}, top 20: {summary['recall_at_20']}; ranks {summary['target_ranks']}",
          f"- LLM baseline for the same step (transcript reading + selection + filmstrip drill, model minutes per run): {summary['baseline_llm_minutes_select_plus_drill']}",
          f"- Stage 2 pairwise tournament over the top 10 ({t_wall:.1f} s): final order {[f['id'] for f in final]}; target ranks after tournament {t_ranks}",
          "\n## Top 15 units by (standalone + hook + payoff)/3\n"]
    for r in ranked[:15]:
        md.append(f"- #{r['rank']} {r['id']} [{r['start']:.1f}-{r['end']:.1f}] {r['duration_s']}s score={r['score']} (s={r['standalone']} h={r['hook']} p={r['payoff']}) Q: {r['question'][:50]!r} | {r['text'][:110]!r}")
    md.append("\n## LLM-picked windows\n")
    for k, v in evals.items():
        md.append(f"- {k}: window {v['window_new_time']} best Jev rank {v['best_rank']} ({v['n_overlapping_units']} units overlap); top hit {v['top_hit']}")
    write_result("S1_speech_select", summary, rows, "\n".join(md) + "\n")
    json.dump({"units": units, "ranked": ranked, "offset": offset}, open("results/S1_units.json", "w"), indent=1)


if __name__ == "__main__":
    main()
