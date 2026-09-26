#!/usr/bin/env python3
"""Live editing session: record (Mac camera and mic, or replay a file at real time), transcribe as you
speak, let Jev judge every phrase and every answer, and cut, caption and render vertical clips while
the recording is still running. When you stop, the clips are already on disk.

Pipeline (all threads inside one process):
  ffmpeg capture -> fragmented MP4 on disk (readable while growing) + 16 kHz PCM pipe
  PCM -> ElevenLabs Scribe v2 realtime (WebSocket, manual commits at our silences) -> words with
  stream timestamps -> phrases (silence >= 0.5 s) -> Jev per phrase (disposable, ends a thought)
  -> units (answers) -> Jev per unit (standalone, hook, payoff) -> cut (pause tightening, padding,
  edge rules) -> ffmpeg clip: ranges concat, 9:16 frame, captions burned last, hardware H.264.

Events are pushed to on_event(dict) for a UI. Outputs: <session>/recording.mp4, words.json,
phrases.json, units.json, clips/clip_NN.mp4 (+ .srt, .ass, .json), session.json.
"""
from __future__ import annotations

import base64
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev import Jev, choice, noul  # noqa: E402
from transcribe import load_api_key  # noqa: E402

REALTIME_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
CHUNK_BYTES = 8000  # 250 ms of 16 kHz mono int16
AUDIO_EVENT = re.compile(r"^\W*\(\[?[a-z ]+\]?\)\W*$", re.I)


def _ffmpeg_caps() -> dict:
    """Which encoder and caption path this machine's ffmpeg supports (probed once)."""
    import platform
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    filt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    forced = os.environ.get("JEV_VIDEO_ENCODER")
    if forced:
        encoder = forced
    elif "h264_nvenc" in enc and (Path("/dev/nvidia0").exists() or Path("/dev/nvidiactl").exists()):
        encoder = "h264_nvenc"
    elif "h264_videotoolbox" in enc and platform.system() == "Darwin":
        encoder = "h264_videotoolbox"
    else:
        encoder = "libx264"
    return {"encoder": encoder, "subtitles": " subtitles " in filt}


_CAPS: dict = {}
HOOK = {"0": "generic setup, context or a question; nothing quotable", "1": "an ordinary point, mildly interesting",
        "2": "a clear, interesting claim or story beat in the first line", "3": "surprising, funny, provocative or quotable from the first sentence"}


def rms(pcm: bytes) -> float:
    import array
    a = array.array("h"); a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not a:
        return 0.0
    return (sum(x * x for x in a) / len(a)) ** 0.5


