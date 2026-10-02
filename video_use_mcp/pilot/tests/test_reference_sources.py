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


@pytest.mark.parametrize(
    "source_id,discovery_url",
    [
        ("motion_awards", "https://motionawards.com/winners-2024.html"),
        ("motion_awards", "https://motionawards.com/winners-2016.html"),
        ("eyecannndy", "https://eyecannndy.com/technique/mixed-media"),
        ("eyecannndy", "https://eyecannndy.com/technique/digital-overlay"),
        ("art_of_the_title", "https://www.artofthetitle.com/style/3d/"),
        ("art_of_the_title", "https://www.artofthetitle.com/title/severance/"),
        ("art_of_the_title", "https://www.artofthetitle.com/titles/2022/"),
        ("art_of_the_title", "https://www.artofthetitle.com/designer/teddy-blanks/"),
        ("art_of_the_title", "https://www.artofthetitle.com/category/tv/"),
        ("stash", "https://www.stashmedia.tv/best-of-stash-2023-3d-style/"),
        ("stash", "https://www.stashmedia.tv/best-of-stash-2024-product-films/"),
        ("stash", "https://www.stashmedia.tv/tag/best-of-stash-2023/"),
        ("wine_after_coffee", "https://vimeo.com/channels/wineaftercoffee/123456"),
        ("vimeo_staff_picks", "https://vimeo.com/channels/premieres/123456"),
        ("vimeo_staff_picks", "https://vimeo.com/channels/bestofstaffpicks"),
        ("what_ships", "https://whatships.com/videos/example-launch/"),
        ("ordinary_folk", "https://www.ordinaryfolk.co/work/example"),
        ("ads_of_the_world", "https://www.adsoftheworld.com/campaigns/example"),
        ("ads_of_the_world", "https://www.adsoftheworld.com/industries/movies"),
        ("behance", "https://www.behance.net/search/projects/kinetic%20typography"),
        ("behance", "https://www.behance.net/gallery/123456/example"),
        ("the_pudding", "https://pudding.cool/2025/06/example/"),
    ],
)
def test_curated_archives_and_source_specific_routes_are_usable(
    source_id, discovery_url
):
    sources.validate_reference_source(
        reference(discovery_url) | {"source_id": source_id}
    )


@pytest.mark.parametrize(
    "source_id,discovery_url",
    [
        ("motion_awards", "https://motionawards.com/enter/"),
        ("motion_awards", "https://motionawards.com/winners-2025.html.evil"),
        ("motion_awards", "https://motionawards.com/winners-2025.html/elsewhere"),
        ("eyecannndy", "https://eyecannndy.com/resources"),
        ("eyecannndy", "https://eyecannndy.com/techniquefake/match-cut"),
        ("eyecannndy", "https://asset.eyecannndy.com/example.gif"),
        ("art_of_the_title", "https://www.artofthetitle.com/stylefake/"),
        ("stash", "https://www.stashmedia.tv/subscribe/"),
        ("stash", "https://www.stashmedia.tv/best-of-stash-not-a-year-product-films/"),
        (
            "stash",
            "https://www.stashmedia.tv/best-of-stash-2023-product-films/subscribe",
        ),
        ("wine_after_coffee", "https://vimeo.com/channels/premieres/123456"),
        ("wine_after_coffee", "https://vimeo.com/123456"),
        ("vimeo_staff_picks", "https://vimeo.com/channels/unrelated/123456"),
        ("vimeo_staff_picks", "https://vimeo.com/123456"),
        ("vimeo_staff_picks", "https://vimeo.com/channels/premieresfake/123456"),
        ("the_pudding", "https://www.youtube.com/@thepudding"),
        ("ordinary_folk", "https://www.ordinaryfolk.co/play"),
    ],
)
def test_curated_collection_does_not_open_unrelated_site_sections(
    source_id, discovery_url
):
    with pytest.raises(ValueError, match="discovery_url"):
        sources.validate_reference_source(
            reference(discovery_url) | {"source_id": source_id}
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/curated/motion/%252e%252e/elsewhere",
        "https://example.com/curated/motion/../elsewhere",
        "https://example.com/curated/motion/%2e%2e%2felsewhere",
        "https://example.com/curated/motion/%5c..%5celsewhere",
        "https://example.com/curated/motion\\..\\elsewhere",
        "https://example.com:8443/curated/motion",
        "https://@example.com/curated/motion",
    ],
)
def test_encoded_paths_ports_and_empty_userinfo_cannot_expand_collection(registry, url):
    with pytest.raises(ValueError, match="discovery_url"):
        sources.validate_reference_source(reference(url))


