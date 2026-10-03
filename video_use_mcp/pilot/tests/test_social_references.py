"""Social attribution comes from official endpoints or owned exact-post evidence."""

import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from video_use_mcp.store import Store
from video_use_mcp.pilot.social_references import (
    _json,
    inspect_social_post,
    social_post,
    validated_duration,
    validate_social_receipt,
    youtube_thumbnail_url,
)

YT = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
TT = "https://www.tiktok.com/@scout2015/video/6718335390845095173"
X = "https://x.com/Interior/status/463440424141459456"


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path)
    value.project = Mock(return_value={"title": "Project"})
    value.config = SimpleNamespace(youtube_api_key="")
    return value


def inspect(store, url=YT, request_id="", handler=None):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                handler
                or (
                    lambda request: httpx.Response(
                        200,
                        json={
                            "type": "video",
                            "author_name": "Creator",
                            "title": "Example film",
                            "author_url": "https://www.youtube.com/@creator",
                            "html": "<script>never execute me</script>",
                        },
                    )
                )
            )
        ) as client:
            return await inspect_social_post(
                store, "owner", "project", url, request_id, client=client
            )

    return asyncio.run(run())


def browser_receipt(store, *, url=YT, owner="owner", project="project", metadata=None):
    post = social_post(url)
    social = {
        **post,
        "page_url": url,
        "post_verified": True,
        "observed_at": 1700000000,
        "title": "Visible title",
        "published_at": "2026-01-02T03:04:05Z",
        "metrics": {
            "views": {
                "value": 125000,
                "display": "125,000",
                "evidence": "125,000 views",
                "source": "visible_text",
            },
            "likes": {
                "value": None,
                "display": "1.2K",
                "evidence": "1.2K likes",
                "source": "visible_text",
            },
        },
    }
    social.update(metadata or {})
    receipt = {
        "owner": owner,
        "project": project,
        "status": "complete",
        "result": {
            "engine": "browser-harness",
            "project_id": project,
            "results": [{"ok": True, "page_url": url, "social_metadata": social}],
        },
    }
    key = hashlib.sha256(b"owner:project:read-post").hexdigest()
    store.put("reference_browser_run", key, receipt)
    return receipt


@pytest.mark.parametrize(
    "url,platform,post_id",
    [
        (YT + "&t=20", "youtube", "aqz-KE-bpKQ"),
        ("https://youtu.be/aqz-KE-bpKQ?si=tracking", "youtube", "aqz-KE-bpKQ"),
        ("https://www.youtube.com/shorts/aqz-KE-bpKQ", "youtube", "aqz-KE-bpKQ"),
        (TT + "?is_from_webapp=1", "tiktok", "6718335390845095173"),
        (X + "/video/1", "x", "463440424141459456"),
        (
            "https://twitter.com/Interior/status/463440424141459456",
            "x",
            "463440424141459456",
        ),
        ("https://x.com/i/web/status/463440424141459456", "x", "463440424141459456"),
    ],
)
def test_canonical_posts_strip_tracking(url, platform, post_id):
    post = social_post(url)
    assert post["platform"] == platform and post["post_id"] == post_id
    assert (
        "tracking" not in post["canonical_url"]
        and "is_from" not in post["canonical_url"]
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://www.youtube.com/watch?v=aqz-KE-bpKQ",
        "https://www.youtube.com.evil.example/watch?v=aqz-KE-bpKQ",
        "https://user@www.youtube.com/watch?v=aqz-KE-bpKQ",
        "https://www.youtube.com:444/watch?v=aqz-KE-bpKQ",
        "https://www.youtube.com/watch?v=aqz-KE-bpKQ&v=abcdefghijk",
        "https://youtube.com/@creator",
        "https://vm.tiktok.com/short",
        "https://www.tiktok.com/@creator",
        "https://x.com/search?q=film",
        "https://127.0.0.1/post",
        "javascript:alert(1)",
        "https://x.com/Interior/status/463440424141459456<script>",
    ],
)
def test_non_post_or_unsafe_urls_are_rejected(url):
    with pytest.raises(ValueError):
        social_post(url)


