"""Public social-post identity and evidence, without copied videos or invented reach."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from mcp.types import CallToolResult, TextContent

from .store import ident

METRICS = ("views", "likes", "comments", "shares")
API_ENDPOINTS = {
    "https://www.youtube.com/oembed",
    "https://www.tiktok.com/oembed",
    "https://publish.twitter.com/oembed",
    "https://publish.x.com/oembed",
    "https://www.googleapis.com/youtube/v3/videos",
}


def social_post(value):
    """Canonical public post identity; share URLs must first resolve in a browser."""
    if (
        not isinstance(value, str)
        or len(value) > 3000
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Use a public YouTube, TikTok or X post URL")
    try:
        p = urlsplit(value)
        if p.scheme != "https" or p.username or p.password or p.port not in {None, 443}:
            raise ValueError
    except ValueError:
        raise ValueError("Use a public HTTPS post URL") from None
    host, path = (p.hostname or "").lower(), p.path.rstrip("/")
    platform = post_id = canonical = None
    if host in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "www.youtube-nocookie.com",
        "youtu.be",
        "www.youtu.be",
    }:
        platform = "youtube"
        if host.endswith("youtu.be"):
            post_id = path.lstrip("/")
        elif path == "/watch":
            values = parse_qs(p.query).get("v", [])
            post_id = values[0] if len(values) == 1 else None
        else:
            match = re.fullmatch(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})", path)
            post_id = match.group(1) if match else None
        if not post_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", post_id):
            raise ValueError("Use an individual YouTube video URL")
        canonical = f"https://www.youtube.com/watch?v={post_id}"
    elif host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}:
        match = re.fullmatch(r"/@([A-Za-z0-9_.]{1,40})/video/([0-9]{10,24})", path)
        if not match:
            raise ValueError(
                "Use the full TikTok @creator/video URL, not a short share link"
            )
        platform, post_id = "tiktok", match.group(2)
        canonical = f"https://www.tiktok.com/@{match.group(1)}/video/{post_id}"
    elif host in {
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
        "mobile.twitter.com",
    }:
        match = re.fullmatch(
            r"/(?:([A-Za-z0-9_]{1,15})/status|i/(?:web/)?status)/([0-9]{5,24})(?:/(?:video|photo)/[1-4])?",
            path,
        )
        if not match:
            raise ValueError("Use an individual public X post URL")
        platform, post_id = "x", match.group(2)
        handle = match.group(1) or "i"
        canonical = f"https://x.com/{handle}/status/{post_id}"
    if not platform:
        raise ValueError("Supported social sources are YouTube, TikTok and X")
    return {"platform": platform, "post_id": post_id, "canonical_url": canonical}


def same_social_post(left, right):
    try:
        first, second = social_post(left), social_post(right)
    except ValueError:
        return False
    return (first["platform"], first["post_id"]) == (
        second["platform"],
        second["post_id"],
    )


class _PostText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.done = False
        self.parts = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignore += 1
        if tag == "p" and not self.done:
            self.inside = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignore:
            self.ignore -= 1
        if tag == "p" and self.inside:
            self.inside = False
            self.done = True

    def handle_data(self, value):
        if self.inside and not self.ignore:
            self.parts.append(value)


def _text(value, limit=500):
    return " ".join(str(value or "").split())[:limit]


def _creator_url(value, platform):
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value)
        allowed = {
            "youtube": {"www.youtube.com", "youtube.com"},
            "tiktok": {"www.tiktok.com", "tiktok.com"},
            "x": {"x.com", "twitter.com", "www.twitter.com"},
        }[platform]
        if (
            p.scheme == "https"
            and p.hostname in allowed
            and not p.username
            and not p.password
            and p.port in {None, 443}
        ):
            return value[:1000]
    except ValueError:
        pass
    return None


async def _json_response(client, endpoint, params):
    """Small fixed-provider responses only; redirects cannot leave official APIs."""
    current = str(httpx.URL(endpoint, params=params))
    for _ in range(3):
        p = urlsplit(current)
        if f"{p.scheme}://{p.netloc}{p.path}" not in API_ENDPOINTS:
            raise ValueError("Provider redirect was outside the public metadata API")
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                current = urljoin(current, response.headers.get("location", ""))
                continue
            if response.status_code != 200:
                raise ValueError("Public metadata is unavailable for this post")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 262144:
                    raise ValueError("Public metadata exceeded its size limit")
                chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks))
            except (ValueError, UnicodeError):
                raise ValueError(
                    "The provider did not return readable metadata"
                ) from None
            if not isinstance(data, dict):
                raise ValueError("The provider did not return post metadata")
            return data
    raise ValueError("Too many public metadata redirects")


async def _json(client, endpoint, params):
    # Per-read socket timeouts alone allow arbitrarily slow trickle responses.
    return await asyncio.wait_for(_json_response(client, endpoint, params), timeout=6)


def _published(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _browser_metadata(store, uid, pid, post, request_id):
    key = hashlib.sha256(f"{uid}:{pid}:{request_id}".encode()).hexdigest()
    receipt = store.get("reference_browser_run", key)
    if (
        not receipt
        or receipt.get("owner") != uid
        or receipt.get("project") != pid
        or receipt.get("status") != "complete"
    ):
        raise ValueError(
            "Social evidence needs a completed browser request from this project"
        )
    report = receipt.get("result", {})
    if report.get("engine") != "browser-harness" or report.get("project_id") != pid:
        raise ValueError(
            "Social evidence needs an actual Browser Harness page snapshot"
        )
    for result in reversed(report.get("results", [])):
        if result.get("ok") is False:
            continue
        snapshot = result.get("snapshot", result)
        page = result.get("page_url") or result.get("url") or snapshot.get("url")
        metadata = snapshot.get("social_metadata") or {}
        canonical = metadata.get("canonical_url") or metadata.get("page_url")
        if (
            same_social_post(page, post["canonical_url"])
            and same_social_post(canonical, post["canonical_url"])
            and metadata.get("platform") == post["platform"]
            and str(metadata.get("post_id")) == post["post_id"]
        ):
            return metadata
    raise ValueError("Browser metadata was not observed on this exact social post")


def _metric(value):
    if not isinstance(value, dict) or value.get("source") not in {
        "visible_text",
        "json_ld",
        "meta",
        "youtube_api",
    }:
        return None
    number, display, evidence = (
        value.get("value"),
        _text(value.get("display"), 80),
        _text(value.get("evidence"), 240),
    )
    if number is not None and (
        type(number) is not int or number < 0 or number > 10**18
    ):
        return None
    if not evidence or (number is None and not display):
        return None
    return {
        "value": number,
        "display": display or str(number),
        "evidence": evidence,
        "source": value["source"],
    }


def validate_social_receipt(store, uid, project_id, receipt_id, reference_url):
    """Load server metadata only; client-provided counts never become evidence."""
    store.project(uid, project_id)
    receipt = store.get("social_reference", receipt_id)
    if (
        not receipt
        or receipt.get("owner") != uid
        or receipt.get("project") != project_id
    ):
        raise ValueError("Social reference receipt does not belong to this project")
    metadata = receipt.get("metadata", {})
    if not same_social_post(metadata.get("canonical_url"), reference_url):
        raise ValueError("Social reference receipt belongs to another post")
    return deepcopy(metadata)


async def inspect_social_post(
    store, uid, project_id, url, browser_request_id="", client=None
):
    store.project(uid, project_id)
    post = social_post(url)
    if browser_request_id and (
        len(browser_request_id) > 160 or any(ord(c) < 32 for c in browser_request_id)
    ):
        raise ValueError("Invalid browser request ID")
    # Validate supplied evidence before any external request, including cache hits.
    browser = (
        _browser_metadata(store, uid, project_id, post, browser_request_id)
        if browser_request_id
        else None
    )
    cache_key = hashlib.sha256(
        f"{uid}:{project_id}:{post['canonical_url']}:{browser_request_id}".encode()
    ).hexdigest()
    cached = store.get("social_reference_cache", cache_key)
    now = datetime.now(timezone.utc)
    if cached:
        receipt = store.get("social_reference", cached.get("receipt_id", ""))
        if (
            receipt
            and receipt.get("owner") == uid
            and receipt.get("project") == project_id
        ):
            age = (
                now - datetime.fromisoformat(receipt["metadata"]["observed_at"])
            ).total_seconds()
            if 0 <= age < 300:
                return {
                    "social_receipt_id": cached["receipt_id"],
                    **deepcopy(receipt["metadata"]),
                    "cached": True,
                }
    metadata = {
        **post,
        "title": None,
        "creator": {"name": None, "url": None},
        "observed_at": now.isoformat(),
        "published_at": None,
        "engagement_labels": {
            "views": "Post views" if post["platform"] == "x" else "Video views",
            "likes": "Likes",
            "comments": "Replies" if post["platform"] == "x" else "Comments",
            "shares": "Reposts" if post["platform"] == "x" else "Shares",
        },
        "engagement": {metric: None for metric in METRICS},
        "engagement_status": "unavailable",
        "post_verified": False,
        "evidence": [],
        "limitations": [],
    }
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(8, connect=4), trust_env=False
    )
    try:
        platform = post["platform"]
        endpoint = {
            "youtube": "https://www.youtube.com/oembed",
            "tiktok": "https://www.tiktok.com/oembed",
            "x": "https://publish.twitter.com/oembed",
        }[platform]
        api_url = (
            post["canonical_url"].replace("https://x.com/", "https://twitter.com/")
            if platform == "x"
            else post["canonical_url"]
        )
        try:
            raw = await _json(
                client,
                endpoint,
                {"url": api_url, "format": "json", "omit_script": "true"},
            )
            if (
                raw.get("type") not in {"video", "rich"}
                or not isinstance(raw.get("author_name"), str)
                or not raw["author_name"]
            ):
                raise ValueError("The provider did not return a public post")
            if raw.get("url") and not same_social_post(raw["url"], url):
                raise ValueError("The provider returned a different post")
            title = raw.get("title")
            if not title and platform == "x":
                parser = _PostText()
                parser.feed(str(raw.get("html", ""))[:50000])
                title = " ".join(parser.parts)
            metadata.update(title=_text(title) or None, post_verified=True)
            metadata["creator"] = {
                "name": _text(raw["author_name"], 160),
                "url": _creator_url(raw.get("author_url"), platform),
            }
            metadata["evidence"].append(
                {
                    "source": "official_oembed",
                    "url": endpoint,
                    "post_url": post["canonical_url"],
                }
            )
        except (httpx.HTTPError, ValueError, TimeoutError):
            metadata["limitations"].append(
                "Official public post metadata was unavailable; the post may be restricted, removed or temporarily blocked."
            )
        key = getattr(getattr(store, "config", None), "youtube_api_key", "")
        if platform == "youtube" and key:
            try:
                raw = await _json(
                    client,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {
                        "part": "snippet,statistics,status",
                        "id": post["post_id"],
                        "key": key,
                    },
                )
                items = raw.get("items", [])
                if not isinstance(items, list):
                    raise ValueError("Invalid public video statistics")
                item = next(
                    (
                        entry
                        for entry in items
                        if isinstance(entry, dict)
                        and entry.get("id") == post["post_id"]
                    ),
                    None,
                )
                if not item:
                    raise ValueError("No public video statistics")
                snippet = item.get("snippet", {})
                if (
                    not isinstance(snippet, dict)
                    or not isinstance(item.get("status", {}), dict)
                    or not isinstance(item.get("statistics", {}), dict)
                ):
                    raise ValueError("Invalid public video statistics")
                metadata.update(
                    title=_text(snippet.get("title")) or metadata["title"],
                    post_verified=True,
                )
                metadata["creator"]["name"] = (
                    _text(snippet.get("channelTitle"), 160)
                    or metadata["creator"]["name"]
                )
                metadata["embeddable"] = item.get("status", {}).get("embeddable")
                metadata["published_at"] = _published(snippet.get("publishedAt"))
                for metric, field in {
                    "views": "viewCount",
                    "likes": "likeCount",
                    "comments": "commentCount",
                }.items():
                    raw_value = item.get("statistics", {}).get(field)
                    if isinstance(raw_value, str) and re.fullmatch(
                        r"[0-9]{1,19}", raw_value
                    ):
                        metadata["engagement"][metric] = _metric(
                            {
                                "value": int(raw_value),
                                "display": raw_value,
                                "evidence": f"YouTube statistics.{field}",
                                "source": "youtube_api",
                            }
                        )
                        if metadata["engagement"][metric]:
                            metadata["engagement"][metric]["observed_at"] = (
                                now.isoformat()
                            )
                metadata["evidence"].append(
                    {
                        "source": "youtube_api",
                        "url": "https://www.googleapis.com/youtube/v3/videos",
                        "post_id": post["post_id"],
                    }
                )
            except (httpx.HTTPError, ValueError, TimeoutError):
                metadata["limitations"].append(
                    "YouTube public statistics were unavailable for this video."
                )
        if browser and browser.get("post_verified") is True:
            metadata["post_verified"] = True
            metadata["published_at"] = metadata["published_at"] or _published(
                browser.get("published_at")
            )
            metadata["title"] = metadata["title"] or _text(browser.get("title")) or None
            creator = browser.get("creator") or {}
            if isinstance(creator, str):
                creator = {"name": creator}
            if isinstance(creator, dict):
                metadata["creator"]["name"] = (
                    metadata["creator"]["name"]
                    or _text(creator.get("name"), 160)
                    or None
                )
                metadata["creator"]["url"] = metadata["creator"]["url"] or _creator_url(
                    creator.get("url"), platform
                )
            captured_at = None
            try:
                if type(browser.get("observed_at")) in {int, float}:
                    captured_at = datetime.fromtimestamp(
                        browser["observed_at"], timezone.utc
                    ).isoformat()
            except (ValueError, OverflowError, OSError):
                pass
            for metric in METRICS:
                observation = _metric(browser.get("metrics", {}).get(metric))
                if observation:
                    observation["observed_at"] = captured_at
                metadata["engagement"][metric] = (
                    metadata["engagement"][metric] or observation
                )
            metadata["evidence"].append(
                {
                    "source": "browser_harness",
                    "request_id": browser_request_id,
                    "post_url": post["canonical_url"],
                    "observed_at": captured_at,
                }
            )
            metadata["limitations"] += [
                _text(item, 240) for item in browser.get("limitations", [])[:4]
            ]
        elif browser:
            metadata["limitations"].append(
                "The browser reached the post address but could not verify its public content; no engagement was taken from that page."
            )
        if any(metadata["engagement"].values()):
            metadata["engagement_status"] = "observed"
        else:
            metadata["limitations"].append(
                "Engagement is unavailable. oEmbed supplies attribution, not view or like counts; unknown counts are not zero and do not establish popularity."
            )
        metadata["limitations"].append(
            "Post metadata and popularity are not visual inspection. Inspect the actual media before claiming its style or motion."
        )
        receipt_id = ident()
        store.put(
            "social_reference",
            receipt_id,
            {"owner": uid, "project": project_id, "metadata": metadata},
        )
        store.put("social_reference_cache", cache_key, {"receipt_id": receipt_id})
        return {"social_receipt_id": receipt_id, **deepcopy(metadata), "cached": False}
    finally:
        if owns_client:
            await client.aclose()


def register_social_references(mcp, store, muser, read):
    @mcp.tool(annotations=read, title="Inspect social reference")
    async def inspect_social_reference(
        project_id: str, url: str, browser_request_id: str = ""
    ) -> CallToolResult:
        """Read public YouTube/TikTok/X post attribution and available engagement before offering it. Returns a private social_receipt_id to attach to Reference, with observed time, evidence and unknown counts as null. Optional browser_request_id reads exact-post metadata from an owned completed Browser Harness snapshot. Public oEmbed does not supply view/like counts; optional configured YouTube API may. Never invent popularity or claim visual inspection from metadata. Does not download media or select/approve the reference."""
        data = await inspect_social_post(
            store, muser(), project_id, url, browser_request_id
        )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(data))],
            structuredContent=data,
        )
