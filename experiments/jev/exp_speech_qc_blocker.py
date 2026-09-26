"""Experiment S3: one gate over a text QC report after render. Given ffprobe facts, loudness, decode
stderr, SRT stats, edge-overlap checks and any tracebacks, does the report contain a defect that must be
fixed before delivery (as opposed to a tooling artifact or a pass)?

Instances are reconstructed from the Jensen benchmark traces (T1 caption drift, T3 sampler traceback at the
exact duration, T3 20 ms word leak, T5 "indus-" fragment and "Oh" interjection, T2 missing subtitles filter,
clean passes) plus a few controlled variants. Label = what the agent did (fixed vs shipped).
Baseline: the agents spent 11-17 verification calls per run (20-33 percent of calls), most of them frame views.
"""
from __future__ import annotations

from common import Jev, choice, noul, stats, write_result

BASE = {"ffprobe": {"width": 1080, "height": 1920, "video_codec": "h264", "pix_fmt": "yuv420p", "fps": "30000/1001", "audio_codec": "aac", "sample_rate": 48000, "channels": 2, "duration_s": 62.894},
        "task_validation": {"min_duration_s": 20, "max_duration_s": 90, "aspect": "9:16", "video_codec": "h264", "audio_codec": "aac", "audible_threshold_db": -50, "caption_sidecar_required": True},
        "loudness": {"integrated_lufs": -14.0, "true_peak_dbtp": -0.9}, "decode_stderr": "", "blackdetect": [],
        "srt": {"cues": 106, "first_start_s": 0.05, "last_end_s": 62.715, "monotonic": True, "max_cue_chars": 24},
        "edge_checks": {"cut_inside_word": [], "other_speaker_token_inside_padded_edge": [], "caption_drift_ms_at_last_cut": 4},
        "tracebacks": []}


def variant(**kw):
    import copy
    s = copy.deepcopy(BASE)
    for k, v in kw.items():
        d = s
        parts = k.split(".")
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = v
    return s


INSTANCES = [
    ("T1 clean final", variant(), False),
    ("T1 124 ms caption drift", variant(**{"edge_checks.caption_drift_ms_at_last_cut": 124}), True),
    ("T3 sampler traceback at exact duration", variant(tracebacks=["timeline_view.py: ValueError: requested frame at 68.200s is at or beyond the file duration 68.200s (frame sampler)"]), False),
    ("T3 20 ms host word inside padded start", variant(**{"edge_checks.other_speaker_token_inside_padded_edge": [{"edge": "start", "token": "that", "speaker": "host", "overlap_ms": 20}]}), True),
    ("T5 host fragment at clip start", variant(**{"edge_checks.other_speaker_token_inside_padded_edge": [{"edge": "start", "token": "indus-", "speaker": "host", "overlap_ms": 180}]}), True),
    ("T5 host 'Oh' inside end padding", variant(**{"edge_checks.other_speaker_token_inside_padded_edge": [{"edge": "end", "token": "Oh", "speaker": "host", "overlap_ms": 60}]}), True),
    ("T4 cut inside a word", variant(**{"edge_checks.cut_inside_word": [{"time_s": 790.72, "word": "scaling", "edge": "start"}]}), True),
    ("silent audio", variant(**{"loudness.integrated_lufs": -70.0, "loudness.true_peak_dbtp": -60.0}), True),
    ("loud but within spec", variant(**{"loudness.integrated_lufs": -12.5, "loudness.true_peak_dbtp": -1.2}), False),
    ("decode error", variant(decode_stderr="[h264 @ 0x7f] error while decoding MB 45 12, bytestream -7\nError while decoding stream #0:0: Invalid data found when processing input"), True),
    ("landscape output", variant(**{"ffprobe.width": 1920, "ffprobe.height": 1080}), True),
    ("too long", variant(**{"ffprobe.duration_s": 96.4, "srt.last_end_s": 96.1}), True),
    ("SRT not monotonic", variant(**{"srt.monotonic": False}), True),
    ("black frames at start", variant(blackdetect=[{"start": 0.0, "end": 0.7}]), True),
    ("harmless ffmpeg deprecation warning", variant(decode_stderr="[aac @ 0x7f] Estimating duration from bitrate, this may be inaccurate"), False),
    ("T2 subtitles filter missing (before render)", variant(tracebacks=["ffmpeg: Unknown filter 'subtitles' (No such filter)"], srt={"cues": 0, "first_start_s": None, "last_end_s": None, "monotonic": None, "max_cue_chars": None}), True),
]


def main() -> None:
    jev = Jev(log_path="results/jev_decisions.jsonl")
    items = [({"qc_report": s, "context": "Post-render QC report for a vertical TikTok clip cut from a long interview with burned captions and an SRT sidecar."},
              {"blocker": noul("The report contains a real defect that must be fixed before delivery; tooling artifacts, harmless warnings and in-spec values are not defects."),
               "action": choice("What should happen next?", {"ship": "Deliver as is.", "fix_and_rerender": "Fix the EDL, captions or audio and render again.", "fix_tooling_only": "The media is fine; only the check or the environment needs attention."})})
             for _, s, _ in INSTANCES]
    results = jev.ask_many(items, workers=8, tag="S3")
    rows, lat = [], []
    ok = 0
    for (name, _, lab), res in zip(INSTANCES, results):
        if isinstance(res, Exception): rows.append({"name": name, "error": str(res)}); continue
        p = res.noul("blocker").noul; a = res.choice("action"); lat.append(res.latency_ms)
        pred = p >= 0.5; ok += pred == lab
        rows.append({"name": name, "label_blocker": lab, "p_blocker": round(p, 2), "correct": pred == lab, "action": a.choice, "p_action": round(a.p_choice, 2)})
    summary = {"n": len(rows), "correct": ok, "acc": round(ok / len(rows), 3), "jev_latency_ms": stats(lat)}
    md = ["# S3 post-render QC blocker gate (raw-footage clip)\n", f"{ok}/{len(rows)} instances classified correctly at p>=0.5; latency ms {stats(lat)}", "\n## Rows\n"] + [f"- {r}" for r in rows]
    write_result("S3_qc_blocker", summary, rows, "\n".join(md) + "\n")


if __name__ == "__main__":
    main()
