"""Curator-owned discovery locations, separate from the agent's creative choices."""

import json
import ipaddress
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

REGISTRY = Path(__file__).with_name("reference_sources.json")


def _public_https_url(value):
    if (
        not isinstance(value, str)
        or "\\" in value
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise ValueError("Reference sources need public HTTPS collection URLs")
    try:
        url = urlsplit(value)
        host, port = url.hostname or "", url.port
    except ValueError as exc:
        raise ValueError("Reference sources need public HTTPS collection URLs") from exc
    if (
        url.scheme != "https"
        or not host
        or url.username is not None
        or url.password is not None
        or port not in {None, 443}
        or "%" in host
    ):
        raise ValueError("Reference sources need public HTTPS collection URLs")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or host.endswith(
            (".localhost", ".local", ".internal", ".invalid", ".test")
        ):
            raise ValueError("Reference sources need public HTTPS collection URLs")
    else:
        if not address.is_global:
            raise ValueError("Reference sources need public HTTPS collection URLs")
    return url


def _registry():
    data = json.loads(REGISTRY.read_text())
    if data.get("version") != 1 or not isinstance(data.get("sources"), list):
        raise ValueError("Invalid reference source registry")
    seen = set()
    for source in data["sources"]:
        if (
            not isinstance(source, dict)
            or not source.get("id")
            or source["id"] in seen
            or not source.get("name")
            or not isinstance(source.get("categories"), list)
        ):
            raise ValueError(
                "Reference sources need distinct IDs, names and categories"
            )
        _public_https_url(source.get("url", ""))
        roots = source.get("discovery_roots", [source["url"]])
        patterns = source.get("discovery_patterns", [])
        if (
            not isinstance(roots, list)
            or not isinstance(patterns, list)
            or not (roots or patterns)
        ):
            raise ValueError(
                "Reference sources need explicit discovery roots or patterns"
            )
        for root in roots:
            _public_https_url(root)
        for pattern in patterns:
            if not isinstance(pattern, dict):
                raise ValueError(
                    "Discovery patterns must declare origin and path_regex"
                )
            origin = _public_https_url(pattern.get("origin", ""))
            if origin.path not in {"", "/"} or origin.query or origin.fragment:
                raise ValueError("Discovery pattern origins must be HTTPS origins")
            expression = pattern.get("path_regex", "")
            if (
                not isinstance(expression, str)
                or not expression.startswith("/")
                or len(expression) > 200
            ):
                raise ValueError(
                    "Discovery patterns need bounded absolute path expressions"
                )
            try:
                re.compile(expression)
            except re.error as exc:
                raise ValueError("Invalid discovery path expression") from exc
        seen.add(source["id"])
    if any(item not in seen for item in data.get("default_primary", [])):
        raise ValueError("Default reference routing points to an unknown source")
    for route in data.get("routing", {}).values():
        if any(
            item not in seen
            for key in ("primary", "secondary", "nearest", "supplemental")
            for item in route.get(key, [])
        ):
            raise ValueError("Reference routing points to an unknown approved source")
    return data


def reference_source_catalog(category=None, *, compact=False):
    """Category routes express fit, not a global popularity or quality ranking.

    Full mode includes curator evidence and unapproved reserves. Routine model
    context may request compact mode to avoid repeating that research history.
    Filtering changes suggestions only; validation always uses the full allowlist.
    """
    data = _registry()
    approved = data["sources"]
    route = data.get("routing", {}).get(category)
    if category and route:
        ids = list(
            dict.fromkeys(
                item
                for key in ("primary", "secondary", "nearest")
                for item in route.get(key, [])
            )
        )
        selected = [
            source
            for source_id in ids
            for source in approved
            if source["id"] == source_id
        ]
    elif data.get("default_primary") and (category or compact):
        selected = [source for key in data["default_primary"] for source in approved if source["id"] == key]
    elif category:
        selected = [source for source in approved if category in source["categories"]]
    else:
        selected = approved
    if compact:
        keys = {
            "id",
            "name",
            "url",
            "categories",
            "discovery_roots",
            "discovery_patterns",
            "verification",
            "search_notes",
            "inspection_notes",
            "access_notes",
            "biases",
            "role",
        }
        base = {
            "version": data["version"],
            "checked_at": data.get("checked_at"),
            "sources": [
                {k: v for k, v in source.items() if k in keys} for source in selected
            ],
            "evidence_policy": data.get("evidence_policy", []),
            "selection_policy": data.get("selection_policy", ""),
            "feedback_policy": data.get("feedback_policy", []),
        }
    else:
        base = data | {"sources": selected}
    if category:
        base.update(
            category=category,
            coverage=route or (
                {
                    "primary": data["default_primary"],
                    "coverage": "live_search",
                    "notes": "Use the primary social platforms for this brief; candidate access and fit still need live inspection.",
                }
                if data.get("default_primary") else {
                    "coverage": "unmapped",
                    "notes": "No researched route for this category. Explain the gap; use a relevant approved neighbor or ask for a user reference.",
                }
            ),
        )
        base["available_sources"] = [
            {key: source[key] for key in ("id", "name", "url", "categories")}
            for source in approved
        ]
    return base | dict(
        status="ready" if data["sources"] else "awaiting_curation",
        source_count=len(approved),
        matched_source_count=len(selected),
        routing_policy="Category routes are starting points, not a browsing whitelist or a global ranking. Offered references must be individual YouTube, TikTok or X video posts. Specialist collections may identify leads, but cannot be offered as references. Discover, inspect and show one fresh candidate before searching for the next; there are no preselected videos.",
        policy=(
            "Search the approved primary social platforms sequentially using host tools, with Browser Harness for public inspection when needed. "
            "Save source_id and the discovery_url inside that collection for each web reference. "
            "Keep discovery attribution, but offer only the individual YouTube, TikTok or X post after inspecting actual media frames. "
            "Prioritize approachable examples with observed traction and actual brief fit. Report only sourced views/likes and observation dates, never invented popularity. "
            "User-supplied references can be inspected directly. If the list is empty or no source fits, "
            "ask for a reference or an explicitly delegated direction; do not silently broaden the search. "
            "Reserve sources are research leads, not approved discovery sources. Metadata access never proves playback."
        ),
    )


def _collection_path(path):
    # Reject encoded traversal rather than allowing multiple decoding layers to
    # disagree about collection membership. Query strings do not expand a root.
    decoded = unquote(path)
    if (
        "\\" in decoded
        or any(part in {".", ".."} for part in decoded.split("/"))
        or re.search(r"%[0-9a-fA-F]{2}", decoded)
    ):
        raise ValueError("discovery_url must be inside the selected curated collection")
    return posixpath.normpath("/" + decoded.lstrip("/"))


def _same_origin(left, right):
    return left.hostname.lower() == right.hostname.lower() and (left.port or 443) == (
        right.port or 443
    )


def validate_reference_source(reference):
    """Validate reported discovery provenance; no network fetch or playback claim."""
    if reference.get("source") == "user_supplied":
        return
    source = next(
        (
            item
            for item in _registry()["sources"]
            if item["id"] == reference.get("source_id")
        ),
        None,
    )
    if not source:
        raise ValueError(
            "Choose a curated source_id or inspect a user-supplied reference"
        )
    try:
        discovery = _public_https_url(reference.get("discovery_url", ""))
        path = _collection_path(discovery.path)
    except ValueError as exc:
        raise ValueError(
            "discovery_url must be inside the selected curated collection"
        ) from exc
    if source["id"] in {"youtube", "tiktok", "x"}:
        from .social_references import social_post

        try:
            if social_post(reference["discovery_url"])["platform"] == source["id"]:
                return  # Canonical posts and mobile/share aliases are one source.
        except ValueError:
            pass
    for root_url in source.get("discovery_roots", [source["url"]]):
        entry = _public_https_url(root_url)
        root = _collection_path(entry.path)
        if _same_origin(entry, discovery) and (
            root == "/" or path == root or path.startswith(root.rstrip("/") + "/")
        ):
            return
    for pattern in source.get("discovery_patterns", []):
        entry = _public_https_url(pattern["origin"])
        if _same_origin(entry, discovery) and re.fullmatch(pattern["path_regex"], path):
            return
    raise ValueError("discovery_url must be inside the selected curated collection")
