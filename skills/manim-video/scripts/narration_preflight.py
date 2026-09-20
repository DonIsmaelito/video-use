#!/usr/bin/env python3
"""Estimate narration duration before making a paid TTS request."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


WORD_PATTERN = re.compile(r"[\w]+(?:['\u2019-][\w]+)*", re.UNICODE)


def estimate(
    text: str,
    *,
    min_duration_s: float,
    max_duration_s: float,
    words_per_minute: float,
    safety_margin_s: float = 0.0,
) -> dict[str, float | int | bool]:
    if min_duration_s <= 0 or max_duration_s < min_duration_s:
        raise ValueError("duration range must be positive and ordered")
    if words_per_minute <= 0:
        raise ValueError("words per minute must be positive")
    if safety_margin_s < 0:
        raise ValueError("safety margin cannot be negative")
    planning_max_duration_s = max_duration_s - safety_margin_s
    if planning_max_duration_s < min_duration_s:
        raise ValueError("safety margin leaves no valid duration range")
    word_count = len(WORD_PATTERN.findall(text))
    estimated_duration_s = word_count / words_per_minute * 60.0
    return {
        "word_count": word_count,
        "words_per_minute": words_per_minute,
        "estimated_duration_s": estimated_duration_s,
        "target_min_duration_s": min_duration_s,
        "target_max_duration_s": max_duration_s,
        "safety_margin_s": safety_margin_s,
        "planning_max_duration_s": planning_max_duration_s,
        "recommended_min_words": math.ceil(min_duration_s * words_per_minute / 60.0),
        "recommended_max_words": math.floor(planning_max_duration_s * words_per_minute / 60.0),
        "estimated_in_range": min_duration_s <= estimated_duration_s <= planning_max_duration_s,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate narration duration without calling a TTS provider"
    )
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--min-duration-s", type=float, required=True)
    parser.add_argument("--max-duration-s", type=float, required=True)
    parser.add_argument("--words-per-minute", type=float, default=145.0)
    parser.add_argument(
        "--safety-margin-s",
        type=float,
        default=0.0,
        help="reserve this many seconds below the hard maximum for TTS timing variance",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if not args.text_file.is_file():
        parser.error(f"narration text not found: {args.text_file}")
    text = args.text_file.read_text(encoding="utf-8").strip()
    if not text:
        parser.error("narration text is empty")
    try:
        result = estimate(
            text,
            min_duration_s=args.min_duration_s,
            max_duration_s=args.max_duration_s,
            words_per_minute=args.words_per_minute,
            safety_margin_s=args.safety_margin_s,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"{result['word_count']} words -> approximately "
            f"{result['estimated_duration_s']:.1f}s at {result['words_per_minute']:.1f} WPM"
        )
        print(
            f"target {result['target_min_duration_s']:.1f}-"
            f"{result['target_max_duration_s']:.1f}s; planning ceiling "
            f"{result['planning_max_duration_s']:.1f}s after "
            f"{result['safety_margin_s']:.1f}s safety margin; recommended "
            f"{result['recommended_min_words']}-"
            f"{result['recommended_max_words']} words"
        )
        print("preflight: PASS" if result["estimated_in_range"] else "preflight: REVISE")
    raise SystemExit(0 if result["estimated_in_range"] else 2)


if __name__ == "__main__":
    main()
