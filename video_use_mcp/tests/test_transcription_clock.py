"""Hosted source-clock/cache contracts with real encoded audio and mocked ASR."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from helpers import transcribe
from tests.test_transcribe_clock import pulse_source, source_events, wav_events
from video_use_mcp.agent import ProductionAgent
from video_use_mcp.pilot.runtime import Manager


ROOT = Path(__file__).resolve().parents[2]


class LocalSandbox:
    """Run the actual worker commands in a disposable local project."""
    def __init__(self, root):
        self.root = root
        self.commands = []
        (root / "sources").mkdir()
        (root / "edit/transcripts").mkdir(parents=True)

    def local(self, path):
        value = Path(str(path).removeprefix("/workspace/"))
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("Invalid fixture path")
        return self.root / value

    async def safe_path(self, path):
        return "/workspace/" + str(self.local(path).relative_to(self.root))

    async def run(self, command, timeout=180):
        self.commands.append(command)
        actual = command.replace("/workspace", str(self.root)).replace("/opt/video-use", str(ROOT))
        if actual.startswith("python "):
            actual = shlex.quote(sys.executable) + actual[len("python"):]
        result = subprocess.run(
            ["bash", "-c", actual], capture_output=True, text=True, timeout=timeout,
            cwd=self.root, env=os.environ | {"PYTHONPATH": str(ROOT)},
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    async def read(self, path, max_bytes=8 * 1024 * 1024):
        value = self.local(path).read_bytes()
        assert len(value) <= max_bytes
        return value

    async def write(self, path, data):
        output = self.local(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)


@pytest.fixture
def sandbox(tmp_path):
    return LocalSandbox(tmp_path)


def agent(sandbox, *, elevenlabs=True):
    speech = object.__new__(ProductionAgent)
    speech.sandbox = sandbox
    speech.credentials = ({"provider": "elevenlabs", "elevenlabs_key": "dummy-provider-key"}
                          if elevenlabs else {"provider": "openai", "key": "dummy-openai-key"})
    return speech


def provider(monkeypatch, payload):
    calls = []
    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200, json=lambda: json.loads(json.dumps(payload)))
    monkeypatch.setattr("video_use_mcp.agent.httpx.AsyncClient", Client)
    return calls


def legacy_payload():
    return {"text": "Fixture", "words": [{"text": "Fixture", "start": .3, "end": .4, "type": "word"}]}


def source(sandbox, *, delay=0., gap=False, rate=48000, origin=0.):
    path = sandbox.root / ("sources/clip.mkv" if gap else "sources/clip.mp4")
    pulse_source(path, rate, delay, origin, gap=gap)
    return path, str(path.relative_to(sandbox.root)), hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("rate,delay,origin,gap,elevenlabs", [
    (44100,.2,0.,False,True), (48000,.2,2.,False,True),
    (48000,-.08,0.,False,True), (48000,0.,0.,True,True),
    (48000,.2,0.,False,False),
])
def test_hosted_provider_receives_actual_source_clock_wav(sandbox, monkeypatch, rate, delay, origin, gap, elevenlabs):
    path, relative, digest = source(sandbox, delay=delay, gap=gap, rate=rate, origin=origin)
    expected, _ = source_events(path)
    payload = legacy_payload()
    calls = provider(monkeypatch, payload)
    reserve = Mock()
    result = asyncio.run(agent(sandbox, elevenlabs=elevenlabs).transcribe(relative, before_provider=reserve))
    assert "Saved word-level transcript" in result["text"]
    reserve.assert_called_once_with()
    assert len(calls) == 1
    wav = sandbox.root / "uploaded.wav"
    wav.write_bytes(calls[0][1]["files"]["file"][1])
    assert wav_events(wav, expected) == pytest.approx(expected, abs=.001)
    saved = json.loads((sandbox.root / "edit/transcripts/clip.json").read_text())
    assert saved["words"] == payload["words"]
    assert saved["_video_use"]["source_sha256"] == digest
    assert saved["_video_use"]["audio_extraction"] == transcribe.AUDIO_EXTRACTION
    assert saved["_video_use"]["provider"] == ("elevenlabs" if elevenlabs else "openai")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert "dummy-provider-key" not in "\n".join(sandbox.commands)
    assert "dummy-openai-key" not in "\n".join(sandbox.commands)


def test_new_hosted_cache_reuses_bytes_without_provider_or_allowance(sandbox, monkeypatch):
    _, relative, _ = source(sandbox, delay=.2)
    calls = provider(monkeypatch, legacy_payload())
    speech = agent(sandbox)
    asyncio.run(speech.transcribe(relative))
    output = sandbox.root / "edit/transcripts/clip.json"
    original = output.read_bytes()
    reserve = Mock()
    result = asyncio.run(speech.transcribe(relative, before_provider=reserve))
    assert "Cached transcript" in result["text"]
    assert len(calls) == 1
    reserve.assert_not_called()
    assert output.read_bytes() == original


@pytest.mark.parametrize("delay,gap", [(0.,False),(.2,False),(0.,True)])
def test_source_bound_legacy_only_reuses_proved_aligned_clock(sandbox, monkeypatch, delay, gap):
    _, relative, digest = source(sandbox, delay=delay, gap=gap)
    output = sandbox.root / "edit/transcripts/clip.json"
    original = json.dumps(legacy_payload(), indent=3).encode()
    output.write_bytes(original)
    calls = provider(monkeypatch, legacy_payload())
    reserve = Mock()
    pending = agent(sandbox).transcribe(relative, legacy_source_sha256=digest, before_provider=reserve)
    if delay or gap:
        with pytest.raises(ValueError, match="Legacy transcript audio clock"):
            asyncio.run(pending)
    else:
        assert "Cached transcript" in asyncio.run(pending)["text"]
    assert not calls
    reserve.assert_not_called()
    assert output.read_bytes() == original


@pytest.mark.parametrize("case", ["unbound", "invalid_json", "wrong_settings", "changed_source", "symlink"])
def test_unverified_local_cache_is_preserved_and_never_uploaded(sandbox, monkeypatch, case):
    path, relative, _ = source(sandbox)
    calls = provider(monkeypatch, legacy_payload())
    speech = agent(sandbox)
    output = sandbox.root / "edit/transcripts/clip.json"
    if case in {"wrong_settings", "changed_source"}:
        asyncio.run(speech.transcribe(relative))
        calls.clear()
        if case == "wrong_settings":
            payload = json.loads(output.read_text())
            payload["_video_use"]["audio_extraction"]["filter"] = "asetpts=PTS-STARTPTS"
            output.write_text(json.dumps(payload))
        else:
            pulse_source(path, delay=.2)
    elif case == "invalid_json":
        output.write_bytes(b"{")
    elif case == "symlink":
        target = sandbox.root / "old.json"
        target.write_text(json.dumps(legacy_payload()))
        output.symlink_to(target)
    else:
        output.write_text(json.dumps(legacy_payload()))
    original = output.read_bytes()
    with pytest.raises(ValueError, match="Transcript cache"):
        asyncio.run(speech.transcribe(relative))
    assert not calls and output.read_bytes() == original


def pilot(sandbox, cache):
    store = Mock()
    store.get.side_effect = lambda kind, _key: cache if kind == "transcript" else None
    manager = Manager(store, SimpleNamespace(speech_key="dummy-provider-key", voice="fixture"))
    task = {"owner":"fixture-owner","project":"fixture-project","id":"fixture-task",
            "operation":"transcribe","payload":{"path":"sources/clip.mp4"}}
    return manager, store, task


@pytest.mark.parametrize("delay,gap", [(0.,False),(.2,False),(0.,True)])
def test_pilot_database_cache_cannot_bypass_legacy_clock_proof(sandbox, monkeypatch, delay, gap):
    _, relative, digest = source(sandbox, delay=delay, gap=gap)
    payload = legacy_payload()
    manager, store, task = pilot(sandbox, payload)
    task["payload"]["path"] = relative
    calls = provider(monkeypatch, payload)
    if delay or gap:
        with pytest.raises(ValueError, match="Legacy transcript audio clock"):
            asyncio.run(manager.perform(task, sandbox))
        assert not list((sandbox.root / "edit/transcripts").iterdir())
    else:
        result = asyncio.run(manager.perform(task, sandbox))
        assert result == {"path":"edit/transcripts/" + digest + ".json","cached":True}
        assert json.loads(sandbox.local(result["path"]).read_text()) == payload
    assert not calls
    store.reserve.assert_not_called()
    store.put.assert_not_called()


def test_pilot_fresh_transcript_persists_bound_clock_identity(sandbox, monkeypatch):
    path, _, digest = source(sandbox, delay=.2)
    expected, _ = source_events(path)
    manager, store, task = pilot(sandbox, None)
    calls = provider(monkeypatch, legacy_payload())
    result = asyncio.run(manager.perform(task, sandbox))
    assert "Saved word-level transcript" in result["text"]
    assert len(calls) == 1
    wav = sandbox.root / "pilot-uploaded.wav"
    wav.write_bytes(calls[0][1]["files"]["file"][1])
    assert wav_events(wav, expected) == pytest.approx(expected, abs=.001)
    store.reserve.assert_called_once_with("fixture-owner", "transcribe", 2, "fixture-task")
    kind, key, payload = store.put.call_args.args
    assert (kind,key) == ("transcript","fixture-owner:"+digest)
    assert payload["_video_use"]["source_sha256"] == digest
    assert payload["_video_use"]["audio_extraction"] == transcribe.AUDIO_EXTRACTION


def test_pilot_rejects_unsafe_restored_local_cache_before_reserving_speech(sandbox, monkeypatch):
    _, _, digest = source(sandbox, delay=.2)
    output = sandbox.root / ("edit/transcripts/"+digest+".json")
    original = json.dumps(legacy_payload(),indent=3).encode()
    output.write_bytes(original)
    manager, store, task = pilot(sandbox, None)
    calls = provider(monkeypatch, legacy_payload())
    with pytest.raises(ValueError, match="Legacy transcript audio clock"):
        asyncio.run(manager.perform(task, sandbox))
    assert not calls and output.read_bytes() == original
    store.reserve.assert_not_called()
    store.put.assert_not_called()
