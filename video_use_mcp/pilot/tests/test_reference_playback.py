"""Source players use owned, observed URLs without copying reference media."""

import asyncio
from copy import deepcopy
import hashlib
from unittest.mock import Mock

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
import pytest

from video_use_mcp.pilot.reference_direction import Reference
from video_use_mcp.pilot.reference_playback import (
    FRAME_ORIGINS, MEDIA_ORIGINS, REFERENCE_UI_URI, observed_playback,
    reference_player, register_reference_playback,
)
from video_use_mcp.store import Store


UID, PID = "owner", "project"
PAGE = "https://www.ordinaryfolk.co/work/example-film"
COLLECTION = "https://www.ordinaryfolk.co/work"
MEDIA = "https://media.ordinary.co/video/home/example.webm"
YOUTUBE = "https://www.youtube.com/watch?v=abcdefghijk"
VIMEO = "https://player.vimeo.com/video/123456789?h=abc123def4&autoplay=1"


def reference(**updates):
    return {
        "id": "source-film", "title": "Source film", "url": PAGE,
        "discovery_url": COLLECTION, "observed_traits": "Clear shape motion",
        "inspection": "video", "source_id": "ordinary_folk",
        "playback": {"url": MEDIA, "browser_request_id": "inspect-source"},
    } | updates


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path)
    store.project = Mock(return_value={"title": "Project"})
    store.reserve = Mock(side_effect=AssertionError("No source playback compute or storage spend"))
    store.upload = Mock(side_effect=AssertionError("No source media upload"))
    store.download = Mock(side_effect=AssertionError("No source media download"))
    return store


def save_reference(store, ref):
    store.put("creative", PID, {"revision": 7, "intake": {"reference_direction": {
        "version": 1, "status": "offered", "rounds": [{"id": "round", "references": [ref]}],
    }}})


def save_receipt(store, *, page=PAGE, media=MEDIA, kind="videos", owner=UID,
                 project=PID, status="complete", engine="browser-harness", duration=5):
    field = "url" if kind == "links" else "src"
    item = {field: media}
    if kind == "videos":
        item["duration_seconds"] = duration
    receipt = {"owner": owner, "project": project, "status": status, "result": {
        "engine": engine, "project_id": project,
        "results": [{"action": "read", "ok": True, "page_url": page, kind: [item]}],
    }}
    key = hashlib.sha256((UID + ":" + PID + ":inspect-source").encode()).hexdigest()
    store.put("reference_browser_run", key, receipt)
    return key


def test_direct_source_clip_plays_without_copy_or_project_mutation(store):
    save_reference(store, reference())
    save_receipt(store)
    before = deepcopy(store.get("creative", PID))
    result = reference_player(store, UID, PID, "source-film")
    assert result["playback_status"] == "available"
    assert result["media"]["url"] == MEDIA
    assert result["media"]["media_type"] == "video/webm"
    assert result["media"]["caption"] == "Source clip"
    assert result["coverage"] == "source_preview" and result["duration_seconds"] == 5
    assert result["follow_project"] is False
    assert result["source_link"]["url"] == PAGE
    assert "complete reference film" in result["coverage_note"]
    assert not {"object_id", "download_url"}.intersection(result["media"])
    assert store.get("creative", PID) == before
    store.reserve.assert_not_called()
    store.upload.assert_not_called()
    store.download.assert_not_called()


def test_project_ownership_is_checked_before_loading_playback(store):
    store.project.side_effect = PermissionError("Project not found")
    store.get = Mock(side_effect=AssertionError("Private metadata read before ownership"))
    with pytest.raises(PermissionError):
        reference_player(store, "other-owner", PID, "source-film")
    store.get.assert_not_called()


@pytest.mark.parametrize("values", [
    {"owner": "other-owner"}, {"project": "other-project"},
    {"status": "failed"}, {"engine": "assistant-reported"},
    {"page": "https://www.ordinaryfolk.co/work/unrelated-film"},
    {"media": "https://media.ordinary.co/video/home/unrelated.webm"},
])
def test_unowned_or_unobserved_playback_returns_source_link(store, values):
    save_reference(store, reference())
    save_receipt(store, **values)
    result = reference_player(store, UID, PID, "source-film")
    assert result["playback_status"] == "source_link"
    assert result["media"]["media_type"] == "source_link"
    assert "url" not in result["media"] and "embed_url" not in result["media"]
    assert result["source_link"]["url"] == PAGE
    assert result["fallback_reason"]


def test_unrelated_collection_hero_cannot_be_attributed_to_candidate(store):
    ref = reference()
    save_reference(store, ref)
    save_receipt(store, page=COLLECTION)
    with pytest.raises(ValueError, match="cited reference"):
        observed_playback(store, UID, PID, ref)
    assert reference_player(store, UID, PID, ref["id"])["playback_status"] == "source_link"


