"""Source players use owned, observed URLs without copying reference media."""

import asyncio
from copy import deepcopy
import hashlib
from unittest.mock import AsyncMock, Mock

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
import pytest

from video_use_mcp.pilot.reference_direction import Reference
from video_use_mcp.pilot.reference_playback import (
    FRAME_ORIGINS, MEDIA_ORIGINS, SOCIAL_RESOURCE_ORIGINS, SOCIAL_CONNECT_ORIGINS, REFERENCE_UI_URI, observed_playback,
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
    assert csp["resourceDomains"] == list(MEDIA_ORIGINS + SOCIAL_RESOURCE_ORIGINS)
    assert csp["frameDomains"] == list(FRAME_ORIGINS)
    assert csp["connectDomains"] == list(SOCIAL_CONNECT_ORIGINS)
    assert not any("*" in value for values in csp.values() for value in values)


@pytest.mark.parametrize("url,platform,post_id,expected", [
    ("https://www.youtube.com/watch?v=aqz-KE-bpKQ", "youtube", "aqz-KE-bpKQ", "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ"),
    ("https://www.tiktok.com/@scout2015/video/6718335390845095173", "tiktok", "6718335390845095173", "https://www.tiktok.com/player/v1/6718335390845095173"),
    ("https://x.com/Interior/status/463440424141459456", "x", "463440424141459456", None),
])
def test_official_social_receipt_creates_exact_provider_player_without_browser_copy(store, url, platform, post_id, expected):
    ref = reference(url=url, playback=None, social_receipt_id="social-receipt")
    save_reference(store, ref)
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "platform": platform, "post_id": post_id, "canonical_url": url,
        "post_verified": True, "title": "Actual creator title", "engagement": {"views": None},
    }})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["playback_status"] == "available"
    assert result["media"]["title"] == "Actual creator title"
    assert result["social"]["engagement"]["views"] is None
    if expected:
        assert result["media"]["media_type"] == "text/html"
        assert result["media"]["embed_url"] == expected
        assert result["media"]["provider"] == platform
    else:
        assert result["media"]["media_type"] == "social/x"
        assert result["media"]["post_id"] == post_id
        assert result["media"]["caption"] == "Source post"
        assert result["coverage"] == "source_post"
        assert "html" not in result["media"] and "script_url" not in result["media"]
    store.download.assert_not_called()
    store.upload.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"owner": "other"}, {"project": "other"},
    {"metadata": {"canonical_url": "https://youtu.be/ABCDEFGHIJK", "post_verified": True}},
    {"metadata": {"canonical_url": YOUTUBE, "post_verified": False}},
    {"metadata": {"canonical_url": YOUTUBE, "post_verified": True, "embeddable": False}},
])
def test_social_receipts_cannot_transplant_posts_or_claim_blocked_embeds(store, changes):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt")
    save_reference(store, ref)
    receipt = {"owner": UID, "project": PID, "metadata": {"canonical_url": YOUTUBE, "post_verified": True}}
    receipt.update(changes)
    store.put("social_reference", "social-receipt", receipt)
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["playback_status"] == "source_link"
    assert "embed_url" not in result["media"]
    assert result["fallback_reason"]


def test_browser_observed_tiktok_player_is_supported(store):
    post = "https://www.tiktok.com/@scout2015/video/6718335390845095173"
    player = "https://www.tiktok.com/player/v1/6718335390845095173?autoplay=0"
    save_reference(store, reference(url=post, playback={"url": player, "browser_request_id": "inspect-source"}))
    save_receipt(store, page=post, media=player, kind="embedded_players")
    result = reference_player(store, UID, PID, "source-film", "round")
    assert result["media"]["embed_url"] == player.split("?")[0]
    assert result["coverage"] == "source_video"


