"""An acknowledged defect must not become an acceptable export caveat."""

import pytest

from video_use_mcp.pilot.review_findings import (
    ReviewFinding,
    merge_review_findings,
    normalize_review_findings,
    require_resolved_review_findings,
)


SOLAR_MEANING = {
    "kind": "meaning",
    "description": (
        "The arrows are labeled electric field but point in the direction of "
        "force on the electrons."
    ),
}


def test_acknowledged_solar_semantics_cannot_be_exported_as_a_caveat():
    findings = normalize_review_findings([SOLAR_MEANING])
    with pytest.raises(ValueError, match="Export blocked.*meaning"):
        require_resolved_review_findings(findings)


def test_empty_retry_or_style_relabel_cannot_erase_recorded_defect():
    original = normalize_review_findings([SOLAR_MEANING])
    for update in (None, [], [SOLAR_MEANING | {"kind": "style"}]):
        merged = merge_review_findings(original, update)
        with pytest.raises(ValueError, match="1 unresolved"):
            require_resolved_review_findings(merged)


def test_explicit_resolution_preserves_record_and_permits_export():
    original = normalize_review_findings([SOLAR_MEANING | {"severity": "major"}])
    merged = merge_review_findings(original, [SOLAR_MEANING | {"resolved": True}])
    assert len(merged) == 1
    assert require_resolved_review_findings(merged) == [
        SOLAR_MEANING | {"resolved": True, "severity": "major"}
    ]
    # A later inspection can reopen an issue; resolution is not permanent.
    reopened = merge_review_findings(merged, [SOLAR_MEANING])
    with pytest.raises(ValueError, match="Export blocked"):
        require_resolved_review_findings(reopened)


@pytest.mark.parametrize("kind", ["correctness", "meaning", "layout", "audio"])
@pytest.mark.parametrize("severity", [None, "minor", "major", "critical"])
def test_reported_defects_are_not_excused_by_low_severity(kind, severity):
    with pytest.raises(ValueError, match="Export blocked"):
        require_resolved_review_findings(
            [
                {
                    "kind": kind,
                    "description": "A concrete unresolved issue",
                    "severity": severity,
                }
            ]
        )


def test_style_is_nonblocking_without_prose_keyword_inference():
    style = ReviewFinding(
        kind="style",
        description="Wrong color for my taste, but no content or readability defect.",
        severity="major",
    )
    assert require_resolved_review_findings([style])[0]["resolved"] is False


def test_older_clients_do_not_need_an_extra_approval_or_findings_call():
    assert normalize_review_findings(None) == []
    assert merge_review_findings(None, None) == []
    assert require_resolved_review_findings(None) == []


@pytest.mark.parametrize(
    "findings",
    [
        {"kind": "meaning", "description": "Not a list"},
        "all fine",
        [{"kind": "meaning", "description": "   "}],
        [SOLAR_MEANING | {"resolved": "false"}],
        [SOLAR_MEANING | {"resolved": 1}],
        [SOLAR_MEANING | {"kind": "approved"}],
        [SOLAR_MEANING | {"severity": "ignore"}],
        [SOLAR_MEANING | {"approval": True}],
        [SOLAR_MEANING] * 41,
    ],
)
def test_invalid_findings_fail_instead_of_silently_skipping_guard(findings):
    with pytest.raises(ValueError):
        normalize_review_findings(findings)


def test_whitespace_does_not_prevent_matching_an_explicit_resolution():
    merged = merge_review_findings(
        [SOLAR_MEANING],
        [
            SOLAR_MEANING
            | {
                "description": "  " + SOLAR_MEANING["description"] + "\n",
                "resolved": True,
            }
        ],
    )
    assert len(require_resolved_review_findings(merged)) == 1


def test_accumulated_records_have_a_bounded_size():
    previous = [
        {"kind": "style", "description": f"Optional preference {i}"} for i in range(40)
    ]
    with pytest.raises(ValueError, match="At most 40"):
        merge_review_findings(previous, [SOLAR_MEANING])