def test_collection_provider_link_attests_only_the_same_cited_video(store):
    ref = reference(url=YOUTUBE, playback={"url": YOUTUBE, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, page=COLLECTION, media=YOUTUBE, kind="links")
    result = reference_player(store, UID, PID, ref["id"])
    assert result["playback_status"] == "available" and result["coverage"] == "source_video"
    assert result["media"]["embed_url"] == "https://www.youtube-nocookie.com/embed/abcdefghijk"
    ref["url"] = "https://www.youtube.com/watch?v=ABCDEFGHIJK"
    save_reference(store, ref)
    assert reference_player(store, UID, PID, ref["id"])["playback_status"] == "source_link"


def test_exact_cited_direct_video_can_be_observed_on_discovery_page(store):
    ref = reference(url=MEDIA)
    save_reference(store, ref)
    save_receipt(store, page=COLLECTION, duration=90)
    result = reference_player(store, UID, PID, ref["id"])
    assert result["playback_status"] == "available" and result["coverage"] == "source_video"
    assert result["source_page_url"] == COLLECTION


def test_publicly_observed_vimeo_embed_retains_exact_unlisted_hash(store):
    ref = reference(playback={"url": VIMEO, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, media=VIMEO, kind="embedded_players")
    result = reference_player(store, UID, PID, ref["id"])
    assert result["media"]["embed_url"] == "https://player.vimeo.com/video/123456789?h=abc123def4"
    assert result["coverage"] == "source_preview"
    assert "autoplay" not in result["media"]["embed_url"]


@pytest.mark.parametrize("url,kind", [
    ("https://private-cdn.example/video.mp4", "videos"),
    ("https://media.ordinary.co/video/live.m3u8", "videos"),
    ("https://player.vimeo.com.evil.example/video/123456789", "embedded_players"),
    ("https://www.youtube.com/embed/abcdefghijk/extra", "embedded_players"),
    ("https://player.vimeo.com/video/123456789?h=not-a-safe-hash", "embedded_players"),
    ("https://player.vimeo.com/video/123456789?h=abcdef&h=123456", "embedded_players"),
    ("https://example.com/embed/custom-player", "embedded_players"),
])
def test_unsupported_players_keep_clickable_fallback_instead_of_arbitrary_iframe(store, url, kind):
    ref = reference(playback={"url": url, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, media=url, kind=kind)
    result = reference_player(store, UID, PID, ref["id"])
    assert result["playback_status"] == "source_link"
    assert result["source_link"] == {"url": PAGE, "title": "Source film"}
    assert result["fallback_reason"]
    assert "embed_url" not in result["media"]


def test_reference_without_playback_falls_back_and_stale_ids_cannot_play(store):
    ref = reference()
    ref.pop("playback")
    save_reference(store, ref)
    assert reference_player(store, UID, PID, ref["id"])["playback_status"] == "source_link"
    with pytest.raises(ValueError, match="current offered"):
        reference_player(store, UID, PID, "old-round-id")


def test_old_descriptor_cannot_show_a_different_film_with_reused_reference_id(store):
    save_reference(store, reference())
    state = store.get("creative", PID)
    state["intake"]["reference_direction"]["rounds"].append({
        "id": "replacement-round", "references": [reference(title="Different film", url="https://artist.example/different")],
    })
    store.put("creative", PID, state)
    with pytest.raises(ValueError, match="offer changed"):
        reference_player(store, UID, PID, "source-film", round_id="round")
    current = reference_player(store, UID, PID, "source-film", round_id="replacement-round")
    assert current["source_link"]["title"] == "Different film"
    assert current["round_id"] == "replacement-round"


def test_optional_playback_preserves_older_reference_serialization():
    ref = reference()
    ref.pop("playback")
    assert "playback" not in Reference.model_validate(ref).model_dump()
    parsed = Reference.model_validate(reference())
    assert parsed.model_dump()["playback"] == reference()["playback"]


@pytest.mark.parametrize("url", ["http://example.com/a.mp4", "https://127.0.0.1/a.mp4", "javascript:alert(1)"])
def test_reference_model_rejects_private_or_executable_playback(url):
    with pytest.raises(ValueError):
        Reference.model_validate(reference(playback={"url": url, "browser_request_id": "inspect-source"}))


def test_reference_tool_has_its_own_restricted_media_resource(store):
    mcp = FastMCP("reference-test")
    register_reference_playback(mcp, store, lambda: UID, ToolAnnotations(readOnlyHint=True))
    tools = asyncio.run(mcp.list_tools())
    tool = next(item.model_dump(by_alias=True) for item in tools if item.name == "show_video_reference")
    assert tool["_meta"]["ui"]["resourceUri"] == REFERENCE_UI_URI
    assert set(tool["inputSchema"]["properties"]) == {"project_id", "reference_id", "round_id"}
    resources = asyncio.run(mcp.list_resources())
    resource = next(item.model_dump(by_alias=True) for item in resources if str(item.uri) == REFERENCE_UI_URI)
    csp = resource["_meta"]["ui"]["csp"]
    assert csp["resourceDomains"] == list(MEDIA_ORIGINS)
    assert csp["frameDomains"] == list(FRAME_ORIGINS)
    assert csp["connectDomains"] == []
    assert not any("*" in value for values in csp.values() for value in values)
