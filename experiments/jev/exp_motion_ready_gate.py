"""Experiment M4: delivery-readiness gate and intentional-hold check on the 24 collection scenes.

Readiness: the real qa.json of each scene (all delivered, label ready) plus five perturbed copies each
(technical failure, audio present, flat black range, wrong fps, duration out of range) that violate the
collection contract (label not ready). Jev sees only the JSON fields and the contract text.
Intentional hold: every nearIdenticalFrameRanges entry of the 8 scenes with a beat table; label = the
range overlaps a beat described as a hold/settle/rest or is the final range and the review calls it deliberate.
"""
from __future__ import annotations

import copy
import random
from collections import Counter

from common import Jev, noul, read_jsonl, stats, write_result

CONTRACT = ("Collection contract: H.264 MP4, exactly 1920x1080 at 30 fps, duration between 8 and 12 seconds, "
            "zero audio streams (silent by design), technicalPass true with no errors, faststart true, no flat black or white "
            "frame ranges, decodedFrames equal to fps*duration.")


def qa_state(qa: dict) -> dict:
    m = qa.get("metrics") or {}
    return {"technicalPass": qa.get("technicalPass"), "errors": qa.get("errors"), "faststart": qa.get("faststart"), "width": qa.get("width"), "height": qa.get("height"), "fps": qa.get("fps"), "duration": qa.get("duration"), "audioStreams": qa.get("audioStreams"), "decodedFrames": m.get("decodedFrames"), "flatBlackOrWhiteRanges": m.get("flatBlackOrWhiteRanges"), "nearIdenticalFrameRanges": m.get("nearIdenticalFrameRanges"), "largeFrameChanges_count": len(m.get("largeFrameChanges") or []), "meanFrameChange": m.get("meanFrameChange")}


def perturb(qa: dict, kind: str) -> dict:
    q = copy.deepcopy(qa); m = q.setdefault("metrics", {})
    if kind == "technical_failure": q["technicalPass"] = False; q["errors"] = ["decode error: corrupt frame at 4.2s"]
    elif kind == "audio_present": q["audioStreams"] = 1
    elif kind == "flat_black": m["flatBlackOrWhiteRanges"] = [{"start": 0.0, "end": 0.8, "kind": "black"}]
    elif kind == "wrong_fps": q["fps"] = 25.0; m["decodedFrames"] = int(round(25 * q["duration"]))
    elif kind == "duration_out_of_range": q["duration"] = 14.5; m["decodedFrames"] = int(round(q["fps"] * 14.5))
    return q


def main() -> None:
    scenes = read_jsonl("collection_scenes.jsonl")
    jev = Jev(log_path="results/jev_decisions.jsonl")
    random.seed(7)
    items, meta = [], []
    for s in scenes:
        if not s["qa"]: continue
        items.append(({"contract": CONTRACT, "qa": qa_state(s["qa"])}, {"ready": noul("This export satisfies the collection contract and is ready to deliver.")})); meta.append((s["id"], "original", True))
        for kind in ("technical_failure", "audio_present", "flat_black", "wrong_fps", "duration_out_of_range"):
            items.append(({"contract": CONTRACT, "qa": qa_state(perturb(s["qa"], kind))}, {"ready": noul("This export satisfies the collection contract and is ready to deliver.")})); meta.append((s["id"], kind, False))
    results = jev.ask_many(items, workers=6, tag="M4-ready")
    rows, lat = [], []
    by_kind = Counter(); n_kind = Counter()
    for (sid, kind, lab), res in zip(meta, results):
        if isinstance(res, Exception): rows.append({"scene": sid, "kind": kind, "error": str(res)}); continue
        p = res.noul("ready").noul; lat.append(res.latency_ms); pred = p >= 0.5
        n_kind[kind] += 1; by_kind[kind] += pred == lab
        rows.append({"scene": sid, "kind": kind, "label_ready": lab, "p_ready": round(p, 2), "correct": pred == lab})
    acc = {k: f"{by_kind[k]}/{n_kind[k]}" for k in n_kind}
    # intentional hold
    hold_items, hold_meta = [], []
    for s in scenes:
        if not s["beats"] or not s["qa"]: continue
        for rng in (s["qa"].get("metrics") or {}).get("nearIdenticalFrameRanges") or []:
            a, b = rng["start"], rng["end"]
            overlapping = [(t0, t1, lbl) for t0, t1, lbl in s["beats"] if t0 < b and t1 > a]
            is_final = abs(b - s["duration"]) < 0.2
            lab = any(any(w in lbl.lower() for w in ("hold", "settle", "rest", "payoff", "still", "pause")) for _, _, lbl in overlapping) or (is_final and ("deliberate" in s["review"].lower() or "intentional" in s["review"].lower()))
            hold_items.append(({"scene": s["title"], "duration_s": s["duration"], "beat_table": [{"start": t0, "end": t1, "beat": lbl} for t0, t1, lbl in s["beats"]], "near_identical_range": {"start": a, "end": b, "duration": rng.get("duration")}, "is_final_range": is_final}, {"intentional": noul("This near-identical (held) frame range is an intentional hold according to the authored beat table, not a stalled or broken animation.")}))
            hold_meta.append((s["id"], a, b, lab))
    hres = jev.ask_many(hold_items, workers=6, tag="M4-hold")
    hrows = []; hok = hn = 0
    for (sid, a, b, lab), res in zip(hold_meta, hres):
        if isinstance(res, Exception): hrows.append({"scene": sid, "error": str(res)}); continue
        p = res.noul("intentional").noul; lat.append(res.latency_ms); hn += 1; hok += (p >= 0.5) == lab
        hrows.append({"scene": sid, "range": [a, b], "label_intentional": lab, "p_intentional": round(p, 2), "correct": (p >= 0.5) == lab})
    summary = {"readiness": {"n": sum(n_kind.values()), "acc_by_kind": acc, "overall": round(sum(by_kind.values()) / max(sum(n_kind.values()), 1), 3)}, "intentional_hold": {"n": hn, "agree": hok, "acc": round(hok / hn, 3) if hn else None}, "jev_latency_ms": stats(lat)}
    md = ["# M4 delivery readiness + intentional hold (collection scenes)\n", f"Readiness: {sum(n_kind.values())} instances (24 real exports + 5 perturbations each). Accuracy by kind: {acc}; overall {summary['readiness']['overall']}", f"Intentional hold: {hok}/{hn} = {summary['intentional_hold']['acc']} on {hn} near-identical ranges from the 8 scenes with beat tables", f"Jev latency ms: {stats(lat)}", "\n## Hold rows\n"] + [f"- {h}" for h in hrows]
    write_result("M4_ready_gate", summary, rows + hrows, "\n".join(md) + "\n")


if __name__ == "__main__":
    main()