def test_explicit_https_default_port_preserves_same_collection(registry):
    sources.validate_reference_source(
        reference("https://example.com:443/curated/motion/example")
    )


def test_researched_registry_keeps_access_evidence_and_reserves_separate():
    catalog = sources.reference_source_catalog()
    assert len(catalog["sources"]) == 11
    assert catalog["source_count"] == 11
    assert catalog["status"] == "ready"
    assert catalog["checked_at"] == "2026-10-02"
    assert {item["verification"] for item in catalog["sources"]} == {
        "fetched",
        "indexed",
    }
    assert all(
        item["verification_evidence"] and item["access_notes"] and item["biases"]
        for item in catalog["sources"]
    )
    assert all("seed_examples" not in item for item in catalog["sources"])
    assert all(item["approved"] is False for item in catalog["reserves"])
    assert any(item["verification"] == "unverified" for item in catalog["reserves"])
    assert any(
        "No reference video was played" in item for item in catalog["evidence_policy"]
    )
    assert "no global quality or popularity ranking" in catalog["selection_policy"]
    for candidate in catalog["reserves"]:
        with pytest.raises(ValueError, match="curated"):
            sources.validate_reference_source(
                reference(candidate.get("url", "")) | {"source_id": candidate["id"]}
            )


def test_category_routing_is_compact_advice_not_an_allowlist():
    catalog = sources.reference_source_catalog("explainer", compact=True)
    assert [source["id"] for source in catalog["sources"]] == [
        "ordinary_folk",
        "wine_after_coffee",
    ]
    assert catalog["coverage"]["coverage"] == "good"
    assert catalog["matched_source_count"] == 2
    assert len(catalog["available_sources"]) == 11
    assert "not a browsing whitelist" in catalog["routing_policy"]
    assert "reserves" not in catalog
    assert all(
        "verification_evidence" not in item and "research_verification" not in item
        for item in catalog["sources"]
    )
    # A specific explainer may benefit from title design; a suggestion route
    # must not reject another approved collection when the agent discovers it.
    sources.validate_reference_source(
        reference("https://www.artofthetitle.com/style/3d/")
        | {"source_id": "art_of_the_title"}
    )


def test_unknown_categories_and_podcast_gap_do_not_invent_coverage():
    unknown = sources.reference_source_catalog("unusual_user_request", compact=True)
    assert unknown["sources"] == []
    assert unknown["coverage"]["coverage"] == "unmapped"
    assert len(unknown["available_sources"]) == 11
    gap = sources.reference_source_catalog("audio_first", compact=True)
    assert gap["sources"] == []
    assert gap["coverage"]["coverage"] == "gap"
    assert (
        gap["status"] == "ready"
    )  # The whole catalog exists; this category has a gap.
    nearby = sources.reference_source_catalog("document_video", compact=True)
    assert [source["id"] for source in nearby["sources"]] == ["the_pudding"]
    assert nearby["coverage"]["coverage"] == "gap"


@pytest.mark.parametrize(
    "change",
    [
        {"discovery_roots": ["http://example.com/collection"]},
        {"discovery_roots": ["https://localhost/collection"]},
        {"discovery_roots": ["https://user:pass@example.com/collection"]},
        {"discovery_roots": [], "discovery_patterns": []},
        {
            "discovery_patterns": [
                {"origin": "https://example.com/a", "path_regex": "/safe.*"}
            ]
        },
        {"discovery_patterns": [{"origin": "https://example.com", "path_regex": "/["}]},
        {"discovery_patterns": ["https://example.com/collection"]},
    ],
)
def test_invalid_curator_rules_fail_closed(registry, change):
    data = json.loads(registry.read_text())
    data["sources"][0].update(change)
    registry.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        sources.reference_source_catalog()
