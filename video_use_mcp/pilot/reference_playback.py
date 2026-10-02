"""Play an observed source URL without copying or generating reference media."""

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from mcp.types import CallToolResult, TextContent

from .reference_direction import public_reference_url


# This list is also enforced in Python: a URL outside the resource CSP never
# becomes a player that misleadingly looks ready. The original citation remains
# clickable for other CDNs, authenticated sources and blocked provider embeds.
MEDIA_ORIGINS = (
    "https://media.ordinary.co",
    "https://assets.website-files.com",
    "https://cdn.prod.website-files.com",
    "https://uploads-ssl.webflow.com",
    "https://videos.ctfassets.net",
    "https://video.wixstatic.com",
    "https://cdn.sanity.io",
    "https://framerusercontent.com",
    "https://vod-progressive.akamaized.net",
)
FRAME_ORIGINS = ("https://www.youtube-nocookie.com", "https://player.vimeo.com")
CARD = Path(__file__).parent / "ui" / "card.html"
_DIGEST = hashlib.sha256(
    CARD.read_bytes() + json.dumps([MEDIA_ORIGINS, FRAME_ORIGINS]).encode()
).hexdigest()[:16]
REFERENCE_UI_URI = f"ui://video-use/reference-{_DIGEST}.html"
REFERENCE_UI_META = {"ui": {"resourceUri": REFERENCE_UI_URI}}


def _https(value):
    public_reference_url(value)
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.port not in {None, 443}:
        raise ValueError("Reference playback needs a public HTTPS URL")
    return parsed


def _provider(value):
    """Canonicalize only standard public provider routes, never arbitrary HTML."""
    parsed = _https(value)
    host, path = parsed.hostname.lower(), parsed.path.rstrip("/")
    youtube_hosts = {"youtube.com", "www.youtube.com", "m.youtube.com", "www.youtube-nocookie.com"}
    video_id = None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = path.lstrip("/")
    elif host in youtube_hosts:
        if path == "/watch":
            values = parse_qs(parsed.query).get("v", [])
            video_id = values[0] if len(values) == 1 else None
        else:
            match = re.fullmatch(r"/(?:embed|shorts|live)/([A-Za-z0-9_-]{11})", path)
            video_id = match.group(1) if match else None
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return {"provider": "youtube", "id": video_id,
                "embed_url": "https://www.youtube-nocookie.com/embed/" + video_id}
    if host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
        pattern = r"/video/([0-9]{1,12})" if host == "player.vimeo.com" else r"/([0-9]{1,12})"
        match = re.fullmatch(pattern, path)
        hashes = parse_qs(parsed.query, keep_blank_values=True).get("h", [])
        if hashes and (len(hashes) != 1 or not re.fullmatch(r"[a-fA-F0-9]{6,32}", hashes[0])):
            return None
        if match:
            # A hash already exposed by a public page is part of that embed's
            # address. Preserve it exactly; never invent a hash or authenticate.
            suffix = "?h=" + hashes[0] if hashes else ""
            return {"provider": "vimeo", "id": match.group(1),
                    "embed_url": "https://player.vimeo.com/video/" + match.group(1) + suffix}
    return None


def _same_media(left, right):
    if left == right:
        return True
    try:
        first, second = _provider(left), _provider(right)
    except ValueError:
        return False
    return bool(first and second and (first["provider"], first["id"]) ==
                (second["provider"], second["id"]))


def observed_playback(store, uid, project_id, reference):
    """Require the exact URL on a cited page in this owner's completed receipt."""
    playback = reference.get("playback")
    if not playback:
        raise ValueError("No browser-observed playback URL was saved for this reference")
    media_url = playback["url"]
    _https(media_url)
    receipt_key = hashlib.sha256(
        (uid + ":" + project_id + ":" + playback["browser_request_id"]).encode()
    ).hexdigest()
    receipt = store.get("reference_browser_run", receipt_key)
    if (not receipt or receipt.get("owner") != uid or receipt.get("project") != project_id
            or receipt.get("status") != "complete"):
        raise ValueError("Playback provenance needs a completed browser request from this project")
    report = receipt.get("result", {})
    if report.get("engine") != "browser-harness" or report.get("project_id") != project_id:
        raise ValueError("Playback provenance needs an actual Browser Harness page snapshot")
    cited = {reference.get("url"), reference.get("discovery_url")} - {"", None}
    for result in report.get("results", []):
        if result.get("ok") is False:
            continue
        snapshot = result.get("snapshot", result)
        page = result.get("page_url") or result.get("url") or snapshot.get("url")
        if page not in cited:
            continue
        # A collection may contain dozens of unrelated hero loops. Seeing one
        # there does not establish that it belongs to the offered candidate.
        if page != reference["url"] and not _same_media(media_url, reference["url"]):
            continue
        for video in snapshot.get("videos", []):
            if isinstance(video, dict) and video.get("src") == media_url:
                return {"source_page_url": page, "observed_as": "video",
                        "duration_seconds": video.get("duration_seconds"),
                        "loop": video.get("loop", False), "url": media_url}
        for player in snapshot.get("embedded_players", []):
            if isinstance(player, dict) and player.get("src") == media_url:
                return {"source_page_url": page, "observed_as": "embedded_player", "url": media_url}
        for link in snapshot.get("links", []):
            url = link.get("url") if isinstance(link, dict) else link
            if url == media_url and _provider(media_url):
                return {"source_page_url": page, "observed_as": "provider_link", "url": media_url}
        if page == media_url and _provider(media_url):
            return {"source_page_url": page, "observed_as": "provider_page", "url": media_url}
    raise ValueError("Playback URL was not observed on the cited reference or discovery page")