def test_oembed_attribution_does_not_invent_metrics_or_execute_html(store):
    result = inspect(store)
    assert result["post_verified"] is True and result["title"] == "Example film"
    assert result["engagement_status"] == "unavailable"
    assert result["engagement"] == dict(
        views=None, likes=None, comments=None, shares=None
    )
    assert result["observed_at"] and result["published_at"] is None
    assert "html" not in result and "never execute" not in str(result)
    assert any("not zero" in text for text in result["limitations"])
    assert any("not visual inspection" in text for text in result["limitations"])
    assert "owner" not in result and "project" not in result


@pytest.mark.parametrize("url", [
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/maxresdefault.jpg?provider=public",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/0.jpg",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault_live.jpg",
    "https://i.ytimg.com/vi_webp/aqz-KE-bpKQ/mqdefault.webp",
])
def test_official_youtube_thumbnail_is_retained_in_owned_receipt(store, url):
    result = inspect(store, handler=lambda request: httpx.Response(200, json={
        "type": "video", "author_name": "Creator", "title": "Example film", "thumbnail_url": url,
    }))
    assert result["thumbnail_url"] == url
    saved = validate_social_receipt(store, "owner", "project", result["social_receipt_id"], YT)
    assert saved["thumbnail_url"] == url
    assert result["post_verified"] is True


@pytest.mark.parametrize("url", [
    "http://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg",
    "https://i.ytimg.com.evil.example/vi/aqz-KE-bpKQ/hqdefault.jpg",
    "https://example.com/vi/aqz-KE-bpKQ/hqdefault.jpg",
    "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg",
    "https://user@i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg",
    "https://i.ytimg.com:444/vi/aqz-KE-bpKQ/hqdefault.jpg",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/../../another.jpg",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/custom.html",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg#wrong",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.webp",
    "https://i.ytimg.com/vi_webp/aqz-KE-bpKQ/hqdefault.jpg",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg\n",
    "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg\\other",
    None,
])
def test_untrusted_or_wrong_video_thumbnails_do_not_enter_metadata(store, url):
    result = inspect(store, handler=lambda request: httpx.Response(200, json={
        "type": "video", "author_name": "Creator", "title": "Example film", "thumbnail_url": url,
    }))
    assert result["post_verified"] is True
    assert result["thumbnail_url"] is None


@pytest.mark.parametrize("post_id", ["../aqz-KE-bpKQ", "aqz-KE-bpKQ/other", "aqz-KE-bpK", "", None])
def test_thumbnail_requires_a_valid_exact_youtube_id(post_id):
    assert youtube_thumbnail_url("https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg", post_id) is None


@pytest.mark.parametrize("url", [TT, X])
def test_other_platforms_do_not_adopt_youtube_thumbnail_urls(store, url):
    result = inspect(store, url, handler=lambda request: httpx.Response(200, json={
        "type": "video", "author_name": "Creator", "thumbnail_url": "https://i.ytimg.com/vi/aqz-KE-bpKQ/hqdefault.jpg",
    }))
    assert result["thumbnail_url"] is None


def test_receipts_and_cache_are_private_and_alias_bound(store):
    first = inspect(store)
    again = inspect(
        store,
        handler=lambda request: (_ for _ in ()).throw(AssertionError("cached request")),
    )
    assert again["cached"] and again["social_receipt_id"] == first["social_receipt_id"]
    metadata = validate_social_receipt(
        store,
        "owner",
        "project",
        first["social_receipt_id"],
        "https://youtu.be/aqz-KE-bpKQ",
    )
    assert metadata["title"] == first["title"]
    for uid, pid, url in [
        ("other", "project", YT),
        ("owner", "other", YT),
        ("owner", "project", "https://youtu.be/abcdefghijk"),
    ]:
        with pytest.raises(ValueError):
            validate_social_receipt(store, uid, pid, first["social_receipt_id"], url)


def test_project_ownership_checked_before_network(store):
    store.project.side_effect = PermissionError("Denied")
    with pytest.raises(PermissionError):
        inspect(
            store,
            handler=lambda request: (_ for _ in ()).throw(AssertionError("network")),
        )


