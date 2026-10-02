"""Curator-owned discovery locations, separate from the agent's creative choices."""

import json
import posixpath
from pathlib import Path
from urllib.parse import unquote, urlsplit

REGISTRY = Path(__file__).with_name("reference_sources.json")


def reference_source_catalog():
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
        url = urlsplit(source.get("url", ""))
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Reference sources need public HTTPS collection URLs")
        seen.add(source["id"])
    return data | dict(
        status="ready" if data["sources"] else "awaiting_curation",
        policy=(
            "Search these curator-approved collections using host tools, not arbitrary sites. "
            "Save source_id and the discovery_url inside that collection for each web reference. "
            "An example may link out to its creator's site; preserve both links. "
            "User-supplied references can be inspected directly. If the list is empty or no source fits, "
            "ask for a reference or an explicitly delegated direction; do not silently broaden the search."
        ),
    )


def _collection_path(path):
    return posixpath.normpath("/" + unquote(path).lstrip("/"))


def validate_reference_source(reference):
    """Validate reported discovery provenance; no network fetch or playback claim."""
    if reference.get("source") == "user_supplied":
        return
    source = next(
        (
            item
            for item in reference_source_catalog()["sources"]
            if item["id"] == reference.get("source_id")
        ),
        None,
    )
    if not source:
        raise ValueError(
            "Choose a curated source_id or inspect a user-supplied reference"
        )
    entry, discovery = (
        urlsplit(source["url"]),
        urlsplit(reference.get("discovery_url", "")),
    )
    root, path = _collection_path(entry.path), _collection_path(discovery.path)
    if (
        discovery.scheme != "https"
        or discovery.netloc.lower() != entry.netloc.lower()
        or discovery.username
        or discovery.password
        or not (root == "/" or path == root or path.startswith(root.rstrip("/") + "/"))
    ):
        raise ValueError("discovery_url must be inside the selected curated collection")
