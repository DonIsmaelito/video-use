"""Public voice choices, safe fallback and voice-aware speech cache behavior."""

import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from video_use_mcp.pilot.runtime import Manager
from video_use_mcp.pilot.voices import narration_voices, resolve_voice


def fixture():
    cfg = SimpleNamespace(speech_key="test-secret", voice="default-voice")
    store = Mock()
    store.get.return_value = None
    return store, cfg


def test_voice_discovery_is_optional_and_does_not_probe_on_normal_capability_call():
    store, cfg = fixture()
    with patch("video_use_mcp.pilot.voices.httpx.Client") as client:
        value = narration_voices(store, cfg)
        assert value["voices"] == [
            {"id": "default-voice", "name": "Host default", "default": True}
        ]
        assert resolve_voice(store, cfg, "") == "default-voice"
        client.assert_not_called()
        store.get.assert_not_called()


def test_catalog_requests_public_voices_and_filters_unexpected_private_entries():
    store, cfg = fixture()
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.elevenlabs.io/v2/voices"),
        json={
            "voices": [
                {
                    "voice_id": "public-voice",
                    "name": "Public narrator",
                    "category": "premade",
                    "labels": {"accent": "british"},
                },
                {
                    "voice_id": "private-voice",
                    "name": "Private clone",
                    "category": "cloned",
                },
            ]
        },
    )
    with patch("video_use_mcp.pilot.voices.httpx.Client") as client:
        client.return_value.__enter__.return_value.get.return_value = response
        value = narration_voices(store, cfg, discover=True)
        args = client.return_value.__enter__.return_value.get.call_args
    assert args.kwargs["params"]["voice_type"] == "default"
    assert args.kwargs["headers"] == {"xi-api-key": cfg.speech_key}
    assert "Authorization" not in args.kwargs["headers"]
    assert [v["id"] for v in value["voices"]] == ["default-voice", "public-voice"]
    assert "Private clone" not in json.dumps(value)
    store.put.assert_called_once()


def test_cached_catalog_supports_only_listed_choices():
    store, cfg = fixture()
    store.get.return_value = [{"id": "public-voice", "name": "Public narrator"}]
    with patch("video_use_mcp.pilot.voices.httpx.Client") as client:
        assert resolve_voice(store, cfg, "public-voice") == "public-voice"
        with pytest.raises(ValueError, match="not available"):
            resolve_voice(store, cfg, "unlisted-private-voice")
        client.assert_not_called()


def test_provider_error_returns_safe_default_and_never_leaks_provider_response():
    store, cfg = fixture()
    with patch("video_use_mcp.pilot.voices.httpx.Client") as client:
        client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
            "contains test-secret"
        )
        value = narration_voices(store, cfg, discover=True)
    assert value["discovery"] == "unavailable"
    assert value["voices"][0]["id"] == cfg.voice
    assert cfg.speech_key not in json.dumps(value)


def test_narration_metadata_returns_bounded_word_timings_with_explicit_coverage():
    store, cfg = fixture()
    manager = Manager(store, cfg)
    sb = Mock()
    sb.safe_path = AsyncMock(return_value="/workspace/audio/test.mp3")
    sb.run = AsyncMock(
        return_value={"exit_code": 0, "stdout": '{"format":{"duration":600}}'}
    )
    words = [{"text": "word", "start": i, "end": i + 0.5} for i in range(501)]
    result = asyncio.run(
        manager.narration_metadata(sb, "audio/test.mp3", json.dumps({"words": words}))
    )
    assert result["word_timings"] == words[:500]
    assert result["word_timings_truncated"]
    assert result["word_count"] == 501
    assert result["timing_path"] == "audio/test.mp3.json"


@pytest.mark.parametrize("voice", ["default-voice", "public-voice"])
def test_selected_voice_controls_provider_credentials_and_cache_key(tmp_path, voice):
    store, cfg = fixture()
    manager = Manager(store, cfg)
    manager.save_object = AsyncMock(return_value={"key": "stored-audio"})
    manager.narration_metadata = AsyncMock(return_value={"duration": 1})
    sb = Mock()
    sb.download = AsyncMock()
    sb.read = AsyncMock(return_value=b'{"words":[]}')
    captured = []

    async def narrate(self, text, output):
        captured.append(self.credentials["elevenlabs_voice"])
        return {}

    task = {
        "id": "task",
        "project": "project",
        "owner": "owner",
        "operation": "narrate",
        "payload": {"text": "Hello.", "output": "audio/test.mp3", "voice_id": voice},
    }
    with patch("video_use_mcp.pilot.runtime.ProductionAgent.narrate", narrate):
        result = asyncio.run(manager.perform(task, sb))
    assert captured == [voice]
    expected = "owner:" + hashlib.sha256((voice + "Hello.").encode()).hexdigest()
    assert any(c.args == ("narration", expected) for c in store.get.call_args_list)
    assert result["voice_id"] == voice
