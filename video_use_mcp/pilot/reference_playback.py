"""Play an observed source URL without copying or generating reference media."""

import hashlib
import json
from pathlib import Path
import re
from textwrap import shorten
from urllib.parse import parse_qs, urlsplit

from mcp.types import CallToolResult, TextContent

from .reference_direction import public_reference_url
from .social_references import social_post, validate_social_receipt, youtube_thumbnail_url


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
FRAME_ORIGINS = (
    "https://www.youtube-nocookie.com", "https://player.vimeo.com",
    "https://www.tiktok.com", "https://platform.twitter.com", "https://platform.x.com",
)
SOCIAL_RESOURCE_ORIGINS = (
    "https://platform.twitter.com", "https://platform.x.com", "https://pbs.twimg.com",
    "https://abs.twimg.com", "https://cdn.syndication.twimg.com",
    "https://i.ytimg.com",
)
SOCIAL_CONNECT_ORIGINS = (
    "https://platform.twitter.com", "https://platform.x.com",
    "https://syndication.twitter.com", "https://cdn.syndication.twimg.com",
)
CARD = Path(__file__).parent / "ui" / "card.html"
_DIGEST = hashlib.sha256(
    CARD.read_bytes() + json.dumps([MEDIA_ORIGINS, FRAME_ORIGINS, SOCIAL_RESOURCE_ORIGINS, SOCIAL_CONNECT_ORIGINS]).encode()
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
    if host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}:
        match = re.fullmatch(r"/player/v1/([0-9]{10,24})", path)
        if match:
            return {"provider": "tiktok", "id": match.group(1), "embed_url": "https://www.tiktok.com/player/v1/" + match.group(1)}
    try:
        social = social_post(value)
    except ValueError:
        social = None
    if social and social["platform"] == "tiktok":
        return {"provider": "tiktok", "id": social["post_id"], "embed_url": "https://www.tiktok.com/player/v1/" + social["post_id"]}
    if social and social["platform"] == "x":
        return {"provider": "x", "id": social["post_id"]}
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


def _plain(value, width=360):
    return shorten(value, width=width, placeholder="…") if isinstance(value, str) else ""


def _reference_description(current, reference):
    """Use this candidate's reason, never an adjacent or previous round's film."""
    batches = current.get("search_batches") or [current.get("search", {})]
    for batch in reversed(batches):
        for candidate in batch.get("candidates", []):
            cited = candidate.get("reference", {})
            if (cited.get("id") == reference["id"]
                    and cited.get("url") == reference["url"]
                    and candidate.get("disposition") == "recommend"):
                fit = _plain(candidate.get("fit"))
                if fit:
                    return fit
    return _plain(reference.get("observed_traits"))


def _social_attribution(social):
    """Plain source labels only from the owned, exact-post metadata receipt."""
    if not social.get("post_verified"):
        return ""
    parts = []
    creator = social.get("creator") or {}
    if isinstance(creator, dict) and (name := _plain(creator.get("name"), 160)):
        parts.append(name)
    for metric, label in (("views", "Post views" if social.get("platform") == "x" else "Views"), ("likes", "Likes")):
        observation = (social.get("engagement") or {}).get(metric)
        if not isinstance(observation, dict) or not observation.get("evidence"):
            continue
        if observation.get("source") not in {"visible_text", "json_ld", "meta", "youtube_api"}:
            continue
        number = observation.get("value")
        if number is not None and (type(number) is not int or number < 0):
            continue
        display = _plain(observation.get("display"), 80)
        if not display and number is not None:
            display = f"{number:,}"
        if display:
            parts.append(f"{label}: {display}")
    published = social.get("published_at")
    if isinstance(published, str) and re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", published):
        parts.append("Published " + published[:10])
    return " · ".join(parts)


def _social_poster(social):
    """A source thumbnail is an image/link fallback, never proof of playback."""
    if social.get("post_verified") is not True:
        return {}
    try:
        post = social_post(social.get("canonical_url"))
    except ValueError:
        return {}
    if (post["platform"] != "youtube"
            or social.get("platform", "youtube") != "youtube"
            or social.get("post_id", post["post_id"]) != post["post_id"]):
        return {}
    # Older owned receipts predate stored thumbnails. The standard public
    # image path preserves the verified ID; the UI handles unavailable images.
    url = youtube_thumbnail_url(social.get("thumbnail_url"), post["post_id"])
    return {"provider": "youtube", "poster_url": url or f"https://i.ytimg.com/vi/{post['post_id']}/hqdefault.jpg"}


