"""Generate benchmark narration while recording ElevenLabs usage metadata."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests


DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_FORMAT = "mp3_44100_128"


def words_from_alignment(alignment: dict[str, object]) -> list[dict[str, object]]:
    """Collapse ElevenLabs character timings into whitespace-delimited words."""
    characters = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not isinstance(characters, list) or not isinstance(starts, list) or not isinstance(ends, list):
        raise ValueError("ElevenLabs response is missing character alignment arrays")
    if not characters or len(characters) != len(starts) or len(characters) != len(ends):
        raise ValueError("ElevenLabs character alignment arrays have inconsistent lengths")

    words: list[dict[str, object]] = []
    text_parts: list[str] = []
    word_start: float | None = None
    word_end: float | None = None
    start_character = 0

    def flush(end_character: int) -> None:
        nonlocal text_parts, word_start, word_end, start_character
        if text_parts and word_start is not None and word_end is not None:
            words.append(
                {
                    "text": "".join(text_parts),
                    "start": word_start,
                    "end": word_end,
                    "start_character": start_character,
                    "end_character": end_character,
                }
            )
        text_parts = []
        word_start = None
        word_end = None

    for index, (character, start, end) in enumerate(zip(characters, starts, ends)):
        value = str(character)
        if value.isspace():
            flush(index)
            continue
        if word_start is None:
            start_character = index
            word_start = float(start)
        text_parts.append(value)
        word_end = float(end)
    flush(len(characters))
    if not words:
        raise ValueError("ElevenLabs alignment did not contain any timed words")
    return words


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate measured ElevenLabs narration")
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path, default=None)
    parser.add_argument("--alignment-output", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-format", default=DEFAULT_FORMAT)
    args = parser.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
    if not api_key:
        sys.exit("ELEVENLABS_API_KEY is required")
    if not voice_id:
        sys.exit("ELEVENLABS_VOICE_ID is required")
    if not args.text_file.is_file():
        sys.exit(f"narration text not found: {args.text_file}")

    text = args.text_file.read_text(encoding="utf-8").strip()
    if not text:
        sys.exit("narration text is empty")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    start = time.monotonic()
    response = requests.post(
        url,
        params={"output_format": args.output_format},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": args.model},
        timeout=600,
    )
    latency_s = time.monotonic() - start
    raw_cost = response.headers.get("character-cost")
    try:
        character_cost = float(raw_cost) if raw_cost is not None else None
    except ValueError:
        character_cost = None
    audio = b""
    alignment: dict[str, object] | None = None
    words: list[dict[str, object]] = []
    response_error: str | None = None
    if response.status_code == 200:
        try:
            payload = response.json()
            encoded_audio = payload.get("audio_base64")
            if not isinstance(encoded_audio, str) or not encoded_audio:
                raise ValueError("ElevenLabs response is missing audio_base64")
            audio = base64.b64decode(encoded_audio, validate=True)
            raw_alignment = payload.get("normalized_alignment") or payload.get("alignment")
            if not isinstance(raw_alignment, dict):
                raise ValueError("ElevenLabs response is missing timestamp alignment")
            alignment = raw_alignment
            words = words_from_alignment(alignment)
        except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
            response_error = str(exc)
    else:
        response_error = response.text[:500]

    succeeded = response.status_code == 200 and response_error is None and bool(audio)
    metrics_path = args.metrics_output or args.output.with_name(
        f"{args.output.stem}.{uuid.uuid4().hex[:12]}.tts_metrics.json"
    )
    alignment_path = args.alignment_output or args.output.with_name(
        f"{args.output.stem}.alignment.json"
    )
    metrics = {
        "schema_version": 1,
        "provider": "elevenlabs",
        "model": args.model,
        "output_format": args.output_format,
        "voice_id_sha256": hashlib.sha256(voice_id.encode("utf-8")).hexdigest(),
        "text_characters": len(text),
        "character_cost": character_cost,
        "estimated_character_units": (
            character_cost
            if character_cost is not None
            else (len(text) if response.status_code == 200 else 0)
        ),
        "latency_s": latency_s,
        "http_status": response.status_code,
        "succeeded": succeeded,
        "audio_bytes": len(audio),
        "alignment_characters": len(alignment.get("characters", [])) if alignment else 0,
        "alignment_words": len(words),
        "response_error": response_error,
        "request_id": response.headers.get("request-id"),
        "trace_id": response.headers.get("x-trace-id"),
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not succeeded:
        raise RuntimeError(
            f"ElevenLabs narration failed ({response.status_code}): {response_error or 'unknown response error'}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(audio)
    alignment_path.parent.mkdir(parents=True, exist_ok=True)
    alignment_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider": "elevenlabs",
                "model": args.model,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "duration_s": float(words[-1]["end"]),
                "words": words,
                "characters": alignment["characters"],
                "character_start_times_seconds": alignment["character_start_times_seconds"],
                "character_end_times_seconds": alignment["character_end_times_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"saved narration: {args.output}")
    print(f"saved alignment: {alignment_path}")
    print(f"saved metrics: {metrics_path}")


if __name__ == "__main__":
    main()
