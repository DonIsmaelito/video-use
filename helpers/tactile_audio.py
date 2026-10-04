"""Synthesize original tap/slide accents from an explicit event timeline.

These are procedural sounds, not recorded Foley or physical material simulation.
No samples, models, services or automatic loudness normalization are used.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import math
from pathlib import Path
import tempfile
import wave

import numpy as np

MAX_SAMPLES = 28_800_000
MAX_EVENTS = 2048
DOCUMENT_FIELDS = {"version", "duration", "sample_rate", "seed", "headroom_db", "events"}
EVENT_FIELDS = {"start", "duration", "pan", "kind", "gain"}


def bounded_number(value, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not minimum <= value <= maximum or not math.isfinite(value):
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return float(value)


def sample_index(seconds: float, rate: int) -> int:
    """Round an absolute nonnegative timestamp to its nearest PCM boundary."""
    return int((Decimal(str(seconds)) * rate).to_integral_value(rounding=ROUND_HALF_UP))


def validate_timeline(value: dict) -> dict:
    """Validate all events before allocating audio or touching an output file."""
    if not isinstance(value, dict) or set(value) - DOCUMENT_FIELDS:
        raise ValueError("Timeline must be an object containing only documented fields")
    if type(value.get("version", 1)) is not int or value.get("version", 1) != 1:
        raise ValueError("Only timeline version 1 is supported")
    rate = value.get("sample_rate", 48000)
    if type(rate) is not int or not 8000 <= rate <= 96000:
        raise ValueError("sample_rate must be an integer between 8000 and 96000")
    duration = bounded_number(value.get("duration"), "duration", 0, 600)
    count = sample_index(duration, rate)
    if not 4 <= count <= MAX_SAMPLES:
        raise ValueError(f"duration must produce between 4 and {MAX_SAMPLES} samples")
    seed = value.get("seed", 0)
    if type(seed) is not int or not 0 <= seed <= 2**64 - 1:
        raise ValueError("seed must be an integer between 0 and 2**64 - 1")
    headroom = bounded_number(value.get("headroom_db", 3), "headroom_db", 0, 24)
    events = value.get("events")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError(f"events must be an explicit list with at most {MAX_EVENTS} events")
    normalized, work = [], 0
    for index, event in enumerate(events):
        label = f"events[{index}]"
        if not isinstance(event, dict) or set(event) - EVENT_FIELDS:
            raise ValueError(f"{label} must contain only documented event fields")
        kind = event.get("kind")
        if kind not in ("tap", "slide"):
            raise ValueError(f"{label}.kind must be tap or slide")
        start = bounded_number(event.get("start"), label + ".start", 0, duration)
        length = bounded_number(event.get("duration"), label + ".duration", 0, duration)
        stop = start + length
        if stop > duration and not math.isclose(stop, duration, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"{label} extends beyond the timeline; events are never truncated")
        begin, end = sample_index(start, rate), sample_index(stop, rate)
        if end > count or end - begin < 4:
            raise ValueError(f"{label} must fit entirely in the timeline and span at least 4 samples")
        pan = bounded_number(event.get("pan", 0), label + ".pan", -1, 1)
        gain = bounded_number(event.get("gain", 1), label + ".gain", 0, 16)
        normalized.append({"kind": kind, "begin": begin, "end": end, "pan": pan, "gain": gain})
        work += end - begin
    if work > MAX_SAMPLES * 4:
        raise ValueError("Total event sample work exceeds the bounded synthesis budget")
    return {"duration": duration, "sample_rate": rate, "samples": count,
            "seed": seed, "headroom_db": headroom, "events": normalized}


def check_headroom(samples: np.ndarray, headroom_db: float) -> float:
    """Reject unsafe sums instead of silently clipping or changing their gain."""
    headroom = bounded_number(headroom_db, "headroom_db", 0, 24)
    if samples.ndim != 2 or samples.shape[1] != 2 or not 1 <= len(samples) <= MAX_SAMPLES:
        raise ValueError("Audio must be a nonempty bounded stereo array")
    if not np.issubdtype(samples.dtype, np.floating) or not np.all(np.isfinite(samples)):
        raise ValueError("Audio must contain only finite floating point samples")
    peak = float(np.max(np.abs(samples)))
    limit = 10 ** (-headroom / 20)
    if peak > limit:
        measured = 20 * math.log10(peak)
        raise ValueError(f"Mix peak {measured:.2f} dBFS exceeds {-headroom:.2f} dBFS headroom limit; lower event gains or overlap")
    return peak


def synthesize(timeline: dict) -> np.ndarray:
    """Return exact-length stereo float64 PCM; manifest order and seed are stable."""
    spec = validate_timeline(timeline)
    rate = spec["sample_rate"]
    result = np.zeros((spec["samples"], 2), dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(spec["seed"]))
    for event in spec["events"]:
        count = event["end"] - event["begin"]
        time = np.arange(count, dtype=np.float64) / rate
        noise = rng.normal(size=count)
        kernel = min(count, max(3, round(35 * rate / 48000)) | 1)
        noise = np.convolve(noise, np.ones(kernel) / kernel, mode="same")
        if event["kind"] == "slide":
            sound = noise * .075 * np.sin(np.linspace(0, np.pi, count)) ** 2
        else:
            sound = (.105 * np.sin(2 * np.pi * 185 * time) * np.exp(-22 * time)
                     + .045 * np.sin(2 * np.pi * 390 * time) * np.exp(-30 * time)
                     + noise * .13 * np.exp(-38 * time))
            tail = (count - 1 - np.arange(count)) / rate
            sound *= np.minimum(time / .004, 1) * np.minimum(tail / .03, 1)
        sound *= event["gain"]
        sound[0] = sound[-1] = 0  # Exact silence at both event boundaries.
        section = result[event["begin"]:event["end"]]
        section[:, 0] += sound * math.sqrt((1 - event["pan"]) / 2)
        section[:, 1] += sound * math.sqrt((1 + event["pan"]) / 2)
    check_headroom(result, spec["headroom_db"])
    return result


def write_pcm(path: Path, samples: np.ndarray, sample_rate: int, *, headroom_db: float = 3) -> dict:
    """Atomically write little-endian stereo PCM16 after checking the full sum."""
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 96000:
        raise ValueError("sample_rate must be an integer between 8000 and 96000")
    peak = check_headroom(samples, headroom_db)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".tactile-", suffix=".wav", delete=False) as handle:
            temporary = Path(handle.name)
        with wave.open(str(temporary), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(sample_rate)
            stream.writeframes(np.rint(samples * 32767).astype("<i2").tobytes())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"sample_rate": sample_rate, "channels": 2, "sample_width": 2, "frames": len(samples),
            "duration": len(samples) / sample_rate, "peak": peak,
            "peak_dbfs": 20 * math.log10(peak) if peak else None,
            "headroom_db": headroom_db, "method": "Original procedural tap/slide synthesis; not recorded Foley"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path, help="Version 1 JSON event timeline")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Stereo PCM16 WAV")
    args = parser.parse_args(argv)
    if args.timeline.resolve() == args.output.resolve():
        parser.error("Output must not overwrite the event timeline")
    try:
        timeline = json.loads(args.timeline.read_text())
        spec = validate_timeline(timeline)
        report = write_pcm(args.output, synthesize(timeline), spec["sample_rate"], headroom_db=spec["headroom_db"])
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    report.update({"seed": spec["seed"], "events": len(spec["events"]), "numpy_version": np.__version__})
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
