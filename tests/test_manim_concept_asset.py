from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


manim = pytest.importorskip("manim")


ASSET_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "manim-video"
    / "assets"
    / "concept_explainer.py"
)
SPEC = importlib.util.spec_from_file_location("concept_explainer_asset", ASSET_PATH)
assert SPEC is not None and SPEC.loader is not None
concept_explainer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(concept_explainer)


def test_safe_frame_accepts_nested_text_with_margin() -> None:
    text = manim.Text("FRAME SAFE", font_size=36)
    nested = manim.Group(manim.RoundedRectangle(width=4, height=2), text)

    concept_explainer.assert_text_within_safe_frame([nested], margin=0.25)


def test_safe_frame_rejects_clipped_payoff_text() -> None:
    text = manim.Text("AI ACCELERATION", font_size=48)
    text.move_to(manim.DOWN * (float(manim.config.frame_height) / 2))

    with pytest.raises(ValueError, match="AI.?ACCELERATION.*safe frame"):
        concept_explainer.assert_text_within_safe_frame([text], margin=0.25)


def test_safe_frame_rejects_negative_margin() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        concept_explainer.assert_text_within_safe_frame([], margin=-0.1)


def test_matrix_grid_cells_are_vgroup_compatible() -> None:
    matrix = concept_explainer.matrix_grid([[1, 2], [3, 4]], color="#42E8E0")
    selected = manim.VGroup(matrix[0], matrix[1])

    assert isinstance(matrix, manim.VGroup)
    assert all(isinstance(cell, manim.VGroup) for cell in matrix)
    assert len(selected) == 2


def test_portable_easing_aliases_match_manim() -> None:
    assert concept_explainer.ease_out_cubic is manim.rate_functions.ease_out_cubic
    assert concept_explainer.ease_in_out_cubic is manim.rate_functions.ease_in_out_cubic