def test_each_player_keeps_its_exact_candidate_explanation_across_search_batches(store):
    refs = [reference(id=f"film-{index}", url=f"https://example.com/film-{index}", playback=None)
            for index in range(3)]
    batches = [{"candidates": [{"reference": ref, "fit": f"Fit for this brief {index}",
                                "disposition": "recommend"}]} for index, ref in enumerate(refs)]
    state = {"revision": 7, "intake": {"reference_direction": {
        "status": "collecting", "rounds": [{"id": "round", "references": refs, "search_batches": batches}],
    }}}
    store.put("creative", PID, state)
    for index, ref in enumerate(refs):
        result = reference_player(store, UID, PID, ref["id"], "round")
        assert result["media"]["description"] == f"Fit for this brief {index}"
        assert result["media"]["inspection"] == "video"
        assert result["media"]["evidence_status"] == "Video inspection reported by the assistant."
        assert "Describe THIS reference now" in result["next_action"]
        assert "continue sequential research" in result["next_action"]
        assert "Do not ask the reference-choice question yet" in result["next_action"]
    assert store.get("creative", PID) == state


@pytest.mark.parametrize("inspection,limitation", [
    ("metadata", "visuals and motion not inspected"),
    ("page", "video motion and sound not checked"),
    ("image", "video motion and sound not checked"),
])
def test_fallback_description_does_not_borrow_another_film_or_claim_visual_inspection(store, inspection, limitation):
    ref = reference(inspection=inspection, observed_traits="Reference details " * 60, playback=None)
    save_reference(store, ref)
    state = store.get("creative", PID)
    state["intake"]["reference_direction"]["rounds"][-1]["search_batches"] = [{"candidates": [
        {"reference": ref | {"id": "other"}, "fit": "Wrong ID", "disposition": "recommend"},
        {"reference": ref | {"url": "https://example.com/other"}, "fit": "Wrong URL", "disposition": "recommend"},
        {"reference": ref, "fit": "Rejected candidate", "disposition": "reject"},
    ]}]
    store.put("creative", PID, state)
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["description"].startswith("Reference details")
    assert len(result["media"]["description"]) <= 360
    assert limitation in result["media"]["evidence_status"]
    assert "native reference-choice question once" in result["next_action"]


def test_legacy_search_fit_remains_visible_and_accepted_reference_does_not_ask_again(store):
    ref = reference()
    save_reference(store, ref)
    state = store.get("creative", PID)
    direction = state["intake"]["reference_direction"]
    direction["status"] = "accepted"
    direction["rounds"][-1]["search"] = {"candidates": [
        {"reference": ref, "fit": "Fits the saved request", "disposition": "recommend"},
    ]}
    store.put("creative", PID, state)
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["description"] == "Fits the saved request"
    assert "do not ask an already answered" in result["next_action"]


def test_attribution_uses_verified_receipt_without_inventing_missing_counts(store):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", inspection="metadata", playback=None)
    ref["social"] = {"creator": {"name": "Untrusted copy"}, "engagement": {"likes": 999999}}
    save_reference(store, ref)
    metadata = {"canonical_url": YOUTUBE, "post_verified": True, "platform": "youtube",
                "creator": {"name": "Actual channel"}, "published_at": "2026-10-02T01:02:03Z",
                "engagement": {"views": {"value": 1200000, "display": "1.2M", "evidence": "1.2M views",
                                         "source": "visible_text"}, "likes": None}}
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": metadata})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["attribution"] == "Actual channel · Views: 1.2M · Published 2026-10-02"
    assert "Likes" not in result["media"]["attribution"]
    assert result["media"]["inspection"] == "metadata"
    assert "not inspected" in result["media"]["evidence_status"]


@pytest.mark.parametrize("observation,expected", [
    (None, "Actual channel"),
    ({"value": 3, "display": "3"}, "Actual channel"),
    ({"value": 3, "display": "3", "evidence": "3 views", "source": "assistant"}, "Actual channel"),
    ({"value": 0, "display": "0", "evidence": "0 views", "source": "youtube_api"}, "Actual channel · Views: 0"),
])
def test_only_observed_metrics_are_rendered_and_real_zero_is_not_missing(store, observation, expected):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", playback=None)
    save_reference(store, ref)
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": True, "creator": {"name": "Actual channel"},
        "engagement": {"views": observation},
    }})
    assert reference_player(store, UID, PID, ref["id"], "round")["media"]["attribution"] == expected