def test_visible_counts_are_kept_exact_or_explicitly_abbreviated(store):
    browser_receipt(store)
    result = inspect(store, request_id="read-post")
    assert result["engagement"]["views"]["value"] == 125000
    assert result["engagement"]["likes"]["value"] is None
    assert result["engagement"]["likes"]["display"] == "1.2K"
    assert result["engagement"]["comments"] is None
    assert result["engagement_status"] == "observed"
    assert result["published_at"] == "2026-01-02T03:04:05+00:00"
    assert result["evidence"][-1]["source"] == "browser_harness"


@pytest.mark.parametrize(
    "changes",
    [
        {"owner": "other"},
        {"project": "other"},
        {"url": X},
        {"metadata": {"canonical_url": "https://youtu.be/abcdefghijk"}},
    ],
)
def test_browser_evidence_requires_owned_exact_post(store, changes):
    browser_receipt(store, **changes)
    with pytest.raises(ValueError):
        inspect(
            store,
            request_id="read-post",
            handler=lambda request: (_ for _ in ()).throw(
                AssertionError("network before provenance")
            ),
        )


def test_optional_youtube_api_provides_only_returned_metrics_and_omits_secret(store):
    store.config.youtube_api_key = "private-test-key"
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "www.googleapis.com":
            assert request.url.params["key"] == "private-test-key"
            assert "contentDetails" in request.url.params["part"].split(",")
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "aqz-KE-bpKQ",
                            "snippet": {
                                "title": "Official title",
                                "channelTitle": "Official creator",
                                "publishedAt": "2021-02-03T04:05:06Z",
                            },
                            "statistics": {"viewCount": "56789", "commentCount": "0"},
                            "contentDetails": {"duration": "PT14M45S"},
                            "status": {"embeddable": False},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    result = inspect(store, handler=handler)
    assert result["engagement"]["views"]["value"] == 56789
    assert result["engagement"]["comments"]["value"] == 0
    assert result["engagement"]["likes"] is None
    assert result["embeddable"] is False and result["post_verified"]
    assert result["published_at"] == "2021-02-03T04:05:06+00:00"
    assert result["duration"] == {
        "seconds": 885,
        "source": "youtube_api",
        "evidence": "YouTube contentDetails.duration: PT14M45S",
        "observed_at": result["observed_at"],
    }
    assert len(requests) == 2  # Runtime shares the existing metadata call.
    assert "private-test-key" not in str(result)
    assert "private-test-key" not in str(
        store.get("social_reference", result["social_receipt_id"])
    )


@pytest.mark.parametrize("details,live", [
    ({"duration": "PT0S"}, "none"),
    ({"duration": "PT119S"}, "live"),
    ({"duration": "PT119S"}, "upcoming"),
    ({"duration": "885"}, "none"),
    ({"duration": "P1M"}, "none"),
    ({"duration": "PT999999H"}, "none"),
    ({"duration": 119}, "none"),
    ({}, "none"),
    (None, "none"),
    ([], "none"),
])
def test_youtube_runtime_unknown_for_live_missing_or_invalid_duration(store, details, live):
    store.config.youtube_api_key = "test-key"

    def handler(request):
        if request.url.host == "www.googleapis.com":
            return httpx.Response(200, json={"items": [{
                "id": "aqz-KE-bpKQ", "snippet": {"liveBroadcastContent": live},
                "contentDetails": details, "statistics": {"viewCount": "123"},
            }]})
        return httpx.Response(404)

    result = inspect(store, handler=handler)
    assert result["duration"] is None
    assert result["engagement"]["views"]["value"] == 123
    assert any("Runtime is unavailable" in note for note in result["limitations"])


