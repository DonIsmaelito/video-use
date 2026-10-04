"""Real encoded speech-clock and legacy-cache compatibility checks; no API calls."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np
import pytest

from helpers import transcribe


pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                                reason="FFmpeg and FFprobe required")


def run(*args):
    result = subprocess.run(args, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def pulse_source(path, rate=48000, delay=0., origin=0., *, gap=False, extra_audio=False):
    # Two audible events; input timestamps are deliberately distinct from the
    # raw decoded sample index when delayed or when a middle block is omitted.
    expression = f"'0.6*sin(2*PI*1000*t)*(gte(t,.3)*lt(t,.4)+gte(t,.8)*lt(t,.9))':s={rate}:d=1.2"
    run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=s=160x90:r=30:d=1.5",
        "-itsoffset", str(delay), "-f", "lavfi", "-i", "aevalsrc=" + expression,
        "-map", "0:v", "-map", "1:a", *(["-map", "1:a"] if extra_audio else []),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        *(["-af", "aselect='not(between(t,0.45,0.65))'"] if gap else []),
        "-c:a", "pcm_s16le" if gap else "aac", "-b:a", "128k",
        "-output_ts_offset", str(origin), str(path))


def source_events(path):
    """Independent reference: place each decoded sample at its probed PTS.

    This never invokes aresample or the extraction filter under test.
    """
    data = json.loads(run("ffprobe", "-v", "error", "-select_streams", "a:0",
                          "-show_streams", "-show_frames", "-show_format", "-of", "json", str(path)))
    stream = data["streams"][0]
    rate, tb = int(stream["sample_rate"]), Fraction(stream["time_base"])
    origin = Fraction(data["format"]["start_time"])
    raw = np.frombuffer(run("ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                            "-ac", "1", "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"), dtype="<f4")
    times = np.concatenate([float(frame["best_effort_timestamp"] * tb - origin)
                            + np.arange(frame["nb_samples"]) / rate for frame in data["frames"]])
    assert len(times) == len(raw)
    energy = raw.astype(float) ** 2
    # An omitted gap shifts the second event's raw index, not its source PTS.
    boundary = round(rate * .5)
    result = []
    for section in (slice(0, boundary), slice(boundary, None)):
        weights = energy[section]
        assert weights.sum() > 1
        result.append(float(np.dot(times[section], weights) / weights.sum()))
    return result, data


def wav_events(path, expected):
    with wave.open(str(path)) as audio:
        assert audio.getframerate() == 16000
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(float) / 32768
    result = []
    for target in expected:
        low, high = round((target - .13) * 16000), round((target + .13) * 16000)
        energy = samples[max(0, low):high] ** 2
        assert energy.sum() > 1, "Speech event was shifted away from its source time"
        times = np.arange(max(0, low), max(0, low) + len(energy)) / 16000
        result.append(float(np.dot(times, energy) / energy.sum()))
    return result


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("delay", [-.08, 0., .2])
@pytest.mark.parametrize("origin", [0., 2.])
def test_asr_wav_keeps_two_real_aac_events_on_source_clock(tmp_path, rate, delay, origin):
    source, output = tmp_path / "source.mp4", tmp_path / "speech.wav"
    pulse_source(source, rate, delay, origin)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    expected, _ = source_events(source)
    transcribe.extract_audio(source, output)
    assert wav_events(output, expected) == pytest.approx(expected, abs=.001)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original


def install_v1(source, edit):
    identity = transcribe.source_identity(source, None, None, "scribe_v2")
    identity.pop("audio_extraction")
    identity["version"] = 1
    output = edit / "transcripts" / (source.stem + ".json")
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps({"text": "Test", "words": [{"text": "Test", "start": .3, "end": .4}],
                                 "_video_use": identity}))
    return output


@pytest.mark.parametrize("rate", [44100, 48000])
def test_zero_clock_v1_cache_is_reused_without_relabeling_or_network(tmp_path, monkeypatch, rate):
    source, edit = tmp_path / "source.mp4", tmp_path / "edit"
    pulse_source(source, rate)
    output = install_v1(source, edit)
    original = output.read_bytes()
    def forbidden(*_args, **_kwargs):
        pytest.fail("Compatible cache must not extract/upload audio again")
    monkeypatch.setattr(transcribe, "extract_audio", forbidden)
    monkeypatch.setattr(transcribe, "call_scribe", forbidden)
    assert transcribe.transcribe_one(source, edit, "", verbose=False) == output
    assert output.read_bytes() == original
    assert transcribe.legacy_audio_clock(source)["max_clock_error_seconds"] <= 1/16000


@pytest.mark.parametrize("rate", [44100, 48000])
def test_delayed_v1_cache_fails_closed_without_overwrite(tmp_path, monkeypatch, rate):
    source, edit = tmp_path / "source.mp4", tmp_path / "edit"
    pulse_source(source, rate, delay=.2)
    output = install_v1(source, edit)
    original = output.read_bytes()
    monkeypatch.setattr(transcribe, "call_scribe", lambda *_: pytest.fail("No automatic paid re-transcription"))
    with pytest.raises(ValueError, match="Legacy transcript audio clock"):
        transcribe.transcribe_one(source, edit, "", verbose=False)
    assert output.read_bytes() == original


def test_internal_gap_is_filled_and_v1_rejected_even_with_zero_start(tmp_path):
    source, output = tmp_path / "gap.mkv", tmp_path / "speech.wav"
    pulse_source(source, gap=True)
    expected, probe = source_events(source)
    assert float(probe["streams"][0]["start_time"]) == 0
    assert expected[1] == pytest.approx(.85, abs=.001)
    transcribe.extract_audio(source, output)
    assert wav_events(output, expected) == pytest.approx(expected, abs=.001)
    old = install_v1(source, tmp_path / "edit")
    original = old.read_bytes()
    with pytest.raises(ValueError, match="audio clock"):
        transcribe.cached_transcript(source, tmp_path / "edit")
    assert old.read_bytes() == original


def test_legacy_multiple_audio_stream_selection_is_not_guessed(tmp_path):
    source = tmp_path / "multiple.mp4"
    pulse_source(source, extra_audio=True)
    install_v1(source, tmp_path / "edit")
    with pytest.raises(ValueError, match="audio clock"):
        transcribe.cached_transcript(source, tmp_path / "edit")


def test_new_identity_declares_clock_policy_and_rejects_filter_tampering(tmp_path):
    source, edit = tmp_path / "source.mp4", tmp_path / "edit"
    source.write_bytes(b"identity-only fixture")
    identity = transcribe.source_identity(source, None, None, "scribe_v2")
    assert identity["version"] == 2
    assert identity["audio_extraction"]["filter"] == transcribe.AUDIO_FILTER
    identity["audio_extraction"]["filter"] = "asetpts=PTS-STARTPTS"
    output = edit / "transcripts/source.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps({"words": [], "_video_use": identity}))
    with pytest.raises(ValueError, match="source bytes and settings"):
        transcribe.cached_transcript(source, edit)