def reference_player(store, uid, project_id, reference_id, round_id=""):
    store.project(uid, project_id)
    state = store.get("creative", project_id) or {}
    direction = state.get("intake", {}).get("reference_direction", {})
    rounds = direction.get("rounds", [])
    current_round = rounds[-1].get("id") if rounds else None
    if round_id and round_id != current_round:
        raise ValueError("The reference offer changed; use the latest reference player's round_id")
    offered = rounds[-1].get("references", []) if rounds else []
    reference = next((item for item in offered if item.get("id") == reference_id), None)
    if reference is None:
        raise ValueError("Choose a reference ID from this project's current offered references")
    source_url = public_reference_url(reference["url"])
    data = {"project_id": project_id, "reference_id": reference_id, "round_id": current_round, "follow_project": False,
            "source_link": {"url": source_url, "title": reference["title"]},
            "playback_status": "source_link", "coverage": "unavailable",
            "media": {"media_type": "source_link", "title": reference["title"],
                      "source_url": source_url, "caption": "Open source"},
            "next_action": "Let the user inspect the source, then ask the supplied native reference-choice question. Playback does not select or approve a reference."}
    try:
        observed = observed_playback(store, uid, project_id, reference)
        url = observed["url"]
        provider = _provider(url)
        duration = observed.get("duration_seconds")
        short_clip = isinstance(duration, (int, float)) and duration <= 15
        if provider:
            exact = _same_media(url, reference["url"])
            media = {"media_type": "text/html", "embed_url": provider["embed_url"]}
        else:
            parsed = _https(url)
            extension = Path(parsed.path).suffix.lower()
            if observed["observed_as"] != "video" or extension not in {".mp4", ".webm"}:
                raise ValueError("This source has no supported public MP4, WebM, YouTube or Vimeo player")
            origin = parsed.scheme + "://" + parsed.netloc
            if origin not in MEDIA_ORIGINS:
                raise ValueError("This source's media origin is not enabled for inline playback; open the original source")
            exact = url == reference["url"] and not short_clip and not observed.get("loop")
            media = {"media_type": "video/mp4" if extension == ".mp4" else "video/webm", "url": url}
        coverage = "source_video" if exact else "source_preview"
        data["media"].update(media, caption="Source video" if exact else "Source clip")
        data.update(playback_status="available", coverage=coverage,
                    source_page_url=observed["source_page_url"],
                    coverage_note=("This player points to the cited source video." if exact else
                                   "This is a source clip or page preview; it has not been verified as the complete reference film."),
                    playback_note="The source controls availability and embed permissions. If playback is blocked or requires sign-in, open the source link.")
        if duration is not None:
            data["duration_seconds"] = duration
    except ValueError as exc:
        data["fallback_reason"] = str(exc)
    return data


def register_reference_playback(mcp, store, muser, read):
    resource_meta = {"ui": {"prefersBorder": False, "csp": {
        "resourceDomains": list(MEDIA_ORIGINS), "connectDomains": [],
        "frameDomains": list(FRAME_ORIGINS),
    }}}

    @mcp.resource(REFERENCE_UI_URI, mime_type="text/html;profile=mcp-app", meta=resource_meta)
    def reference_card() -> str:
        return CARD.read_text()

    @mcp.resource("ui://video-use/reference-{version}.html", mime_type="text/html;profile=mcp-app", meta=resource_meta)
    def previous_reference_card(version: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{16}", version):
            raise ValueError("Unknown reference player version")
        return reference_card()

    @mcp.tool(annotations=read, meta=REFERENCE_UI_META, title="Play source reference")
    def show_video_reference(project_id: str, reference_id: str, round_id: str = "") -> CallToolResult:
        """Show an offered source reference in a neutral player, before asking the user's choice. Always pass the round_id from the returned show_video_reference descriptor so an older offer cannot display a different film with a reused ID. Reads only saved references and Browser Harness receipts; never downloads, stores or generates source video. Save Reference.playback.url and playback.browser_request_id from the cited page's actual videos, embedded_players or provider links when offering references. Short source clips are labeled honestly. Unsupported or unverified media returns the original source link. Showing playback does not select a reference or approve production."""
        data = reference_player(store, muser(), project_id, reference_id, round_id)
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))], structuredContent=data)
