"""Transcribe a video with ElevenLabs Scribe.

Extracts mono 16kHz audio via ffmpeg, uploads to Scribe with verbatim +
diarize + audio events + word-level timestamps, writes the full response
to <edit_dir>/transcripts/<video_stem>.json.

Cached by source bytes and transcription settings. A conflicting or unverified
existing transcript is preserved and rejected instead of silently reused.

Usage:
    python helpers/transcribe.py <video_path>
    python helpers/transcribe.py <video_path> --edit-dir /custom/edit
    python helpers/transcribe.py <video_path> --language en
    python helpers/transcribe.py <video_path> --num-speakers 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import dotenv_values


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v2"
MODELS = ("scribe_v2", "scribe_v1")


def load_api_key() -> str:
    value = os.environ.get("ELEVENLABS_API_KEY", "")
    if value:
        return value
    for candidate in [Path(__file__).resolve().parent.parent / ".env", Path(".env")]:
        if candidate.exists():
            value = dotenv_values(candidate, interpolate=False).get("ELEVENLABS_API_KEY")
            if value:
                return value
    sys.exit("ELEVENLABS_API_KEY not found in .env or environment")


def source_identity(video: Path, language: str | None, num_speakers: int | None, model: str) -> dict:
    if model not in MODELS:
        raise ValueError("Unsupported Scribe model")
    if num_speakers is not None and (isinstance(num_speakers, bool) or not isinstance(num_speakers, int) or not 1 <= num_speakers <= 32):
        raise ValueError("num_speakers must be an integer from 1 through 32")
    digest = hashlib.sha256()
    with video.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"version": 1, "source_sha256": digest.hexdigest(),
            "model_id": model, "language_code": language, "num_speakers": num_speakers,
            "diarize": True, "tag_audio_events": True, "timestamps_granularity": "word"}


def cached_transcript(video: Path, edit_dir: Path, language: str | None = None,
                      num_speakers: int | None = None, model: str = DEFAULT_MODEL) -> Path | None:
    identity = source_identity(video, language, num_speakers, model)
    out_path = edit_dir / "transcripts" / f"{video.stem}.json"
    if not out_path.exists():
        return None
    if out_path.is_symlink():
        raise ValueError("Transcript output must not be a symlink")
    try:
        payload = json.loads(out_path.read_text())
    except (ValueError, UnicodeError):
        raise ValueError("Existing transcript is not valid JSON; preserve it and use a separate edit directory") from None
    if not isinstance(payload, dict) or payload.get("_video_use") != identity or not isinstance(payload.get("words"), list):
        raise ValueError("Existing transcript does not match these source bytes and settings; preserve it and use a separate edit directory")
    return out_path


def extract_audio(video_path: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    if model not in MODELS:
        raise ValueError("Unsupported Scribe model")
    data: dict[str, str] = {
        "model_id": model,
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned HTTP {resp.status_code}")

    payload = resp.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("words"), list):
        raise ValueError("Scribe did not return a word-level transcript")
    return payload


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
    model: str = DEFAULT_MODEL,
) -> Path:
    """Transcribe a single video. Returns path to transcript JSON.

    An unchanged source/settings pair is reused without another API request.
    """
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"

    cached = cached_transcript(video, edit_dir, language, num_speakers, model)
    if cached is not None:
        if verbose:
            print(f"cached: {out_path.name}")
        return out_path

    identity = source_identity(video, language, num_speakers, model)

    if verbose:
        print(f"  extracting audio from {video.name}", flush=True)

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / f"{video.stem}.wav"
        extract_audio(video, audio)
        size_mb = audio.stat().st_size / (1024 * 1024)
        if verbose:
            print(f"  uploading {video.stem}.wav ({size_mb:.1f} MB)", flush=True)
        payload = call_scribe(audio, api_key, language, num_speakers, model)

    if source_identity(video, language, num_speakers, model) != identity:
        raise ValueError("Source changed during transcription; no transcript was installed")
    payload["_video_use"] = identity
    # Modal volumes do not support hard links. Exclusive creation works there
    # and protects a transcript installed by another process during the upload.
    # A concurrent reader fails closed until this complete JSON has been written.
    encoded = json.dumps(payload, indent=2) + "\n"
    with out_path.open("x") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path.name} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a video with ElevenLabs Scribe")
    ap.add_argument("video", type=Path, help="Path to video file")
    ap.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL,
                    help="Scribe model (default: scribe_v2; v1 only for explicit legacy use)")
    ap.add_argument(
        "--edit-dir",
        type=Path,
        default=None,
        help="Edit output directory (default: <video_parent>/edit)",
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code (e.g., 'en'). Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers when known. Improves diarization accuracy.",
    )
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    api_key = load_api_key()

    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        api_key=api_key,
        language=args.language,
        num_speakers=args.num_speakers,
        model=args.model,
    )


if __name__ == "__main__":
    main()
