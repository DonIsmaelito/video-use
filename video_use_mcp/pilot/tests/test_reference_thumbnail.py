import asyncio
import base64

import httpx
import pytest

from video_use_mcp.pilot import reference_thumbnail as thumbnails


POSTER = "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"
MEDIA = {"provider": "youtube", "source_url": "https://www.youtube.com/watch?v=abcdefghijk", "poster_url": POSTER}
JPEG = b"\xff\xd8\xff\xe0test\xff\xd9"


@pytest.fixture(autouse=True)
def clear_cache():
    thumbnails._CACHE.clear()
    yield
    thumbnails._CACHE.clear()


def fetch(handler, media=MEDIA):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await thumbnails.reference_poster_metadata(media, client=client)
    return asyncio.run(run())


def test_thumbnail_delivers_only_exact_source_image_and_reuses_bounded_public_cache():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=JPEG)
    result = fetch(handler)
    assert result["reference_poster"] == {
        "source_url": POSTER, "post_id": "abcdefghijk",
        "data_uri": "data:image/jpeg;base64," + base64.b64encode(JPEG).decode(),
    }
    assert fetch(handler) == result
    assert len(requests) == 1
    assert str(requests[0].url) == POSTER
    assert not {"authorization", "cookie"}.intersection(requests[0].headers)


@pytest.mark.parametrize("changes", [
    {"provider": "vimeo"}, {"source_url": "https://youtube.com.evil.example/watch?v=abcdefghijk"},
    {"poster_url": "https://127.0.0.1/image.jpg"},
    {"poster_url": "https://i.ytimg.com/vi/ABCDEFGHIJK/hqdefault.jpg"},
    {"poster_url": "https://user:pass@i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"},
    {"poster_url": None},
])
def test_unverified_or_mismatched_targets_never_issue_requests(changes):
    def forbidden(request):
        raise AssertionError("Unexpected network request")
    assert fetch(forbidden, MEDIA | changes) == {}


@pytest.mark.parametrize("status,headers,body", [
    (302, {"location": "https://example.com/unrelated.jpg"}, JPEG),
    (404, {"content-type": "image/jpeg"}, JPEG),
    (200, {"content-type": "image/svg+xml"}, b"<svg></svg>"),
    (200, {"content-type": "image/jpeg"}, b"<html>not an image</html>"),
    (200, {"content-type": "image/webp"}, JPEG),
    (200, {"content-type": "image/jpeg", "content-length": str(thumbnails.MAX_BYTES + 1)}, JPEG),
    (200, {"content-type": "image/jpeg", "content-length": "invalid"}, JPEG),
])
def test_redirects_missing_images_and_non_raster_or_oversized_responses_are_not_embedded(status, headers, body):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers=headers, content=body)
    assert fetch(handler) == {}
    assert len(calls) == 1
    assert not thumbnails._CACHE


def test_streamed_response_without_size_header_is_bounded():
    class Oversized(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield JPEG[:3]
            for _ in range(9):
                yield b"a" * 16384
    def handler(request):
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, stream=Oversized())
    assert fetch(handler) == {}


def test_fetch_errors_keep_reference_tool_usable():
    def handler(request):
        raise httpx.ReadTimeout("Public thumbnail unavailable", request=request)
    assert fetch(handler) == {}


def test_mismatched_reference_cannot_reuse_cached_image():
    fetch(lambda request: httpx.Response(200, headers={"content-type": "image/jpeg"}, content=JPEG))
    assert fetch(lambda request: pytest.fail("Unexpected network request"),
                 MEDIA | {"source_url": "https://www.youtube.com/watch?v=ABCDEFGHIJK"}) == {}
