# public entry point for the reusable manim explainer assets
# it re exports the teaching primitives so scripts can import them from one place

"""Reusable style-neutral Manim explainer assets."""

from .teaching import (
    LinkedValue,
    SemanticMobject,
    TeachingScene,
    TeachingThreeDScene,
    VisualTheme,
    fit_to_frame,
    theme_text,
)

__all__ = [
    "LinkedValue",
    "SemanticMobject",
    "TeachingScene",
    "TeachingThreeDScene",
    "VisualTheme",
    "fit_to_frame",
    "theme_text",
]