@pytest.mark.parametrize("api_case,expected_seconds,expected_source", [
    ("failed", 119, "json_ld"),
    ("missing", 119, "json_ld"),
    ("different_post", 119, "json_ld"),
    ("valid", 885, "youtube_api"),
    ("live", None, None),
])
def test_api_runtime_priority_and_exact_browser_fallback(store, api_case, expected_seconds, expected_source):
    store.config.youtube_api_key = "test-key"
    browser_receipt(store, metadata={"duration": {
        "seconds": 119, "source": "json_ld", "evidence": "VideoObject.duration: PT119S",
        "observed_at": "2026-10-01T00:00:00Z",  # Capture time, not page input, must win.
    }})

    def handler(request):
        if request.url.host != "www.googleapis.com" or api_case == "failed":
            return httpx.Response(403)
        return httpx.Response(200, json={"items": [{
            "id": "abcdefghijk" if api_case == "different_post" else "aqz-KE-bpKQ",
            "snippet": {"liveBroadcastContent": "live" if api_case == "live" else "none"},
            "contentDetails": {} if api_case == "missing" else {"duration": "PT14M45S"},
        }]})

    result = inspect(store, request_id="read-post", handler=handler)
    if expected_seconds is None:
        assert result["duration"] is None
    else:
        assert result["duration"]["seconds"] == expected_seconds
        assert result["duration"]["source"] == expected_source
        if expected_source == "json_ld":
            assert result["duration"]["observed_at"] == "2023-11-14T22:13:20+00:00"
            assert result["duration"]["evidence"] == "VideoObject.duration: PT119S"
            assert result["evidence"][-1]["request_id"] == "read-post"
        else:
            assert result["duration"]["observed_at"] == result["observed_at"]


@pytest.mark.parametrize("changes", [
    {"seconds": True}, {"seconds": "119"}, {"seconds": 0}, {"seconds": -1},
    {"seconds": float("inf")}, {"seconds": float("nan")}, {"seconds": 604801},
    {"seconds": 10**1000}, {"source": "title"}, {"source": {}}, {"evidence": ""},
    {"evidence": []}, {"observed_at": None}, {"observed_at": "invalid"},
    {"observed_at": "2026-10-01"},
])
def test_receipt_duration_validation_rejects_unattributable_or_unbounded_values(changes):
    assert validated_duration({
        "seconds": 119, "source": "json_ld", "evidence": "VideoObject.duration: PT119S",
        "observed_at": "2026-10-01T00:00:00Z", **changes,
    }) is None


@pytest.mark.parametrize("seconds", [0.5, 119, 604800])
def test_receipt_duration_validation_preserves_real_runtime(seconds):
    result = validated_duration({
        "seconds": seconds, "source": "json_ld", "evidence": "VideoObject.duration",
        "observed_at": "2026-10-01T00:00:00Z",
    })
    assert result["seconds"] == seconds
    assert result["observed_at"] == "2026-10-01T00:00:00+00:00"


@pytest.mark.parametrize("changes", [
    {"post_verified": False}, {"observed_at": None},
    {"duration": {"seconds": 119, "source": "youtube_api", "evidence": "Not an API response"}},
])
def test_browser_runtime_requires_verified_content_capture_time_and_json_ld(store, changes):
    browser_receipt(store, metadata={"duration": {
        "seconds": 119, "source": "json_ld", "evidence": "VideoObject.duration: PT119S",
    }, **changes})
    assert inspect(store, request_id="read-post")["duration"] is None


def test_x_text_is_parsed_as_text_never_returned_html_and_views_are_post_views(store):
    def handler(request):
        assert request.url.host == "publish.twitter.com"
        return httpx.Response(
            200,
            json={
                "type": "rich",
                "author_name": "Creator",
                "url": X.replace("x.com", "twitter.com"),
                "author_url": "https://twitter.com/creator",
                "html": '<blockquote><p>Original <a href="https://x.com">post</a><script>evil()</script></p></blockquote><script src="https://evil.test/x.js"></script>',
            },
        )

    result = inspect(store, url=X, handler=handler)
    assert result["title"] == "Original post"
    assert result["engagement_labels"]["views"] == "Post views"
    assert "evil" not in str(result)


