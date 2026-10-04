"""Bounded production evidence for choosing references, not a template bank.

An installed renderer is not a quality benchmark. Historical outputs establish
particular visual mechanisms and keep their original runtime/review limitations.
"""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _catalog():
    return json.loads(
        (Path(__file__).parent / "references" / "production-evidence.json").read_text()
    )


def production_context():
    """Give the searching host enough evidence without another discovery call."""
    catalog = _catalog()
    return {
        "version": catalog["version"],
        "policy": (
            "Match the reference's defining action/composition to supported methods "
            "and evidence before recommending it. Record production_plan with method, "
            "treatment, evidence_ids, asset_requirements, adaptations and confidence. "
            "Installed methods alone require confidence=requires_sample. Historical "
            "examples prove only the described mechanism, not exact cloning or speed. "
            "Do not offer a reference whose defining look needs unavailable assets or "
            "effects unless a concrete adaptation is disclosed before the user chooses. "
            "Source software is not a filter: a Blender-authored simple object may be "
            "reproducible in Three.js; a photoreal city is not proved by a toy planet. "
            "Search fresh references for the brief; these examples are internal evidence."
        ),
        "runtime": deepcopy(catalog["runtime"]),
        "examples": [
            {key: example[key] for key in (
                "id", "methods", "origin", "supports", "limits"
            )}
            for example in catalog["examples"]
        ],
        "review_scope": catalog["review_scope"],
        "details": "video_use_guidance topic=production-evidence",
    }


def production_evidence_details():
    return json.dumps(_catalog(), ensure_ascii=False, indent=2)


def validate_production_plan(plan):
    """Check evidence identity and scope; artistic similarity is still reviewed."""
    catalog = _catalog()
    method = plan.get("method")
    runtime = {item["id"]: item for item in catalog["runtime"]}
    examples = {item["id"]: item for item in catalog["examples"]}
    known = runtime | examples
    ids = plan.get("evidence_ids", [])
    if method not in {item["method"] for item in runtime.values()}:
        raise ValueError("Choose an available production method")
    if not ids or len(ids) != len(set(ids)) or any(item not in known for item in ids):
        raise ValueError("Use distinct known production evidence IDs from production_context")
    for evidence_id in ids:
        item = known[evidence_id]
        methods = item.get("methods", [item.get("method")])
        if method not in methods:
            raise ValueError("Production evidence must support the selected method")
    if plan.get("confidence") == "demonstrated" and not any(
        evidence_id in examples for evidence_id in ids
    ):
        raise ValueError("Demonstrated production needs a stored example; runtime alone requires_sample")
    # Free-text treatment is intentionally not keyword-scored. The host must
    # inspect the candidate, disclose gaps, then prove the fit in the snippet.