class LiveSession:
    def __init__(self, session_dir: str | os.PathLike, *, mode: str = "mic", source: str | None = None, start_s: float = 0.0, duration_s: float | None = None,
                 frame: str = "crop", video_device: str = "0", audio_device: str = "0", on_event=None, language: str = "en", container: str = "mp4",
                 phrase_gap: float = 0.5, unit_gap: float = 2.0, tighten: float = 0.9, min_clip: float = 15.0, max_clip: float = 90.0, clip_threshold: float = 0.35):
        self.dir = Path(session_dir); self.dir.mkdir(parents=True, exist_ok=True); (self.dir / "clips").mkdir(exist_ok=True)
        self.mode, self.source, self.start_s, self.duration_s, self.frame = mode, source, start_s, duration_s, frame
        self.video_device, self.audio_device, self.language = video_device, audio_device, language
        self.on_event = on_event or (lambda e: None)
        self.phrase_gap, self.unit_gap, self.tighten, self.min_clip, self.max_clip, self.clip_threshold = phrase_gap, unit_gap, tighten, min_clip, max_clip, clip_threshold
        self.recording = self.dir / f"recording.{container if mode == 'remote' else 'mp4'}"
        self.jev = Jev(log_path=self.dir / "jev_decisions.jsonl")
        self.words: list[dict] = []; self.phrases: list[dict] = []; self.units: list[dict] = []; self.clips: list[dict] = []
        self._audio_q: queue.Queue = queue.Queue(); self._word_q: queue.Queue = queue.Queue()
        self._stop = threading.Event(); self._proc = None; self._threads: list[threading.Thread] = []
        self._audio_seconds = 0.0; self._last_commit = 0.0; self._quiet_run = 0.0; self._ws = None
        self._pending: list[dict] = []; self._unit: list[dict] = []; self._starts: list[int] = []; self._clipped: list[tuple[float, float]] = []
        self._pool = ThreadPoolExecutor(max_workers=2); self._clip_futures = []; self._clip_lock = threading.Lock(); self._clip_counter = 0
        self.started_at = None; self.stopped_at = None; self._final_commit = threading.Event()

    # ------------------------------------------------------------ events
    def emit(self, kind: str, msg: str = "", **data) -> None:
        ev = {"t": round(time.time() - self.started_at, 2) if self.started_at else 0.0, "type": kind, "msg": msg, **data}
        try:
            self.on_event(ev)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ capture
    def _capture_cmd(self) -> list[str]:
        out = [*("-map", "0:v", "-c:v", "h264_videotoolbox", "-b:v", "6M", "-g", "30", "-pix_fmt", "yuv420p",
                 "-map", "0:a", "-c:a", "aac", "-b:a", "160k", "-movflags", "+frag_keyframe+empty_moov+default_base_moof", str(self.recording)),
               *("-map", "0:a", "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1")]
        if self.mode == "replay":
            inp = ["-re", "-ss", str(self.start_s)] + (["-t", str(self.duration_s)] if self.duration_s else []) + ["-i", str(self.source)]
        else:
            inp = ["-f", "avfoundation", "-framerate", "30", "-video_size", "1280x720", "-i", f"{self.video_device}:{self.audio_device}"]
        return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inp, *out]

    def _pcm_reader(self) -> None:
        assert self._proc and self._proc.stdout
        while not self._stop.is_set():
            data = self._proc.stdout.read(CHUNK_BYTES)
            if not data:
                break
            self._audio_q.put(data)
        self._audio_q.put(None)

    # ------------------------------------------------------------ asr
    def _asr(self) -> None:
        try:
            self._asr_inner()
        except Exception as exc:  # noqa: BLE001
            self.emit("asr_error", f"transcription thread failed: {exc}")
            self._word_q.put(None)

    def _connect_asr(self, offset_s: float):
        import websocket  # websocket-client
        key = load_api_key()
        url = f"{REALTIME_URL}?model_id=scribe_v2_realtime&audio_format=pcm_16000&commit_strategy=manual&include_timestamps=true&language_code={self.language}"
        ws = websocket.create_connection(url, header=[f"xi-api-key: {key}"], timeout=30)
        self._ws = ws
        self.emit("asr", f"realtime transcription connected (clock offset {offset_s:.2f}s)")

        def rx():
            while True:
                try:
                    m = ws.recv()
                except Exception:
                    break
                if not m:
                    break
                o = json.loads(m); mt = o.get("message_type")
                if mt == "partial_transcript":
                    self.emit("partial", o.get("text", "")[-160:])
                elif mt == "committed_transcript_with_timestamps":
                    words = [dict(w, start=float(w["start"]) + offset_s, end=float(w["end"]) + offset_s) for w in (o.get("words") or []) if w.get("type") == "word" and w.get("start") is not None]
                    self._word_q.put(words)
                    self.emit("committed", f"{len(words)} words up to {words[-1]['end']:.2f}s" if words else "empty commit", words=len(words))
                    if self._stop.is_set():
                        self._final_commit.set()
                elif mt and (mt.endswith("error") or mt in ("quota_exceeded", "rate_limited", "queue_overflow", "commit_throttled", "input_error", "invalid_request", "session_time_limit_exceeded")):
                    self.emit("asr_error", f"{mt}: {o.get('error')}")
        threading.Thread(target=rx, daemon=True, name="asr-rx").start()
        return ws

    def _asr_inner(self) -> None:
        ws = self._connect_asr(0.0)
        loud_ref = 400.0
        while True:
            data = self._audio_q.get()
            if data is None:
                break
            self._audio_seconds += len(data) / 32000.0
            level = rms(data)
            loud_ref = max(loud_ref * 0.995, level, 150.0)  # slowly decaying reference of how loud speech is
            quiet = level < 0.25 * loud_ref
            self._quiet_run = self._quiet_run + 0.25 if quiet else 0.0
            since = self._audio_seconds - self._last_commit
            # commit only inside a silence so no word is cut in half; the model would auto-commit at 36 s
            commit = (since >= 5.0 and self._quiet_run >= 0.5) or (since >= 18.0 and quiet) or since >= 24.0
            if commit:
                self._last_commit = self._audio_seconds; self._quiet_run = 0.0
            try:
                ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": base64.b64encode(data).decode(), "commit": commit, "sample_rate": 16000}))
            except Exception as exc:  # noqa: BLE001
                # the server closed the session (time limit or hiccup): reopen with the clock carried forward
                self.emit("asr_error", f"send failed ({exc}); reconnecting")
                try:
                    ws = self._connect_asr(self._audio_seconds - len(data) / 32000.0)
                    self._last_commit = self._audio_seconds
                    ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": base64.b64encode(data).decode(), "commit": False, "sample_rate": 16000}))
                except Exception as exc2:  # noqa: BLE001
                    self.emit("asr_error", f"reconnect failed: {exc2}"); break
        # final commit with a little silence so the last words are flushed
        try:
            ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": base64.b64encode(b"\x00" * CHUNK_BYTES).decode(), "commit": True, "sample_rate": 16000}))
            self._final_commit.wait(timeout=8)
            ws.close()
        except Exception:  # noqa: BLE001
            pass
        self._word_q.put(None)

    # ------------------------------------------------------------ editor
    def _editor(self) -> None:
        while True:
            batch = self._word_q.get()
            if batch is None:
                break
            for w in batch:
                w = {"text": w["text"], "start": float(w["start"]), "end": float(w["end"]), "speaker": w.get("speaker_id")}
                self.words.append(w)
                if self._pending and w["start"] - self._pending[-1]["end"] >= self.phrase_gap:
                    self._close_phrase()
                self._pending.append(w)
        self._close_phrase(final=True)
        (self.dir / "words.json").write_text(json.dumps({"words": self.words}))
        (self.dir / "phrases.json").write_text(json.dumps(self.phrases, indent=1))
        (self.dir / "units.json").write_text(json.dumps(self.units, indent=1))

    def _close_phrase(self, final: bool = False) -> None:
        if not self._pending:
            return
        words = self._pending; self._pending = []
        text = " ".join(w["text"] for w in words)
        ph = {"idx": len(self.phrases), "start": words[0]["start"], "end": words[-1]["end"], "text": text, "words": words, "n_words": len(words),
              "gap_before": round(words[0]["start"] - self.phrases[-1]["end"], 2) if self.phrases else None}
        prev = self.phrases[-1]["text"] if self.phrases else None
        t0 = time.perf_counter()
        if AUDIO_EVENT.match(text):
            ph.update({"disposable": None, "ends_thought": 0.0, "question": 0.0, "kept": True})
        else:
            qs = {"disposable": noul("This phrase is a false start, filler-only, a verbatim repetition, or a listener interjection that can be removed from the clip without losing meaning."),
                  "ends_thought": noul("This phrase ends a complete thought or sentence; the speaker could stop here and the point would be made."),
                  "question": noul("This phrase is a question put to the main speaker by another person, such as an interviewer or host, rather than part of the speaker's own answer.")}
            if not self.phrases or (ph["gap_before"] or 0) >= 1.5:
                qs["hook"] = choice("Rate how strong this opening is as the first line of a social clip.", HOOK)
            state = {"phrase": text, "previous_phrase": prev, "seconds_of_silence_before": ph["gap_before"], "duration_s": round(ph["end"] - ph["start"], 2)}
            try:
                r = self.jev.ask(state, qs, tag="live_phrase")
                ph["disposable"] = round(r.noul("disposable").noul, 2); ph["ends_thought"] = round(r.noul("ends_thought").noul, 2); ph["question"] = round(r.noul("question").noul, 2)
                if "hook" in qs:
                    h = r.choice("hook"); ph["hook"] = round(sum(int(k) * v for k, v in h.probabilities.items()) / 3.0, 2)
                ph["jev_ms"] = round(r.latency_ms)
            except Exception as exc:  # noqa: BLE001
                ph.update({"disposable": 0.0, "ends_thought": 0.0, "question": 0.0, "jev_error": str(exc)[:120]})
            ph["kept"] = ph["disposable"] < 0.6 and ph["question"] < 0.6
        ph["jev_wall_ms"] = round((time.perf_counter() - t0) * 1000)
        self.phrases.append(ph)
        self.emit("phrase", text, start=ph["start"], end=ph["end"], kept=ph["kept"], disposable=ph.get("disposable"), ends_thought=ph.get("ends_thought"), question=ph.get("question"), hook=ph.get("hook"), gap_before=ph["gap_before"], jev_ms=ph.get("jev_ms"), unit=len(self.units) + 1)
        prev_ph = self.phrases[-2] if len(self.phrases) > 1 else None
        # a phrase can start a clip when it opens the recording, follows a long pause, follows a question,
        # or follows a finished thought; it can end one when it finishes a thought or precedes a pause
        if prev_ph is None or (ph["gap_before"] or 0) >= 1.5 or ph.get("question", 0) >= 0.4 or (prev_ph.get("ends_thought") or 0) >= 0.6 or (prev_ph.get("question") or 0) >= 0.4:
            self._starts.append(ph["idx"])
        if prev_ph is not None and ((prev_ph.get("ends_thought") or 0) >= 0.5 or (ph["gap_before"] or 0) >= 1.0 or ph.get("question", 0) >= 0.4):
            self._evaluate_end(prev_ph["idx"])
        if final:
            self._evaluate_end(ph["idx"], final=True)

    def _covered(self, a: float, b: float) -> float:
        return sum(max(0.0, min(b, y) - max(a, x)) for x, y in self._clipped) / max(b - a, 1e-6)

    def _evaluate_end(self, end_idx: int, final: bool = False) -> None:
        """Score every plausible clip ending at phrase end_idx; make the best one when it clears the bar."""
        end_ph = self.phrases[end_idx]
        cands = []
        for s in reversed(self._starts):
            if s > end_idx:
                continue
            phrases = self.phrases[s:end_idx + 1]
            kept = [p for p in phrases if p["kept"]]
            if not kept:
                continue
            dur = kept[-1]["end"] - kept[0]["start"]
            if dur < self.min_clip:
                continue
            if dur > self.max_clip or len(cands) >= 3:
                break
            if self._covered(kept[0]["start"], kept[-1]["end"]) > 0.4:
                continue
            cands.append((s, phrases, kept, dur))
        if not cands:
            return
        items = []
        for s, phrases, kept, dur in cands:
            text = " ".join(p["text"] for p in kept)
            items.append(({"context": "A spoken answer from a recording being cut into standalone short vertical social clips (15-90 s).",
                           "answer_first_400_chars": text[:400], "answer_last_200_chars": text[-200:], "duration_s": round(dur, 1)},
                          {"standalone": noul("A viewer who has heard nothing before this answer would understand it and find it complete on its own."),
                           "hook": choice("Rate how strong the opening of this answer is as the first line of a social clip.", HOOK),
                           "payoff": noul("The answer ends on a complete thought, punchline or memorable claim rather than trailing off mid-argument.")}))
        results = self.jev.ask_many(items, workers=3, tag="live_unit")
        scored = []
        for (s, phrases, kept, dur), r in zip(cands, results):
            if isinstance(r, Exception):
                continue
            h = r.choice("hook"); hook = sum(int(k) * v for k, v in h.probabilities.items()) / 3.0
            u = {"idx": len(self.units) + 1, "start": kept[0]["start"], "end": kept[-1]["end"], "duration_s": round(dur, 2), "text": " ".join(p["text"] for p in kept), "n_phrases": len(phrases), "n_kept": len(kept),
                 "standalone": round(r.noul("standalone").noul, 2), "hook": round(hook, 2), "payoff": round(r.noul("payoff").noul, 2), "jev_ms": round(r.latency_ms), "start_idx": s, "end_idx": end_idx}
            u["score"] = round(0.5 * u["payoff"] + 0.3 * u["hook"] + 0.2 * u["standalone"], 3)
            scored.append((u, phrases))
        if not scored:
            return
        scored.sort(key=lambda x: -x[0]["score"])
        best, phrases = scored[0]
        best["verdict"] = "clip" if best["score"] >= self.clip_threshold else "skip"
        best["candidates"] = [(u["start_idx"], u["score"]) for u, _ in scored]
        self.units.append(best)
        self.emit("unit", f"candidate ending at {end_ph['end']:.1f}s: best {best['duration_s']}s from {best['start']:.1f}s score {best['score']} -> {best['verdict']} ({len(scored)} candidates)", **{k: v for k, v in best.items() if k not in ("text",)}, preview=best["text"][:140])
        if best["verdict"] == "clip":
            self._clipped.append((best["start"], best["end"]))
            self._clip_futures.append(self._pool.submit(self._make_clip, best, phrases, self._next_clip_name()))

    # ------------------------------------------------------------ clips
    def _next_clip_name(self) -> str:
        with self._clip_lock:
            self._clip_counter += 1
            return f"clip_{self._clip_counter:02d}"

    def _make_clip(self, unit: dict, phrases: list[dict], name: str | None = None) -> dict | None:
        name = name or self._next_clip_name()
        t0 = time.perf_counter()
        try:
            self.emit("clip", f"{name}: cutting unit {unit['idx']}", clip=name, unit=unit["idx"])
            kept = [p for p in phrases if p["kept"]]
            # groups of consecutive kept phrases; split on a dropped phrase or a pause >= tighten
            groups: list[list[dict]] = []
            for p in phrases:
                if not p["kept"]:
                    if groups and groups[-1]:
                        groups.append([])
                    continue
                if groups and groups[-1] and (p["start"] - groups[-1][-1]["end"]) < self.tighten:
                    groups[-1].append(p)
                else:
                    groups.append([p])
            groups = [g for g in groups if g]
            ranges = []
            all_words = self.words
            for gi, g in enumerate(groups):
                s, e = g[0]["start"] - 0.05, g[-1]["end"] + 0.08
                before = [w["end"] for w in all_words if w["end"] <= g[0]["start"] + 1e-3 and w["end"] > g[0]["start"] - 3]
                after = [w["start"] for w in all_words if w["start"] >= g[-1]["end"] - 1e-3 and w["start"] < g[-1]["end"] + 3]
                if before: s = max(s, max(before) + 0.01)
                if after: e = min(e, min(after) - 0.01)
                if gi and s < ranges[-1]["end"]: s = ranges[-1]["end"]
                ranges.append({"start": round(max(s, 0), 3), "end": round(e, 3), "text": " ".join(p["text"] for p in g), "words": [w for p in g for w in p["words"]]})
            total = sum(r["end"] - r["start"] for r in ranges)
            while total > self.max_clip and len(ranges) > 1:
                total -= ranges[-1]["end"] - ranges[-1]["start"]; ranges.pop()
            # captions in output time
            cues = []; offset = 0.0
            for r in ranges:
                chunk: list[dict] = []
                for w in r["words"]:
                    chunk.append(w)
                    if len(chunk) >= 3 or re.search(r"[.!?,]$", w["text"]):
                        cues.append((chunk[0]["start"] - r["start"] + offset, chunk[-1]["end"] - r["start"] + offset, " ".join(x["text"] for x in chunk).upper())); chunk = []
                if chunk:
                    cues.append((chunk[0]["start"] - r["start"] + offset, chunk[-1]["end"] - r["start"] + offset, " ".join(x["text"] for x in chunk).upper()))
                offset += r["end"] - r["start"]
            ass = self.dir / "clips" / f"{name}.ass"; srt = self.dir / "clips" / f"{name}.srt"; out = self.dir / "clips" / f"{name}.mp4"
            self._write_ass(ass, cues); self._write_srt(srt, cues)
            # ffmpeg: one seeked input per range (cost stays flat as the recording grows), concat,
            # 9:16 framing, a caption band overlaid last, loudness normalised in the same graph
            from captions import CaptionCue, render_caption_image  # noqa: PLC0415
            band_h, band_y = 380, 1380
            cap_dir = self.dir / "clips" / f"{name}_captions"; cap_dir.mkdir(exist_ok=True)
            blank = cap_dir / "blank.png"
            from PIL import Image  # noqa: PLC0415
            Image.new("RGBA", (1080, band_h), (0, 0, 0, 0)).save(blank, compress_level=1)
            cap_cfg = {"font_size": 78, "x": 0.5, "y": 0.5, "stroke_width": 5, "stroke": "#000000", "fill": "#FFFFFF", "font": "Helvetica"}
            lines = ["ffconcat version 1.0"]; cursor = 0.0
            for i, (a, b, text) in enumerate(cues, 1):
                a = max(cursor, min(a, total)); b = min(total, max(b, a))
                if a > cursor:
                    lines += [f"file 'blank.png'", f"duration {a - cursor:.3f}"]; cursor = a
                if b <= a:
                    continue
                img = cap_dir / f"cue_{i:04d}.png"
                render_caption_image(CaptionCue(a, b, text), img, width=1080, height=band_h, config=cap_cfg)
                lines += [f"file '{img.name}'", f"duration {max(0.04, b - a):.3f}"]; cursor = b
            if cursor < total:
                lines += ["file 'blank.png'", f"duration {total - cursor:.3f}"]
            lines.append("file 'blank.png'")
            cap_track = cap_dir / "captions.ffconcat"; cap_track.write_text("\n".join(lines) + "\n")
            inputs = []; fc = []; parts = []
            for i, r in enumerate(ranges):
                d = r["end"] - r["start"]
                inputs += ["-ss", f"{r['start']:.3f}", "-to", f"{r['end']:.3f}", "-i", str(self.recording)]
                fc.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}];[{i}:a]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.03,afade=t=out:st={max(d-0.03,0):.3f}:d=0.03[a{i}]")
                parts.append(f"[v{i}][a{i}]")
            cap_index = len(ranges)
            inputs += ["-f", "concat", "-safe", "0", "-i", str(cap_track)]
            fc.append(f"{''.join(parts)}concat=n={len(ranges)}:v=1:a=1[cv][ca]")
            if self.frame == "crop":
                framing = "crop=ih*9/16:ih,scale=1080:1920"
            else:
                framing = "split[bg][fg];[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:2,scale=1080:1920,eq=brightness=-0.15[bgb];[fg]scale=1080:-2[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
            if not _CAPS:
                _CAPS.update(_ffmpeg_caps())
            if _CAPS["subtitles"]:
                # libass is present: burn the ASS directly (fast) and drop the PNG band input
                inputs = inputs[:-6]  # drop "-f concat -safe 0 -i <track>"
                fc.append(f"[cv]{framing},subtitles={ass.name}[outv];[ca]loudnorm=I=-14:TP=-1:LRA=11[outa]")
            else:
                fc.append(f"[cv]{framing}[fr];[{cap_index}:v]format=rgba[cap];[fr][cap]overlay=0:{band_y}:eof_action=pass:format=auto[outv];[ca]loudnorm=I=-14:TP=-1:LRA=11[outa]")
            enc = {"h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "8M"], "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "8M"], "libx264": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]}[_CAPS["encoder"]]
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[outv]", "-map", "[outa]",
                   *enc, "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.dir / "clips"))
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr[-400:])
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip() or 0)
            meta = {"clip": name, "file": str(out), "srt": str(srt), "duration_s": round(dur, 2), "encoder": _CAPS.get("encoder"), "captions": "libass" if _CAPS.get("subtitles") else "pil-band", "source_ranges": [{"start": r["start"], "end": r["end"]} for r in ranges], "unit": unit["idx"],
                    "hook_line": ranges[0]["text"][:120], "text": " ".join(r["text"] for r in ranges), "scores": {k: unit.get(k) for k in ("standalone", "hook", "payoff", "score")},
                    "cues": len(cues), "render_s": round(time.perf_counter() - t0, 2), "frame": self.frame}
            (self.dir / "clips" / f"{name}.json").write_text(json.dumps(meta, indent=1))
            self.clips.append(meta)
            self.emit("clip_ready", f"{name}: {meta['duration_s']}s from {len(ranges)} ranges in {meta['render_s']}s", **meta)
            return meta
        except Exception as exc:  # noqa: BLE001
            self.emit("clip_error", f"{name}: {exc}", clip=name)
            return None

    @staticmethod
    def _ass_time(s: float) -> str:
        s = max(0.0, s); h = int(s // 3600); m = int(s % 3600 // 60); sec = s % 60
        return f"{h:d}:{m:02d}:{sec:05.2f}"

    def _write_ass(self, path: Path, cues) -> None:
        head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Cap,Liberation Sans,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,420,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        lines = [head]
        for a, b, text in cues:
            lines.append(f"Dialogue: 0,{self._ass_time(a)},{self._ass_time(b)},Cap,,0,0,0,,{text.replace(chr(10), ' ')}\n")
        path.write_text("".join(lines))

    @staticmethod
    def _write_srt(path: Path, cues) -> None:
        def ts(s):
            s = max(0.0, s); h = int(s // 3600); m = int(s % 3600 // 60); sec = int(s % 60); ms = int(round((s - int(s)) * 1000))
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
        path.write_text("".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1)))

    # ------------------------------------------------------------ lifecycle
    # remote mode: a client streams 16 kHz mono int16 audio and appends the growing recording file
    def feed_audio(self, pcm: bytes) -> None:
        self._audio_q.put(pcm)

    def append_video(self, data: bytes, offset: int | None = None) -> int:
        with self._video_lock:
            with open(self.recording, "ab") as f:
                if offset is not None and offset < f.tell():
                    return f.tell()  # duplicate chunk after a retry
                f.write(data)
                return f.tell()

    def start(self) -> None:
        self.started_at = time.time()
        if self.mode == "remote":
            self._video_lock = threading.Lock()
            self.recording.touch()
            self.emit("status", "remote session started: waiting for audio and video", mode=self.mode)
            threads = (("asr", self._asr), ("editor", self._editor))
        else:
            self._proc = subprocess.Popen(self._capture_cmd(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.emit("status", f"recording started ({self.mode}) -> {self.recording.name}", mode=self.mode)
            threads = (("pcm", self._pcm_reader), ("asr", self._asr), ("editor", self._editor))
        for name, fn in threads:
            t = threading.Thread(target=fn, daemon=True, name=name); t.start(); self._threads.append(t)

    def stop(self) -> dict:
        if self.stopped_at:
            return self._summary()
        self._stop.set(); self.stopped_at = time.time()
        self.emit("status", "stopping: finalising transcript and remaining clips")
        if self.mode == "remote":
            self._audio_q.put(None)
        else:
            try:
                if self._proc and self._proc.stdin and self._proc.poll() is None:
                    self._proc.stdin.write(b"q"); self._proc.stdin.flush()
            except Exception:  # noqa: BLE001
                pass
            try:
                if self._proc and self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._proc.wait(timeout=15)
            except Exception:  # noqa: BLE001
                self._proc.kill()
        for t in self._threads:
            t.join(timeout=60)
        for f in list(self._clip_futures):
            try: f.result(timeout=180)
            except Exception: pass
        summary = self._summary()
        (self.dir / "session.json").write_text(json.dumps(summary, indent=1))
        self.emit("done", f"{len(self.clips)} clips ready {summary['finished_s_after_stop']}s after stop", **{k: v for k, v in summary.items() if k != "clips"}, n_clips=len(self.clips))
        return summary

    def _summary(self) -> dict:
        return {"mode": self.mode, "recording": str(self.recording), "seconds_recorded": round((self.stopped_at or time.time()) - self.started_at, 1), "words": len(self.words), "phrases": len(self.phrases),
                "units": len(self.units), "clips": self.clips, "jev_calls": self.jev.calls, "jev_mean_ms": round(self.jev.total_latency_ms / max(self.jev.calls, 1)), "finished_s_after_stop": round(time.time() - (self.stopped_at or time.time()), 1)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["mic", "replay"], default="replay"); ap.add_argument("--source"); ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--duration", type=float)
    ap.add_argument("--frame", choices=["crop", "contain"], default="crop"); ap.add_argument("--out", required=True); ap.add_argument("--seconds", type=float, help="record this long then stop (mic mode)")
    a = ap.parse_args()
    s = LiveSession(a.out, mode=a.mode, source=a.source, start_s=a.start, duration_s=a.duration, frame=a.frame, on_event=lambda e: print(f"[{e['t']:7.2f}] {e['type']:10s} {e['msg'][:150]}", flush=True))
    s.start()
    try:
        limit = a.duration if a.mode == "replay" else a.seconds
        t0 = time.time()
        while s._proc.poll() is None and (limit is None or time.time() - t0 < (limit or 0) + 2):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print(json.dumps(s.stop(), indent=1)[:1500])
