"""Deterministic answer-unit splitter over a Scribe word-level transcript.

An answer-unit is a run of consecutive guest phrases (phrases as produced by pack_transcripts.group_into_phrases:
break on silence >= 0.5 s or speaker change). Host phrases shorter than SHORT_HOST_S and under SHORT_HOST_WORDS
words ("Right.", "Yeah.") are absorbed and recorded as interjections. The preceding host phrase is attached as the
question. Units longer than MAX_UNIT_S are split at their largest internal gaps into chunks of at most MAX_UNIT_S.
Everything here is pure text arithmetic; no model is called.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from helpers.pack_transcripts import group_into_phrases  # noqa: E402

SHORT_HOST_S = 1.5
SHORT_HOST_WORDS = 4
MAX_UNIT_S = 90.0
MIN_SPLIT_GAP_S = 0.6
FILLERS = re.compile(r"\b(uh|um|you know|like|I mean|sort of|kind of)\b", re.I)


def load_phrases(transcript_json: Path, silence_threshold: float = 0.5) -> list[dict]:
    data = json.loads(transcript_json.read_text())
    words = data.get("words") or []
    phrases = group_into_phrases(words, silence_threshold)
    for i, p in enumerate(phrases):
        p["idx"] = i
        p["gap_before"] = round(p["start"] - phrases[i - 1]["end"], 3) if i else None
        p["n_words"] = len(p["text"].split())
        p["fillers"] = len(FILLERS.findall(p["text"]))
        p["laugh"] = "(laugh" in p["text"].lower()
    return phrases


def guest_speaker(phrases: list[dict]) -> str:
    c = Counter()
    for p in phrases:
        if p.get("speaker_id"):
            c[p["speaker_id"]] += p["n_words"]
    return c.most_common(1)[0][0]


def _chunk(unit_phrases: list[dict]) -> list[list[dict]]:
    dur = unit_phrases[-1]["end"] - unit_phrases[0]["start"]
    if dur <= MAX_UNIT_S or len(unit_phrases) < 2:
        return [unit_phrases]
    # split at the largest gap that keeps both halves non-trivial, then recurse
    best = None
    for i in range(1, len(unit_phrases)):
        g = unit_phrases[i]["start"] - unit_phrases[i - 1]["end"]
        left = unit_phrases[i - 1]["end"] - unit_phrases[0]["start"]
        if g >= MIN_SPLIT_GAP_S and 15 <= left and (unit_phrases[-1]["end"] - unit_phrases[i]["start"]) >= 15:
            score = g - abs(left - dur / 2) / dur  # prefer big gaps near the middle
            if best is None or score > best[0]:
                best = (score, i)
    if best is None:
        i = len(unit_phrases) // 2
    else:
        i = best[1]
    return _chunk(unit_phrases[:i]) + _chunk(unit_phrases[i:])


def build_units(phrases: list[dict], guest: str | None = None) -> list[dict]:
    guest = guest or guest_speaker(phrases)
    units: list[dict] = []
    run: list[dict] = []
    interjections: list[dict] = []
    question: dict | None = None
    last_host: dict | None = None

    def flush():
        nonlocal run, interjections
        if run:
            for k, chunk in enumerate(_chunk(run)):
                units.append({
                    "id": f"u{len(units):04d}", "start": chunk[0]["start"], "end": chunk[-1]["end"],
                    "duration_s": round(chunk[-1]["end"] - chunk[0]["start"], 2), "speaker": guest,
                    "question": (question or {}).get("text"), "question_start": (question or {}).get("start"),
                    "continues_previous": k > 0, "phrase_idx": [p["idx"] for p in chunk],
                    "text": " ".join(p["text"] for p in chunk),
                    "interjections": [i["text"] for i in interjections if chunk[0]["start"] <= i["start"] <= chunk[-1]["end"]],
                    "n_words": sum(p["n_words"] for p in chunk), "fillers": sum(p["fillers"] for p in chunk),
                    "laughs": sum(1 for p in chunk if p["laugh"]),
                    "gaps": [round(chunk[j]["start"] - chunk[j - 1]["end"], 2) for j in range(1, len(chunk))],
                })
        run, interjections = [], []

    for p in phrases:
        sp = p.get("speaker_id")
        if sp == guest:
            if not run:
                question = last_host
            run.append(p)
        else:
            short = (p["end"] - p["start"]) < SHORT_HOST_S and p["n_words"] <= SHORT_HOST_WORDS
            if run and short:
                interjections.append(p)
                continue
            flush()
            last_host = p
    flush()
    for u in units:
        u["wps"] = round(u["n_words"] / max(u["duration_s"], 0.1), 2)
    return units


def next_host_phrase(phrases: list[dict], unit: dict, guest: str) -> str | None:
    for p in phrases[unit["phrase_idx"][-1] + 1 : unit["phrase_idx"][-1] + 4]:
        if p.get("speaker_id") != guest:
            return p["text"]
    return None


if __name__ == "__main__":
    path = Path(sys.argv[1])
    ph = load_phrases(path)
    g = guest_speaker(ph)
    us = build_units(ph, g)
    print(f"{len(ph)} phrases, guest={g}, {len(us)} units; durations: min {min(u['duration_s'] for u in us)} max {max(u['duration_s'] for u in us)}")
    for u in us[:8]:
        print(u["id"], u["start"], u["end"], u["duration_s"], "Q:", (u["question"] or "")[:60], "|", u["text"][:100])