@pytest.mark.parametrize("seconds,label", [(119, "1:59"), (885, "14:45"), (3661, "1:01:01")])
def test_source_runtime_remains_visible_when_embedding_is_unavailable(store, seconds, label):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", playback=None)
    save_reference(store, ref)
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": True, "embeddable": False,
        "creator": {"name": "Actual uploader"}, "duration": {
            "seconds": seconds, "source": "json_ld", "evidence": "VideoObject.duration",
            "observed_at": "2026-10-03T21:00:00+00:00",
        },
    }})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["attribution"] == f"Actual uploader · Length {label}"
    assert result["media"]["duration_seconds"] == seconds
    assert "embed_url" not in result["media"]


@pytest.mark.parametrize("verified,source", [(False, "json_ld"), (True, "assistant"), (True, "html_video")])
def test_unverified_runtime_and_ad_player_duration_are_not_presented_as_source_length(store, verified, source):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", playback=None)
    save_reference(store, ref)
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": verified, "duration": {
            "seconds": 15, "source": source, "evidence": "Duration claim",
            "observed_at": "2026-10-03T21:00:00+00:00",
        },
    }})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert "Length" not in result["media"]["attribution"]
    assert "duration_seconds" not in result["media"]


def test_unknown_social_metadata_keeps_independently_observed_source_playback(store):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt",
                    playback={"url": YOUTUBE, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, page=YOUTUBE, media=YOUTUBE, kind="links")
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": False, "creator": {"name": "Not verified"},
    }})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["provider"] == "youtube"
    assert result["playback_status"] == "available"
    assert result["source_page_url"] == YOUTUBE
    assert result["media"]["attribution"] == ""
    assert result["media"]["poster_url"] == "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"


@pytest.mark.parametrize("observed_url,kind", [
    (YOUTUBE, "links"),
    ("https://www.youtube-nocookie.com/embed/abcdefghijk", "embedded_players"),
])
def test_exact_browser_youtube_evidence_supplies_poster_without_social_receipt(store, observed_url, kind):
    ref = reference(url=YOUTUBE, playback={"url": observed_url, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, page=YOUTUBE, media=observed_url, kind=kind)
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["playback_status"] == "available"
    assert result["media"]["source_url"] == YOUTUBE
    assert result["media"]["poster_url"] == "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"
    assert result["media"]["attribution"] == ""
    store.download.assert_not_called()
    store.upload.assert_not_called()


@pytest.mark.parametrize("page,observed_url,owner", [
    (YOUTUBE, YOUTUBE, "other"),
    ("https://www.youtube.com/watch?v=ABCDEFGHIJK", YOUTUBE, UID),
    (PAGE, "https://www.youtube.com/watch?v=ABCDEFGHIJK", UID),
])
def test_browser_poster_cannot_borrow_unowned_or_unrelated_evidence(store, page, observed_url, owner):
    ref = reference(url=YOUTUBE, playback={"url": observed_url, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, page=page, media=observed_url, kind="links", owner=owner)
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["playback_status"] == "source_link"
    assert "poster_url" not in result["media"]


@pytest.mark.parametrize("post_verified", [False, True])
def test_explicit_embed_denial_cannot_be_bypassed_with_browser_receipt(store, post_verified):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt",
                    playback={"url": YOUTUBE, "browser_request_id": "inspect-source"})
    save_reference(store, ref)
    save_receipt(store, page=YOUTUBE, media=YOUTUBE, kind="links")
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": post_verified, "embeddable": False,
    }})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["playback_status"] == "source_link"
    assert "does not permit embedding" in result["fallback_reason"]
    assert "embed_url" not in result["media"]


@pytest.mark.parametrize("embeddable", [None, True, False])
def test_older_verified_youtube_receipts_supply_visual_source_fallback(store, embeddable):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", playback=None)
    save_reference(store, ref)
    metadata = {"canonical_url": YOUTUBE, "post_verified": True}
    if embeddable is not None:
        metadata["embeddable"] = embeddable
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": metadata})
    before = deepcopy(store.get("social_reference", "social-receipt"))
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["poster_url"] == "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"
    assert result["media"]["provider"] == "youtube"
    assert result["media"]["source_url"] == YOUTUBE
    if embeddable is False:
        assert result["playback_status"] == "source_link"
        assert "embed_url" not in result["media"]
    else:
        assert result["playback_status"] == "available"
        assert result["media"]["embed_url"] == "https://www.youtube-nocookie.com/embed/abcdefghijk"
    assert store.get("social_reference", "social-receipt") == before
    store.download.assert_not_called()
    store.upload.assert_not_called()


