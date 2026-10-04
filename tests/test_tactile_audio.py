"""Timeline safety and encoded PCM guarantees for original procedural accents."""

import json
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np
import pytest

from helpers.tactile_audio import synthesize, validate_timeline, write_pcm


def event(**extra):
    return {"kind": "tap", "start": .1, "duration": .2, "pan": 0, "gain": 1, **extra}


def timeline(**extra):
    return {"version": 1, "duration": .5, "sample_rate": 8000, "seed": 207,
            "headroom_db": 3, "events": [event()], **extra}


def test_pcm_has_exact_stereo_duration_and_silent_boundaries(tmp_path):
    spec = timeline(duration=.5000625, events=[event(start=0, duration=.2, pan=-1)])
    samples = synthesize(spec)
    assert samples.shape == (4001, 2)  # Half-sample timestamps round up.
    assert np.max(np.abs(samples[:, 0])) > 0
    assert not samples[:, 1].any()
    assert not samples[0].any() and not samples[1599:].any()
    path = tmp_path / "tactile.wav"
    report = write_pcm(path, samples, 8000)
    with wave.open(str(path), "rb") as stream:
        assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()) == (2, 2, 8000, 4001)
        assert len(stream.readframes(5000)) == 4001 * 4
    assert report["frames"] == 4001 and report["duration"] == 4001 / 8000


def test_seed_is_repeatable_and_pan_uses_equal_power():
    spec = timeline(events=[event(kind="slide")])
    first = synthesize(spec)
    assert np.array_equal(first, synthesize(spec))
    assert not np.array_equal(first, synthesize({**spec, "seed": 208}))
    left = synthesize(timeline(events=[event(kind="slide", pan=-1)]))
    right = synthesize(timeline(events=[event(kind="slide", pan=1)]))
    assert np.allclose(np.sum(first**2), np.sum(left**2))
    assert np.array_equal(left[:, 0], right[:, 1])
    assert not left[:, 1].any() and not right[:, 0].any()


def test_empty_event_list_stays_silent_and_minimal_events_fit():
    assert not synthesize(timeline(events=[])).any()
    output = synthesize(timeline(events=[event(start=.4995, duration=.0005, kind="slide")]))
    assert output.shape == (4000, 2) and np.all(np.isfinite(output))
    assert not output[-1].any()


@pytest.mark.parametrize("extra", [
    {"duration": 0}, {"duration": float("nan")}, {"duration": float("inf")}, {"duration": True},
    {"duration": 601}, {"duration": 600, "sample_rate": 96000},
    {"sample_rate": 0}, {"sample_rate": 48000.0}, {"sample_rate": True},
    {"seed": -1}, {"seed": 2**64}, {"seed": True},
    {"headroom_db": -1}, {"headroom_db": float("nan")}, {"version": True},
    {"events": None}, {"events": [{}] * 2049}, {"typo": 1},
])
def test_invalid_timeline_is_rejected(extra):
    with pytest.raises(ValueError):
        validate_timeline(timeline(**extra))


@pytest.mark.parametrize("extra", [
    {"start": -.1}, {"start": float("nan")}, {"start": .4, "duration": .2},
    {"duration": 0}, {"duration": .0001}, {"duration": float("inf")},
    {"pan": -1.01}, {"pan": float("nan")}, {"gain": -1}, {"gain": 17},
    {"gain": True}, {"gain": float("inf")}, {"kind": "recorded-wood"}, {"typo": 1},
])
def test_invalid_events_are_rejected_without_truncation(extra):
    with pytest.raises(ValueError):
        synthesize(timeline(events=[event(**extra)]))


def test_overlapping_sound_is_summed_and_clipping_is_rejected(tmp_path):
    # Quiet overlap is retained, not normalized. Excessive coherent tap overlap
    # must fail before PCM conversion, which would otherwise wrap/clamp samples.
    one = synthesize(timeline(events=[event(gain=0)]))
    assert not one.any()
    quiet = synthesize(timeline(events=[event(gain=.2), event(gain=.2)]))
    louder = synthesize(timeline(events=[event(gain=.4), event(gain=.4)]))
    assert np.allclose(louder, quiet * 2)
    with pytest.raises(ValueError, match="headroom limit"):
        synthesize(timeline(events=[event(gain=16)] * 12))
    with pytest.raises(ValueError, match="headroom limit"):
        synthesize(timeline(headroom_db=24, events=[event(gain=2)]))
    destination = tmp_path / "existing.wav"
    destination.write_bytes(b"preserve previous artifact")
    with pytest.raises(ValueError, match="headroom limit"):
        write_pcm(destination, np.ones((20, 2)), 8000)
    assert destination.read_bytes() == b"preserve previous artifact"
    for bad in (np.zeros(20), np.zeros((20, 1)), np.full((20, 2), np.nan), np.ones((20, 2), dtype=np.int16)):
        with pytest.raises(ValueError):
            write_pcm(destination, bad, 8000)


def test_cli_renders_from_manifest_and_protects_input(tmp_path):
    source, output = tmp_path / "events.json", tmp_path / "audio.wav"
    source.write_text(json.dumps(timeline()))
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "helpers/tactile_audio.py"), str(source), "-o"]
    result = subprocess.run([*command, str(output)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["frames"] == 4000
    original = source.read_bytes()
    failed = subprocess.run([*command, str(source)], capture_output=True, text=True)
    assert failed.returncode != 0 and source.read_bytes() == original
