"""Original tonal beds and explicit soft pulses, not recorded location sound.

Deterministic PCM synthesis from a bounded JSON score. No samples, model,
normalization, compression or automatic harmony/rhythm generation is involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np

try:
    from .tactile_audio import bounded_number, check_headroom, sample_index, write_pcm
except ImportError:
    from tactile_audio import bounded_number, check_headroom, sample_index, write_pcm


MAX_SAMPLES = 11_520_000
MAX_WORK = MAX_SAMPLES * 8
FIELDS = {"version", "duration", "sample_rate", "seed", "headroom_db", "fade_in", "fade_out", "tones", "pulses"}
TONE_FIELDS = {"frequency", "gain", "pan"}
PULSE_FIELDS = TONE_FIELDS | {"start", "duration"}


def validate_score(value: dict) -> dict:
    """Validate the complete score before allocating PCM or creating output."""
    if not isinstance(value, dict) or set(value) - FIELDS:
        raise ValueError("Score must contain only documented fields")
    if type(value.get("version", 1)) is not int or value.get("version", 1) != 1:
        raise ValueError("Only score version 1 is supported")
    rate = value.get("sample_rate", 48000)
    if type(rate) is not int or not 8000 <= rate <= 96000:
        raise ValueError("sample_rate must be an integer from 8000 through 96000")
    duration = bounded_number(value.get("duration"), "duration", 0, 120)
    count = sample_index(duration, rate)
    if not 8 <= count <= MAX_SAMPLES:
        raise ValueError(f"Duration must span 8 through {MAX_SAMPLES} samples")
    seed = value.get("seed", 0)
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be an unsigned 64-bit integer")
    headroom = bounded_number(value.get("headroom_db", 3), "headroom_db", 0, 24)
    fades = [sample_index(bounded_number(value.get(key, min(.5, duration / 4)), key, 0, duration), rate)
             for key in ("fade_in", "fade_out")]
    if min(fades) < 2 or sum(fades) > count:
        raise ValueError("Fades must each span at least 2 samples and together fit the timeline")
    tones, pulses = value.get("tones", []), value.get("pulses", [])
    if not isinstance(tones, list) or len(tones) > 16 or not isinstance(pulses, list) or len(pulses) > 512:
        raise ValueError("Provide at most 16 tones and 512 pulses")
    if not tones and not pulses:
        raise ValueError("Score needs at least one explicitly authored tone or pulse")
    events, work = [], 0
    for kind, entries, fields in (("tone", tones, TONE_FIELDS), ("pulse", pulses, PULSE_FIELDS)):
        for index, entry in enumerate(entries):
            name = f"{kind}s[{index}]"
            if not isinstance(entry, dict) or set(entry) - fields:
                raise ValueError(f"{name} must contain only documented fields")
            frequency = bounded_number(entry.get("frequency"), name + ".frequency", 20, rate * .45)
            gain = bounded_number(entry.get("gain"), name + ".gain", 0, 1)
            pan = bounded_number(entry.get("pan", 0), name + ".pan", -1, 1)
            begin, end = 0, count
            if kind == "pulse":
                start = bounded_number(entry.get("start"), name + ".start", 0, duration)
                length = bounded_number(entry.get("duration"), name + ".duration", 0, duration)
                stop = start + length
                if stop > duration and not math.isclose(stop, duration, rel_tol=0, abs_tol=1e-12):
                    raise ValueError(f"{name} extends beyond the timeline; pulses are never truncated")
                begin, end = sample_index(start, rate), sample_index(stop, rate)
                if end > count or end - begin < 4:
                    raise ValueError(f"{name} must fit the timeline and span at least 4 samples")
            work += end - begin
            events.append({"kind": kind, "frequency": frequency, "gain": gain, "pan": pan, "begin": begin, "end": end})
    if work > MAX_WORK:
        raise ValueError("Total oscillator sample work exceeds the bounded synthesis budget")
    return {"sample_rate": rate, "samples": count, "seed": seed, "headroom_db": headroom,
            "fade_in": fades[0], "fade_out": fades[1], "events": events}


def synthesize(score: dict) -> np.ndarray:
    """Return stereo float64 PCM with exact rounded length and silent endpoints."""
    spec = validate_score(score)
    pcm = np.zeros((spec["samples"], 2), dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(spec["seed"]))
    for event in spec["events"]:
        count = event["end"] - event["begin"]
        time = np.arange(count, dtype=np.float64) / spec["sample_rate"]
        phase = rng.uniform(0, 2 * np.pi)
        sound = event["gain"] * np.sin(2 * np.pi * event["frequency"] * time + phase)
        if event["kind"] == "pulse":
            sound *= np.sin(np.linspace(0, np.pi, count)) ** 2
            sound[0] = sound[-1] = 0
        section = pcm[event["begin"]:event["end"]]
        section[:, 0] += sound * math.sqrt((1 - event["pan"]) / 2)
        section[:, 1] += sound * math.sqrt((1 + event["pan"]) / 2)
    pcm[:spec["fade_in"]] *= np.sin(np.linspace(0, np.pi / 2, spec["fade_in"]))[:, None] ** 2
    pcm[-spec["fade_out"]:] *= np.cos(np.linspace(0, np.pi / 2, spec["fade_out"]))[:, None] ** 2
    pcm[0] = pcm[-1] = 0
    check_headroom(pcm, spec["headroom_db"])
    return pcm


def _install_new(path: Path, complete: Path):
    """Reserve a new path exclusively; compatible with volumes without hard links."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    own = None
    try:
        own = os.fstat(descriptor)
        current = path.stat(follow_symlinks=False)
        if (own.st_dev, own.st_ino) != (current.st_dev, current.st_ino):
            raise FileExistsError("Output reservation changed")
        os.replace(complete, path)
    except BaseException:
        try:
            current = path.stat(follow_symlinks=False)
            if own is not None and (own.st_dev, own.st_ino) == (current.st_dev, current.st_ino):
                path.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(descriptor)


def render(score_path: Path, output: Path) -> dict:
    """Save a new PCM16 WAV plus a stdout-ready reproducibility report."""
    score_path, output = Path(score_path).resolve(), Path(output).absolute()
    if output.suffix.lower() != ".wav" or output.resolve() == score_path:
        raise ValueError("Output must be a new WAV separate from its JSON score")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output already exists; choose a new path")
    if score_path.stat().st_size > 1_048_576:
        raise ValueError("Score must be no larger than 1 MiB")
    original = score_path.read_bytes()
    if len(original) > 1_048_576:
        raise ValueError("Score must be no larger than 1 MiB")
    score = json.loads(original)
    spec = validate_score(score)
    pcm = synthesize(score)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ambient-audio-", dir=output.parent) as folder:
        temporary = Path(folder) / "complete.wav"
        report = write_pcm(temporary, pcm, spec["sample_rate"], headroom_db=spec["headroom_db"])
        if score_path.read_bytes() != original:
            raise ValueError("Score changed during synthesis")
        report.update({"schema": "video-use.ambient-audio.v1", "method": "Original sinusoidal bed and explicit soft pulses; not recorded location sound",
                       "source_sha256": hashlib.sha256(original).hexdigest(), "sha256": hashlib.sha256(temporary.read_bytes()).hexdigest(),
                       "file": output.name, "seed": spec["seed"], "numpy_version": np.__version__,
                       "tones": len(score.get("tones", [])), "pulses": len(score.get("pulses", []))})
        _install_new(output, temporary)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = render(args.score, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
