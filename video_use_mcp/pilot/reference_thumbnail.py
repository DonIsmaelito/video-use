"""Deliver a bounded public source thumbnail to the app without a second image request.

Only verified reference-player metadata reaches this helper. No source video is
fetched, no auth is forwarded, and the image stays outside model-visible content.
"""

import asyncio
import base64
from collections import OrderedDict
import time

import httpx

from .social_references import social_post, youtube_thumbnail_url

MAX_BYTES = 128 * 1024
_CACHE = OrderedDict()


def _image_type(data):
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def _fetch(client, url):
    async with client.stream("GET", url, follow_redirects=False, headers={"Accept": "image/jpeg,image/webp"}) as response:
        if response.status_code != 200:
            return None
        mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if mime not in {"image/jpeg", "image/webp"}:
            return None
        length = response.headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BYTES):
            return None
        data = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=16384):
            if len(data) + len(chunk) > MAX_BYTES:
                return None
            data.extend(chunk)
        if _image_type(data) != mime:
            return None
        return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


async def reference_poster_metadata(media, *, client=None):
    """Return UI-only bytes for this exact public YouTube thumbnail, or nothing."""
    if not isinstance(media, dict) or media.get("provider") != "youtube":
        return {}
    try:
        post = social_post(media.get("source_url"))
    except ValueError:
        return {}
    if post["platform"] != "youtube":
        return {}
    url = youtube_thumbnail_url(media.get("poster_url"), post["post_id"])
    if not url:
        return {}
    cached = _CACHE.get(url)
    if cached and cached[0] > time.monotonic():
        _CACHE.move_to_end(url)
        return {"reference_poster": dict(cached[1])}
    _CACHE.pop(url, None)
    try:
        # Total wall-clock cap includes response streaming, not just individual reads.
        async with asyncio.timeout(4):
            if client is None:
                async with httpx.AsyncClient(timeout=3, trust_env=False) as own_client:
                    image = await _fetch(own_client, url)
            else:
                image = await _fetch(client, url)
    except (httpx.HTTPError, TimeoutError, ValueError):
        return {}
    if image is None:
        return {}
    payload = {"source_url": url, "post_id": post["post_id"], "data_uri": image}
    _CACHE[url] = (time.monotonic() + 3600, payload)
    while len(_CACHE) > 64:
        _CACHE.popitem(last=False)
    return {"reference_poster": dict(payload)}
