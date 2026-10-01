"""Bounded public voice discovery; never expose the host's private voice library."""

import hashlib
import re

import httpx


def narration_voices(store, config, *, discover=False):
    default_id = getattr(config, "voice", "")
    speech_key = getattr(config, "speech_key", "")
    default = {"id": default_id, "name": "Host default", "default": True}
    result = {
        "available": bool(speech_key),
        "default_voice_id": default_id,
        "voices": [default] if speech_key else [],
        "discovery": "not_requested",
    }
    if not speech_key or not discover:
        return result
    key = hashlib.sha256(config.speech_key.encode()).hexdigest()
    cached = store.get("public_voices", key)
    if cached is None:
        try:
            # A separate client prevents forwarding the InsForge bearer header.
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                response = client.get(
                    "https://api.elevenlabs.io/v2/voices",
                    headers={"xi-api-key": config.speech_key},
                    params={"voice_type": "default", "page_size": 20},
                )
                response.raise_for_status()
                if len(response.content) > 1000000:
                    raise ValueError("Voice catalog exceeds size limit")
                payload = response.json()
            cached = []
            for voice in payload.get("voices", [])[:100]:
                ident = voice.get("voice_id", "")
                # Check the category as well as the request filter. Clones and
                # other workspace voices must not become pilot-wide choices.
                if voice.get("category") not in {
                    "premade",
                    "default",
                } or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", ident):
                    continue
                labels = voice.get("labels") or {}
                cached.append(
                    {
                        "id": ident,
                        "name": str(voice.get("name") or "Voice")[:80],
                        "labels": {
                            k: str(labels[k])[:60]
                            for k in ("accent", "age", "gender", "use_case")
                            if k in labels
                        },
                    }
                )
                if len(cached) == 20:
                    break
            store.put("public_voices", key, cached, ttl=3600)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            # Do not propagate provider errors (which may contain credentials).
            return result | {
                "discovery": "unavailable",
                "notice": "Additional voices could not be listed; the configured default remains available.",
            }
    choices = [dict(v, default=v["id"] == config.voice) for v in cached]
    if not any(v["id"] == config.voice for v in choices):
        choices.insert(0, default)
    return result | {"voices": choices, "discovery": "available"}


def resolve_voice(store, config, voice_id):
    if not voice_id or voice_id == config.voice:
        return config.voice
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", voice_id):
        raise ValueError(
            "Choose a voice_id from video_use_capabilities(include_voices=true)"
        )
    choices = narration_voices(store, config, discover=True)
    if voice_id not in {v["id"] for v in choices["voices"]}:
        raise ValueError(
            "Voice is not available. Choose a listed voice_id or use the configured default."
        )
    return voice_id