def test_failed_provider_is_honest_and_does_not_verify_a_post(store):
    result = inspect(store, url=TT, handler=lambda request: httpx.Response(403))
    assert (
        result["post_verified"] is False
        and result["engagement_status"] == "unavailable"
    )
    assert result["creator"] == {"name": None, "url": None}
    assert any("unavailable" in text for text in result["limitations"])


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "http://127.0.0.1/secret"}),
        httpx.Response(302, headers={"location": "https://evil.test/secret"}),
        httpx.Response(200, content=b"x" * 262145),
        httpx.Response(200, json=[{"title": "wrong shape"}]),
    ],
)
def test_provider_response_is_bounded_and_redirects_are_fixed(response):
    async def run():
        requests = []

        def handler(request):
            requests.append(str(request.url))
            return response

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError):
                await _json(client, "https://www.youtube.com/oembed", {"url": YT})
        assert len(requests) == 1

    asyncio.run(run())


def test_official_x_redirect_is_supported():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    302, headers={"location": "https://publish.x.com/oembed?url=" + X}
                )
                if request.url.host == "publish.twitter.com"
                else httpx.Response(200, json={"ok": True})
            )
        ) as client:
            assert await _json(
                client, "https://publish.twitter.com/oembed", {"url": X}
            ) == {"ok": True}

    asyncio.run(run())


def test_login_wall_address_does_not_prove_content_or_metrics(store):
    browser_receipt(store, metadata={"post_verified": False})
    result = inspect(
        store, request_id="read-post", handler=lambda request: httpx.Response(403)
    )
    assert result["post_verified"] is False
    assert result["engagement_status"] == "unavailable"
    assert all(value is None for value in result["engagement"].values())
    assert any(
        "could not verify its public content" in text for text in result["limitations"]
    )


@pytest.mark.parametrize("has_post", [True, False])
def test_actual_worker_snapshot_contract_hydrates_only_verified_public_posts(
    store, has_post
):
    import json
    import shutil
    import subprocess

    from video_use_mcp.pilot.reference_browser_worker import SOCIAL_METADATA_JS

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to exercise the production browser extractor")
    schema = {
        "@type": "VideoObject",
        "url": YT,
        "name": "Real browser title",
        "author": {"name": "Real browser creator"},
        "uploadDate": "2026-01-02",
        "duration": "PT1M59S",
        "interactionStatistic": [
            {
                "interactionType": "https://schema.org/WatchAction",
                "userInteractionCount": 12345,
            },
            {
                "interactionType": "https://schema.org/LikeAction",
                "userInteractionCount": "1.2K",
            },
        ],
    }
    setup = (
        "const source="
        + json.dumps(YT)
        + "; const schema="
        + json.dumps(schema if has_post else None)
        + ";"
        + r"""
        global.location={href:source};
        global.document={querySelectorAll(selector){
            if(selector==='link[rel="canonical"]')return [{href:source}];
            if(selector==='script[type="application/ld+json"]')return schema?[{textContent:JSON.stringify(schema)}]:[];
            return [];
        }};
        global.fetch=()=>{throw Error('Extractor must not call network')};
    """
    )
    result = subprocess.run(
        [
            node,
            "-e",
            setup + "process.stdout.write(JSON.stringify(" + SOCIAL_METADATA_JS + "));",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    metadata = json.loads(result.stdout)
    # This is precisely the shape snapshot() saves, with its capture timestamp.
    metadata["observed_at"] = 1700000000
    browser_receipt(store, metadata=metadata)
    output = inspect(
        store, request_id="read-post", handler=lambda request: httpx.Response(403)
    )
    assert metadata["post_verified"] is has_post
    assert output["post_verified"] is has_post
    if has_post:
        assert output["title"] == "Real browser title"
        assert output["creator"]["name"] == "Real browser creator"
        assert output["engagement"]["views"]["value"] == 12345
        assert (
            output["engagement"]["views"]["observed_at"] == "2023-11-14T22:13:20+00:00"
        )
        assert output["engagement"]["likes"]["value"] is None
        assert output["engagement"]["likes"]["display"] == "1.2K"
        assert output["published_at"] == "2026-01-02T00:00:00"
        assert output["duration"] == {
            "seconds": 119, "source": "json_ld", "evidence": "VideoObject.duration: PT1M59S",
            "observed_at": "2023-11-14T22:13:20+00:00",
        }
    else:
        assert output["title"] is None
        assert output["creator"]["name"] is None
        assert output["engagement_status"] == "unavailable"
        assert output["duration"] is None
        assert all(metric is None for metric in output["engagement"].values())
