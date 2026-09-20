from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "manim-video"
    / "scripts"
    / "narration_preflight.py"
)
SPEC = importlib.util.spec_from_file_location("narration_preflight", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
narration_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(narration_preflight)


def test_safety_margin_rejects_near_ceiling_estimate() -> None:
    text = " ".join(["word"] * 154)

    without_margin = narration_preflight.estimate(
        text,
        min_duration_s=55,
        max_duration_s=65,
        words_per_minute=145,
    )
    with_margin = narration_preflight.estimate(
        text,
        min_duration_s=55,
        max_duration_s=65,
        words_per_minute=145,
        safety_margin_s=3,
    )

    assert without_margin["estimated_in_range"] is True
    assert with_margin["estimated_in_range"] is False
    assert with_margin["planning_max_duration_s"] == 62
    assert with_margin["recommended_max_words"] == 149


@pytest.mark.parametrize("margin", [-1, 11])
def test_invalid_safety_margin_is_rejected(margin: float) -> None:
    with pytest.raises(ValueError, match="safety margin"):
        narration_preflight.estimate(
            "short narration",
            min_duration_s=55,
            max_duration_s=65,
            words_per_minute=145,
            safety_margin_s=margin,
        )
