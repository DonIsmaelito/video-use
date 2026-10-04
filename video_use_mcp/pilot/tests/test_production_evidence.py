"""Keep production claims bound to the actual archived output provenance."""

import json
from pathlib import Path

from video_use_mcp.pilot.production_evidence import production_context
from video_use_mcp.pilot.tests.test_cards import rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_served_evidence_matches_saved_outputs_without_starting_worker(pilot):
    result = rpc(pilot, "tools/call", {
        "name": "video_use_guidance", "arguments": {"topic": "production-evidence"}
    })
    assert not result.get("isError"), result
    evidence = json.loads(result["content"][0]["text"])
    root = Path(__file__).resolve().parents[3]
    sources = {item["id"]: item for item in json.loads(
        (root / "website/data/media-sources.json").read_text()
    )}
    for example in evidence["examples"]:
        record = sources[example["id"]]
        assert example["sha256"] == record["websiteSha256"]
        assert example["video"] in {item["url"] for item in record["websiteAssets"]}
    binary = next(x for x in evidence["examples"] if x["id"] == "lane-1-ee1aba7e491f")
    assert not binary["methods"]  # Its original renderer has not been established.
    assert "No continuous motion/listening" in evidence["review_scope"]


def test_capabilities_and_intake_share_one_evidence_contract(pilot):
    result = rpc(pilot, "tools/call", {
        "name": "video_use_capabilities", "arguments": {}
    })
    assert not result.get("isError"), result
    context = json.loads(result["content"][0]["text"])["production_context"]
    assert context == production_context()
    # Detailed prompts and source URLs stay out of repeated intake responses.
    assert all("prompt" not in item and "video" not in item for item in context["examples"])