def _presentation_context(direction, current, reference):
    inspection = reference.get("inspection", "metadata")
    evidence_status = {
        "metadata": "Metadata only · visuals and motion not inspected.",
        "page": "Page inspected · video motion and sound not checked.",
        "image": "Still images inspected · video motion and sound not checked.",
        "video": "Video inspection reported by the assistant.",
    }.get(inspection, "Visual inspection not recorded.")
    action = (
        "Describe THIS reference now in one short chat sentence using media.description and available media.attribution. "
        "Keep its inspection limitation clear; metadata is not proof of visual style, motion or popularity. "
    )
    status = direction.get("status", current.get("status"))
    if status == "collecting":
        action += (
            "Then continue sequential research and append the next useful candidate to this round, or finish collection. "
            "Do not ask the reference-choice question yet or replay earlier players."
        )
    elif status == "offered":
        action += (
            "Show any remaining unshown references with their own descriptions, then ask the supplied native reference-choice question once. "
            "Include Find another batch and Give my input."
        )
    else:
        action += "Follow the saved reference decision; do not ask an already answered reference-choice question again."
    return {"description": _reference_description(current, reference), "attribution": "",
            "inspection": inspection, "evidence_status": evidence_status}, action


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
    presentation, next_action = _presentation_context(direction, rounds[-1], reference)
    data = {"project_id": project_id, "reference_id": reference_id, "round_id": current_round, "follow_project": False,
            "source_link": {"url": source_url, "title": reference["title"]},
            "playback_status": "source_link", "coverage": "unavailable",
            "media": {**presentation, "media_type": "source_link", "title": reference["title"],
                      "source_url": source_url, "caption": "Open source"},
            "next_action": next_action + " Playback does not select or approve a reference."}
    try:
        if reference.get("social_receipt_id"):
            social = validate_social_receipt(store, uid, project_id, reference["social_receipt_id"], reference["url"])
            data["social"] = social
            data["media"]["attribution"] = _social_attribution(social)
            data["media"].update(_social_poster(social))
            if social.get("embeddable") is False:
                raise ValueError("This video's owner does not permit embedding; open the original source")
            if not social.get("post_verified"):
                if not reference.get("playback"):
                    raise ValueError("The public social post could not be verified; open its original source")
                # An unavailable metadata API must not erase independent,
                # exact-page browser evidence. Explicit embed denials still win.
                observed = observed_playback(store, uid, project_id, reference)
            else:
                observed = {"url": social["canonical_url"], "source_page_url": social["canonical_url"], "observed_as": "official_social_metadata"}
            if social.get("post_verified") and social.get("title"):
                data["media"]["title"] = social["title"]
                data["source_link"]["title"] = social["title"]
        else:
            observed = observed_playback(store, uid, project_id, reference)
        url = observed["url"]
        provider = _provider(url)
        duration = observed.get("duration_seconds")
        short_clip = isinstance(duration, (int, float)) and duration <= 15
        if provider:
            exact = _same_media(url, reference["url"])
            media = ({"media_type": "social/x", "post_id": provider["id"]}
                     if provider["provider"] == "x" else
                     {"media_type": "text/html", "embed_url": provider["embed_url"], "provider": provider["provider"]})
        else:
            parsed = _https(url)
            extension = Path(parsed.path).suffix.lower()
            if observed["observed_as"] != "video" or extension not in {".mp4", ".webm"}:
                raise ValueError("This source has no supported public MP4, WebM or supported provider player")
            origin = parsed.scheme + "://" + parsed.netloc
            if origin not in MEDIA_ORIGINS:
                raise ValueError("This source's media origin is not enabled for inline playback; open the original source")
            exact = url == reference["url"] and not short_clip and not observed.get("loop")
            media = {"media_type": "video/mp4" if extension == ".mp4" else "video/webm", "url": url}
        coverage = "source_post" if provider and provider["provider"] == "x" else "source_video" if exact else "source_preview"
        data["media"].update(media, caption="Source post" if provider and provider["provider"] == "x" else "Source video" if exact else "Source clip")
        data.update(playback_status="available", coverage=coverage,
                    source_page_url=observed["source_page_url"],
                    coverage_note=("This displays the cited X post; inspect it to confirm whether it contains playable video." if coverage == "source_post" else "This player points to the cited source video." if exact else
                                   "This is a source clip or page preview; it has not been verified as the complete reference film."),
                    playback_note="A player address is ready; client display and playback have not been verified. The source and chat host control embed permissions. If blocked or sign-in is required, open the source link.")
        if duration is not None:
            data["duration_seconds"] = duration
    except ValueError as exc:
        data["fallback_reason"] = str(exc)
    return data


def register_reference_playback(mcp, store, muser, read):
    resource_meta = {"ui": {"prefersBorder": False, "csp": {
        "resourceDomains": list(MEDIA_ORIGINS + SOCIAL_RESOURCE_ORIGINS), "connectDomains": list(SOCIAL_CONNECT_ORIGINS),
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
        """Show an offered source reference in a neutral player, before asking the user's choice. Always pass the round_id from the returned show_video_reference descriptor so an older offer cannot display a different film with a reused ID. Reads only saved references and owned social-metadata or Browser Harness receipts; never downloads, stores or generates source video. For YouTube, TikTok and X attach social_receipt_id from inspect_social_reference; it does not prove visual inspection or popularity. Otherwise save Reference.playback.url and playback.browser_request_id from the cited page's actual videos, embedded_players or provider links when offering references. Short source clips are labeled honestly. Unsupported or unverified media returns the original source link. Showing playback does not select a reference or approve production."""
        data = reference_player(store, muser(), project_id, reference_id, round_id)
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))], structuredContent=data)
