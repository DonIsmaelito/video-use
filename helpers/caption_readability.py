"""Read-only SRT/ASS timing and text-capacity report, not editorial approval.

Warnings do not change captions or fail a render. Review spoken meaning, timing,
intentional overlap and actual encoded frames before deciding how to revise.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import heapq
import html
import json
import math
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

try:
    from .captions import parse_srt_timestamp, _wrap_text
except ImportError:
    from captions import parse_srt_timestamp, _wrap_text


MAX_BYTES = 1_048_576
MAX_CUES = 4000
MAX_OVERLAP_DETAILS = 1000
SRT_TIME = r"\d{2,}:\d{2}:\d{2}[,.]\d{3}"
ASS_TIME = r"\d+:\d{2}:\d{2}\.\d{2}"


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    line: int
    style: str = ""
    layer: str = ""
    overrides: bool = False
    drawing: bool = False


def _time(value, *, ass=False):
    if not re.fullmatch(ASS_TIME if ass else SRT_TIME, value):
        raise ValueError(f"Invalid {'ASS' if ass else 'SRT'} timestamp: {value!r}")
    parts = re.split(r"[:,.]", value)
    if int(parts[1]) >= 60 or int(parts[2]) >= 60:
        raise ValueError("Caption minutes and seconds must be below 60")
    # Reuse the renderer's SRT clock parser; ASS centiseconds need one zero.
    seconds = parse_srt_timestamp(value + "0" if ass else value)
    if seconds > 86_400:
        raise ValueError("Caption timestamps must not exceed 24 hours")
    return seconds


def _cue(start, end, text, line, **fields):
    if end <= start:
        raise ValueError(f"Caption at line {line} needs a positive duration")
    if not text.strip():
        raise ValueError(f"Caption at line {line} contains no text")
    return Cue(start, end, text, line, **fields)


def _srt(raw):
    cues, blocks, lines, offset = [], [], [], 1
    for number, line in enumerate(raw.splitlines() + [""], start=1):
        if line.strip():
            if not lines:
                offset = number
            lines.append(line)
        elif lines:
            blocks.append((offset, lines))
            lines = []
    for offset, lines in blocks:
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError(f"Malformed SRT block near line {offset}; no cues are silently skipped")
        match = re.fullmatch(rf"\s*({SRT_TIME})\s+-->\s+({SRT_TIME})\s*", lines[1])
        if not match:
            raise ValueError(f"Malformed SRT timing near line {offset + 1}")
        text = "\n".join(lines[2:]).strip()
        markup = bool(re.search(r"</?(?:b|i|u|font)\b[^>]*>", text, re.I))
        text = html.unescape(re.sub(r"</?(?:b|i|u|font)\b[^>]*>", "", text, flags=re.I))
        cues.append(_cue(_time(match[1]), _time(match[2]), text, offset, overrides=markup))
    return cues, {}


def _ass(raw):
    cues, styles = [], {}
    section, event_format, style_format = "", None, None
    for number, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            continue
        if section == "[v4+ styles]":
            if line.lower().startswith("format:"):
                style_format = [s.strip().lower() for s in line.split(":", 1)[1].split(",")]
            elif line.lower().startswith("style:") and style_format:
                parts = [s.strip() for s in line.split(":", 1)[1].split(",", len(style_format) - 1)]
                if len(parts) != len(style_format):
                    raise ValueError(f"Malformed ASS style at line {number}")
                data = dict(zip(style_format, parts))
                if data.get("name"):
                    styles[data["name"]] = data
        if section != "[events]":
            continue
        if line.lower().startswith("format:"):
            event_format = [s.strip().lower() for s in line.split(":", 1)[1].split(",")]
            if len(event_format) != len(set(event_format)) or not {"start", "end", "text"} <= set(event_format) or event_format[-1] != "text":
                raise ValueError("ASS events need unique Start End fields and Text as the last field")
        elif line.lower().startswith("dialogue:"):
            if event_format is None:
                raise ValueError("ASS Dialogue requires an explicit Events Format")
            parts = line.split(":", 1)[1].lstrip().split(",", len(event_format) - 1)
            if len(parts) != len(event_format):
                raise ValueError(f"Malformed ASS Dialogue at line {number}")
            data = dict(zip(event_format, parts))
            text = data["text"]
            overrides = bool(re.search(r"\{[^}]*\}", text))
            drawing = bool(re.search(r"\\p[1-9]\d*\b", text))
            text = re.sub(r"\{[^}]*\}", "", text).replace(r"\N", "\n").replace(r"\n", " ").replace(r"\h", " ")
            cues.append(_cue(_time(data["start"].strip(), ass=True), _time(data["end"].strip(), ass=True),
                             text, number, style=data.get("style", "").strip(), layer=data.get("layer", "").strip(),
                             overrides=overrides, drawing=drawing))
    return cues, styles


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return float(value)


def _layout(font_path, font_size, max_width, max_lines):
    if all(v is None for v in (font_path, font_size, max_width, max_lines)):
        return None
    if any(v is None for v in (font_path, font_size, max_width, max_lines)):
        raise ValueError("Capacity measurement needs font, font_size, max_width and max_lines together")
    for name, value, low, high in (("font_size", font_size, 1, 512), ("max_width", max_width, 8, 8192), ("max_lines", max_lines, 1, 8)):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be an integer between {low} and {high}")
    path = Path(font_path).resolve()
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Font must be no larger than 32 MiB")
    return {"font": ImageFont.truetype(str(path), font_size), "font_size": font_size,
            "max_width": max_width, "max_lines": max_lines,
            "font_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def analyze(path, *, max_cps=24, short_seconds=.8, long_words=5,
            font_path=None, font_size=None, max_width=None, max_lines=None):
    """Report advisory flags without changing text, timestamps, or input files."""
    max_cps = _number(max_cps, "max_cps", 1, 200)
    short_seconds = _number(short_seconds, "short_seconds", .1, 10)
    if type(long_words) is not int or not 2 <= long_words <= 50:
        raise ValueError("long_words must be an integer from 2 through 50")
    layout = _layout(font_path, font_size, max_width, max_lines)
    path = Path(path)
    if path.suffix.lower() not in (".srt", ".ass"):
        raise ValueError("Expected an SRT or ASS file")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Caption file must be no larger than 1 MiB")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError("Caption file must be no larger than 1 MiB")
    raw = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    cues, styles = _ass(raw) if path.suffix.lower() == ".ass" else _srt(raw)
    if not cues or len(cues) > MAX_CUES:
        raise ValueError(f"Expected between 1 and {MAX_CUES} captions")
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    rows = []
    for index, cue in enumerate(cues, start=1):
        text = " ".join(cue.text.split())
        words, characters, duration = len(text.split()), len(text), cue.end - cue.start
        flags = []
        cps = None if cue.drawing else characters / duration
        if cue.drawing:
            flags.append("drawing_event_needs_manual_review")
            words = characters = None
        else:
            emphasis = words == 1 and characters <= 12
            if cps > max_cps and not emphasis:
                flags.append("high_text_density")
            if duration < short_seconds and (words >= long_words or characters >= 30):
                flags.append("short_multiword_cue")
        capacity = {"status": "not_measured"}
        if layout and not cue.drawing:
            lines = []
            for paragraph in cue.text.splitlines():
                lines.extend(_wrap_text(draw, paragraph, layout["font"], layout["max_width"]))
            boxes = [draw.textbbox((0, 0), line, font=layout["font"]) for line in lines]
            widths = [box[2] - box[0] for box in boxes]
            over = len(lines) > layout["max_lines"] or any(w > layout["max_width"] for w in widths)
            capacity = {"status": "fixed_font_estimate", "lines": lines, "line_widths_px": widths,
                        "line_count": len(lines), "exceeds": over,
                        "inline_formatting_ignored": cue.overrides,
                        "source_ass_style": styles.get(cue.style) if cue.style else None}
            if over:
                flags.append("estimated_line_capacity_exceeded")
            if cue.overrides:
                flags.append("inline_formatting_needs_visual_review")
        rows.append({"id": index, "source_line": cue.line, "start": cue.start, "end": cue.end,
                     "duration": round(duration, 6), "text": cue.text, "characters": characters,
                     "kind": "drawing" if cue.drawing else "text",
                     "whitespace_words": words, "characters_per_second": round(cps, 3) if cps is not None else None,
                     "style": cue.style, "layer": cue.layer, "capacity": capacity, "flags": flags})
    # Count every overlap, retaining a bounded set of pairs. Layers may be
    # intentional speaker lanes; temporal overlap requests review, not deletion.
    active, overlaps, total = {}, [], 0
    endings = []
    for row in sorted(rows, key=lambda r: (r["start"], r["id"])):
        while endings and endings[0][0] <= row["start"] + 1e-9:
            _, old = heapq.heappop(endings)
            active.pop(old, None)
        total += len(active)
        if active:
            row["flags"].append("temporal_overlap")
        remaining = MAX_OVERLAP_DETAILS - len(overlaps)
        for prior in list(active.values())[:remaining]:
            overlaps.append({"ids": [prior["id"], row["id"]], "start": row["start"],
                             "end": min(prior["end"], row["end"]),
                             "layers": [prior["layer"], row["layer"]]})
        active[row["id"]] = row
        heapq.heappush(endings, (row["end"], row["id"]))
    return {"schema": "video-use.caption-readability.v1", "source": {"file": path.name, "sha256": hashlib.sha256(data).hexdigest()},
            "status": "review_needed" if any(r["flags"] for r in rows) else "no_automatic_flags",
            "thresholds": {"max_cps": max_cps, "short_seconds": short_seconds, "long_words": long_words},
            "layout": {k: v for k, v in layout.items() if k != "font"} if layout else None,
            "ass_styles": styles or None,
            "cue_count": len(rows), "flagged_cues": sum(bool(r["flags"]) for r in rows), "cues": rows,
            "overlap_count": total, "overlaps": overlaps, "overlap_details_truncated": total > len(overlaps),
            "limits": ["Advisory report only; no caption edits, semantic approval or render gate.",
                       "Character counts include spaces; words use whitespace, not language-specific segmentation.",
                       "Short single-token emphasis up to12 characters is not automatically a density warning.",
                       "Capacity uses the supplied fixed font and word wrapping with explicit line breaks; it is not libass shaping, renderer shrink-to-fit, safe-zone or collision proof.",
                       "ASS positions, transforms, karaoke, inline styling and intentional speaker overlaps need encoded-frame and semantic review."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captions", type=Path)
    parser.add_argument("--max-cps", type=float, default=24)
    parser.add_argument("--short-seconds", type=float, default=.8)
    parser.add_argument("--long-words", type=int, default=5)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--max-width", type=int)
    parser.add_argument("--max-lines", type=int)
    args = parser.parse_args(argv)
    try:
        report = analyze(args.captions, max_cps=args.max_cps, short_seconds=args.short_seconds,
                         long_words=args.long_words, font_path=args.font, font_size=args.font_size,
                         max_width=args.max_width, max_lines=args.max_lines)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
