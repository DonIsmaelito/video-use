#!/usr/bin/env python3
"""Turn word or ElevenLabs character timestamps into caption-safe ASS subtitles.

The generated captions sit inside a dedicated bottom rail. Use the same rail in
the EDL's ``captions.safe_region`` so render.py can reject colliding overlays.

Usage:
    python helpers/captions.py alignment.json -o master.ass
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PUNCTUATION_BREAKS = ".?!;:"


def _as_word(item: dict) -> dict[str, float | str] | None:
    text = str(item.get("text") or item.get("word") or "").strip()
    if not text:
        return None
    try:
        start = float(item["start"])
        end = float(item["end"])
    except (KeyError, TypeError, ValueError):
        return None
    if end <= start:
        end = start + 0.08
    return {"text": text, "start": start, "end": end}


def _words_from_char_alignment(alignment: dict) -> list[dict[str, float | str]]:
    characters = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not (len(characters) == len(starts) == len(ends)):
        raise ValueError("ElevenLabs character alignment arrays have different lengths")

    words: list[dict[str, float | str]] = []
    buffer: list[str] = []
    word_start: float | None = None
    word_end: float | None = None

    def flush() -> None:
        nonlocal buffer, word_start, word_end
        text = "".join(buffer).strip()
        if text and word_start is not None and word_end is not None:
            words.append({"text": text, "start": word_start, "end": word_end})
        buffer = []
        word_start = None
        word_end = None

    for char, start, end in zip(characters, starts, ends):
        if str(char).isspace():
            flush()
            continue
        if word_start is None:
            word_start = float(start)
        buffer.append(str(char))
        word_end = float(end)
    flush()
    return words


def load_words(payload: dict) -> list[dict[str, float | str]]:
    """Read a generic word list or an ElevenLabs timestamp response."""
    for key in ("normalized_alignment", "alignment"):
        alignment = payload.get(key)
        if isinstance(alignment, dict) and alignment.get("characters") is not None:
            words = _words_from_char_alignment(alignment)
            if words:
                return words

    raw_words = payload.get("words")
    if isinstance(raw_words, list):
        words = [word for item in raw_words if isinstance(item, dict) if (word := _as_word(item))]
        if words:
            return words
    raise ValueError("expected ElevenLabs alignment data or a words array")


def chunk_words(
    words: list[dict[str, float | str]],
    *,
    max_words: int = 6,
    max_characters: int = 44,
) -> list[tuple[float, float, str]]:
    """Create short, readable cues with punctuation-aware boundaries."""
    cues: list[tuple[float, float, str]] = []
    current: list[dict[str, float | str]] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = re.sub(r"\s+", " ", " ".join(str(word["text"]) for word in current)).strip()
        cues.append((float(current[0]["start"]), float(current[-1]["end"]), text))
        current = []

    for word in words:
        proposed = " ".join(str(item["text"]) for item in [*current, word])
        if current and (len(current) >= max_words or len(proposed) > max_characters):
            flush()
        current.append(word)
        if str(word["text"])[-1:] in PUNCTUATION_BREAKS:
            flush()
    flush()
    return cues


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _wrap_two_lines(text: str, max_line_characters: int = 30) -> str:
    if len(text) <= max_line_characters:
        return _ass_escape(text)
    words = text.split()
    if len(words) < 2:
        return _ass_escape(text)
    candidates = []
    for index in range(1, len(words)):
        left = " ".join(words[:index])
        right = " ".join(words[index:])
        candidates.append((max(len(left), len(right)), abs(len(left) - len(right)), left, right))
    _, _, left, right = min(candidates)
    return f"{_ass_escape(left)}\\N{_ass_escape(right)}"


def write_ass(
    cues: list[tuple[float, float, str]],
    output: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    safe_bottom: float = 0.16,
    font: str = "Helvetica",
    font_size: int = 42,
) -> None:
    if not 0.10 <= safe_bottom <= 0.35:
        raise ValueError("safe_bottom must be between 0.10 and 0.35")
    margin_v = max(28, int(height * safe_bottom * 0.22))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{font_size},&H00FFFFFF,&H00FFFFFF,&H00101827,&HC0111728,-1,0,0,0,100,100,0,0,3,2,0,2,72,72,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for start, end, text in cues:
        if end <= start:
            end = start + 0.25
        events.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,"
            f"{_wrap_two_lines(text)}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header + "\n".join(events) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alignment", type=Path, help="ElevenLabs response or generic words JSON")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output .ass path")
    parser.add_argument("--max-words", type=int, default=6)
    parser.add_argument("--max-characters", type=int, default=44)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--safe-bottom", type=float, default=0.16)
    parser.add_argument("--font", default="Helvetica")
    parser.add_argument("--font-size", type=int, default=42)
    args = parser.parse_args()

    payload = json.loads(args.alignment.read_text())
    words = load_words(payload)
    cues = chunk_words(
        words,
        max_words=max(1, args.max_words),
        max_characters=max(12, args.max_characters),
    )
    write_ass(
        cues,
        args.output,
        width=args.width,
        height=args.height,
        safe_bottom=args.safe_bottom,
        font=args.font,
        font_size=args.font_size,
    )
    print(f"captions → {args.output} ({len(cues)} cues)")


if __name__ == "__main__":
    main()