@pytest.mark.parametrize("thumbnail,expected", [
    ("https://i.ytimg.com/vi/abcdefghijk/maxresdefault.jpg", "https://i.ytimg.com/vi/abcdefghijk/maxresdefault.jpg"),
    ("https://i.ytimg.com/vi/DIFFERENTID/hqdefault.jpg", "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"),
    ("https://images.example/other.jpg", "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"),
])
def test_saved_poster_is_revalidated_before_rendering(store, thumbnail, expected):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", playback=None)
    save_reference(store, ref)
    store.put("social_reference", "social-receipt", {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": True, "thumbnail_url": thumbnail,
    }})
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert result["media"]["poster_url"] == expected


@pytest.mark.parametrize("changes", [
    {"owner": "other"},
    {"project": "other"},
    {"metadata": {"canonical_url": "https://youtu.be/DIFFERENTID", "post_verified": True}},
    {"metadata": {"canonical_url": YOUTUBE, "post_verified": False}},
    {"metadata": {"canonical_url": YOUTUBE, "post_verified": True, "post_id": "../abcdefghijk"}},
    {"metadata": {"canonical_url": YOUTUBE, "post_verified": True, "post_id": "ABCDEFGHIJK"}},
    {"metadata": {"canonical_url": YOUTUBE, "post_verified": True, "platform": "tiktok"}},
])
def test_poster_requires_owned_verified_matching_youtube_identity(store, changes):
    ref = reference(url=YOUTUBE, social_receipt_id="social-receipt", playback=None)
    save_reference(store, ref)
    receipt = {"owner": UID, "project": PID, "metadata": {
        "canonical_url": YOUTUBE, "post_verified": True,
        "thumbnail_url": "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg",
    }}
    receipt.update(changes)
    store.put("social_reference", "social-receipt", receipt)
    result = reference_player(store, UID, PID, ref["id"], "round")
    assert "poster_url" not in result["media"]


def test_only_reference_image_csp_adds_exact_youtube_thumbnail_origin(store):
    mcp = FastMCP("reference-images-test")
    register_reference_playback(mcp, store, lambda: UID, ToolAnnotations(readOnlyHint=True))
    resource = next(item.model_dump(by_alias=True) for item in asyncio.run(mcp.list_resources())
                    if str(item.uri) == REFERENCE_UI_URI)
    csp = resource["_meta"]["ui"]["csp"]
    assert "https://i.ytimg.com" in csp["resourceDomains"]
    assert "https://i.ytimg.com" not in csp["frameDomains"]
    assert "https://i.ytimg.com" not in csp["connectDomains"]


def test_thumbnail_bytes_are_app_metadata_and_never_model_visible(store, monkeypatch):
    import video_use_mcp.pilot.reference_playback as playback
    from mcp.types import CallToolResult

    save_reference(store, reference(url=YOUTUBE, playback={"url": YOUTUBE, "browser_request_id": "inspect-source"}))
    save_receipt(store, page=YOUTUBE, media=YOUTUBE, kind="embedded_players")
    poster = {"source_url": "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg", "post_id": "abcdefghijk",
              "data_uri": "data:image/jpeg;base64,APP_ONLY_IMAGE_BYTES"}
    fetch = AsyncMock(return_value={"reference_poster": poster})
    monkeypatch.setattr(playback, "reference_poster_metadata", fetch)
    mcp = FastMCP("reference-inline-image-test")
    register_reference_playback(mcp, store, lambda: UID, ToolAnnotations(readOnlyHint=True))
    result = asyncio.run(mcp.call_tool("show_video_reference", {"project_id": PID, "reference_id": "source-film", "round_id": "round"}))
    assert isinstance(result, CallToolResult)
    assert result.meta == {"reference_poster": poster}
    assert "APP_ONLY_IMAGE_BYTES" not in str(result.structuredContent)
    assert "APP_ONLY_IMAGE_BYTES" not in str(result.content)
    assert result.structuredContent["media"]["embed_url"].endswith("/abcdefghijk")
    assert fetch.await_args.args[0]["poster_url"] == poster["source_url"]
