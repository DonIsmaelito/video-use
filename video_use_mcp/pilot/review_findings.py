"""Keep an editor's acknowledged defects separate from optional style preferences.

These records are an editor's assessment, not automated factual verification.
The existing encoded-video inspection check remains a separate requirement.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_REVIEW_FINDINGS = 40


class ReviewFinding(BaseModel):
    """One concrete finding reported by the host assistant after inspection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["correctness", "meaning", "layout", "audio", "style"] = Field(
        description=(
            "correctness: factual or source errors; meaning: misleading visual "
            "relationships, arrows or labels; layout: clipping, overlap or "
            "unreadable content; audio: missing, unintelligible or mistimed audio; "
            "style: an optional aesthetic preference, not a known defect."
        )
    )
    description: str = Field(min_length=1, max_length=1200)
    resolved: bool = Field(
        default=False,
        description=(
            "True only after the issue has been corrected or reinspection has "
            "established that it is not a defect. To resolve a recorded finding, "
            "repeat its kind and description with resolved=true."
        ),
    )
    severity: Literal["minor", "major", "critical"] | None = Field(
        default=None,
        description=(
            "Optional prioritization. Even a minor acknowledged defect must be "
            "resolved before export; optional style preferences never block it."
        ),
    )

    @field_validator("description")
    @classmethod
    def nonblank_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A review finding needs a concrete description")
        return value


def normalize_review_findings(
    findings: Sequence[ReviewFinding | Mapping] | None,
) -> list[dict]:
    """Validate bounded structured input, allowing omitted findings for old clients."""
    if findings is None:
        return []
    if isinstance(findings, (str, bytes)) or not isinstance(findings, Sequence):
        raise ValueError("Review findings must be a list of structured findings")
    if len(findings) > MAX_REVIEW_FINDINGS:
        raise ValueError(f"At most {MAX_REVIEW_FINDINGS} review findings are allowed")
    return [
        ReviewFinding.model_validate(finding).model_dump(exclude_none=True)
        for finding in findings
    ]


def merge_review_findings(
    previous: Sequence[ReviewFinding | Mapping] | None,
    updates: Sequence[ReviewFinding | Mapping] | None,
) -> list[dict]:
    """Retain reported issues until explicitly resolved, including across retries.

    A finding's kind and trimmed description identify it. Omitting findings or
    supplying an empty list does not erase earlier issues. Relabeling a defect as
    style creates a separate finding and cannot silently dismiss the old one.
    """
    merged = {}
    for finding in normalize_review_findings(previous) + normalize_review_findings(
        updates
    ):
        key = finding["kind"], finding["description"]
        merged[key] = merged.get(key, {}) | finding
    if len(merged) > MAX_REVIEW_FINDINGS:
        raise ValueError(f"At most {MAX_REVIEW_FINDINGS} review findings are allowed")
    return list(merged.values())


def require_resolved_review_findings(
    findings: Sequence[ReviewFinding | Mapping] | None,
) -> list[dict]:
    """Reject explicitly acknowledged unresolved defects, without judging the video."""
    normalized = normalize_review_findings(findings)
    unresolved = [
        finding
        for finding in normalized
        if finding["kind"] != "style" and not finding["resolved"]
    ]
    if unresolved:
        examples = "; ".join(
            f"{finding['kind']}: {finding['description'][:200]}"
            for finding in unresolved[:3]
        )
        raise ValueError(
            f"Export blocked by {len(unresolved)} unresolved review finding(s): "
            f"{examples}. Correct and inspect the affected output, then repeat "
            "each finding's kind and description with resolved=true. Optional "
            "style preferences do not require approval."
        )
    return normalized
