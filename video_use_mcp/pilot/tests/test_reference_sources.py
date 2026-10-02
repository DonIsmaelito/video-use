"""Discovery stays inside curator-selected collections; candidates do not approve themselves."""

import json

import pytest

from video_use_mcp.pilot import reference_sources as sources


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "sources": [
                    {
                        "id": "motion",
                        "name": "Motion collection",
                        "url": "https://example.com/curated/motion",
                        "categories": ["motion_design"],
                        "search_notes": "Use collection search",
                        "inspection_notes": "Public images; playback may require login",
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(sources, "REGISTRY", path)
    return path


def reference(discovery_url):
    return dict(
        source="web_search",
        source_id="motion",
        discovery_url=discovery_url,
        url="https://artist.example/film",
    )


def test_approved_collection_can_link_to_original_creator(registry):
    sources.validate_reference_source(
        reference("https://example.com/curated/motion/film")
    )
    assert sources.reference_source_catalog()["status"] == "ready"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/elsewhere",
        "https://example.com/curated/motionfake/film",
        "https://example.com.evil.test/curated/motion",
        "http://example.com/curated/motion",
        "https://example.com/curated/motion/%2e%2e/elsewhere",
        "https://user:pass@example.com/curated/motion",
        "",
    ],
)
def test_uncurated_discovery_location_is_rejected(registry, url):
    with pytest.raises(ValueError, match="discovery_url"):
        sources.validate_reference_source(reference(url))


def test_empty_registry_is_explicit_and_user_links_still_allowed(registry):
    registry.write_text('{"version":1,"sources":[]}')
    assert sources.reference_source_catalog()["status"] == "awaiting_curation"
    with pytest.raises(ValueError, match="curated"):
        sources.validate_reference_source(
            reference("https://example.com/curated/motion")
        )
    sources.validate_reference_source({"source": "user_supplied"})


def test_researcher_candidate_fields_do_not_autoapprove_an_unknown_source(registry):
    with pytest.raises(ValueError, match="curated"):
        sources.validate_reference_source(
            reference("https://example.com/curated/motion")
            | {"source_id": "agent_recommended"}
        )
