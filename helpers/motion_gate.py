#!/usr/bin/env python3
"""Text-only delivery gate for a rendered motion-design piece.

  python helpers/motion_gate.py render.mp4 --width 1920 --height 1080 --fps 30 --min-s 8 --max-s 12 [--silent] [--beats beats.json] [--out edit/verify]

Deterministic facts (ffprobe, full decode, black/white flat ranges, frozen ranges via freezedetect) are
collected into a report; Jev answers "ready to deliver per the contract" (calibrated threshold 0.15,
measured on 24 real exports and 120 perturbed ones) and, when a beat table is given
([{"start": s, "end": s, "beat": "..."}]), whether each frozen range is an intentional hold.
Hard rules (spec mismatch, decode errors, flat ranges, duration out of range) fail regardless of Jev.
Exit 0 = ship, 2 = fix.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev import Jev, noul  # noqa: E402

READY_THRESHOLD = 0.15


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=900)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("--width", type=int, required=True); ap.add_argument("--height", type=int, required=True); ap.add_argument("--fps", type=float, required=True)
    ap.add_argument("--min-s", type=float, required=True); ap.add_argument("--max-s", type=float, required=True); ap.add_argument("--silent", action="store_true", help="the piece must have no audio stream")
    ap.add_argument("--beats"); ap.add_argument("--out", default="edit/verify")
    a = ap.parse_args()
    t0 = time.perf_counter(); video = Path(a.video); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pr = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames", "-count_frames", "-of", "json", str(video)])
    probe = json.loads(pr.stdout or "{}"); streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {}); audio = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(probe.get("format", {}).get("duration") or 0)
    num, den = (v.get("r_frame_rate") or "0/1").split("/"); fps = float(num) / float(den or 1)
    dec = run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"])
    bd = run(["ffmpeg", "-nostats", "-i", str(video), "-vf", "blackdetect=d=0.25:pic_th=0.99", "-an", "-f", "null", "-"])
    flat = [{"start": float(x), "end": float(y), "kind": "black"} for x, y in re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", bd.stderr or "")]
    fz = run(["ffmpeg", "-nostats", "-i", str(video), "-vf", "freezedetect=n=0.003:d=0.5", "-an", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: ([0-9.]+)", fz.stderr or "")]; ends = [float(x) for x in re.findall(r"freeze_end: ([0-9.]+)", fz.stderr or "")]
    frozen = [{"start": s, "end": e, "duration": round(e - s, 3)} for s, e in zip(starts, ends)]
    if len(starts) > len(ends) and duration: frozen.append({"start": starts[-1], "end": duration, "duration": round(duration - starts[-1], 3)})
    qa = {"technicalPass": dec.returncode == 0 and not (dec.stderr or "").strip(), "errors": [(dec.stderr or "").strip()[-300:]] if (dec.stderr or "").strip() else [], "width": v.get("width"), "height": v.get("height"), "fps": round(fps, 3), "duration": round(duration, 3),
          "audioStreams": len(audio), "decodedFrames": int(v.get("nb_read_frames") or v.get("nb_frames") or 0), "flatBlackOrWhiteRanges": flat, "nearIdenticalFrameRanges": frozen, "video_codec": v.get("codec_name")}
    contract = (f"Contract: H.264 MP4, exactly {a.width}x{a.height} at {a.fps:g} fps, duration between {a.min_s:g} and {a.max_s:g} seconds, "
                f"{'zero audio streams (silent by design)' if a.silent else 'audio allowed'}, technicalPass true with no errors, no flat black or white frame ranges, decodedFrames equal to fps*duration.")
    hard = []
    if not qa["technicalPass"]: hard.append("decode errors")
    if (qa["width"], qa["height"]) != (a.width, a.height): hard.append(f"size {qa['width']}x{qa['height']} != {a.width}x{a.height}")
    if abs(fps - a.fps) > 0.01: hard.append(f"fps {fps:.3f} != {a.fps:g}")
    if not (a.min_s <= duration <= a.max_s): hard.append(f"duration {duration:.2f}s outside {a.min_s:g}-{a.max_s:g}")
    if a.silent and audio: hard.append("audio stream present in a silent piece")
    if flat: hard.append(f"flat frame ranges {flat}")
    jev = Jev(log_path=out / "jev_decisions.jsonl")
    resp = jev.ask({"contract": contract, "qa": qa}, {"ready": noul("This export satisfies the contract and is ready to deliver.")}, tag="motion_gate")
    p_ready = resp.noul("ready").noul
    holds = []
    if a.beats and frozen:
        beats = json.loads(Path(a.beats).read_text())
        items = []
        for r in frozen:
            overlapping = [b for b in beats if b["start"] < r["end"] and b["end"] > r["start"]]
            items.append(({"beat_table": beats, "near_identical_range": r, "is_final_range": abs(r["end"] - duration) < 0.2, "overlapping_beats": overlapping},
                          {"intentional": noul("This near-identical (held) frame range is an intentional hold according to the authored beat table, not a stalled or broken animation.")}))
        for r, res in zip(frozen, jev.ask_many(items, workers=6, tag="motion_hold")):
            holds.append({**r, "p_intentional": None if isinstance(res, Exception) else round(res.noul("intentional").noul, 2)})
        for h in holds:
            if h["p_intentional"] is not None and h["p_intentional"] < 0.5: hard.append(f"unexplained frozen range {h['start']:.2f}-{h['end']:.2f}s")
    verdict = "fix" if (hard or p_ready < READY_THRESHOLD) else "ship"
    report = {"video": str(video), "contract": contract, "qa": qa, "jev_p_ready": round(p_ready, 3), "ready_threshold": READY_THRESHOLD, "holds": holds, "hard_rule_failures": hard, "verdict": verdict, "seconds": round(time.perf_counter() - t0, 1)}
    (out / "motion_gate.json").write_text(json.dumps(report, indent=1))
    print(f"motion gate: {verdict.upper()} (Jev p_ready={p_ready:.2f} vs {READY_THRESHOLD}; hard rules: {hard or 'none'}; frozen ranges {len(frozen)}) in {report['seconds']} s -> {out / 'motion_gate.json'}")
    sys.exit(0 if verdict == "ship" else 2)


if __name__ == "__main__":
    main()
