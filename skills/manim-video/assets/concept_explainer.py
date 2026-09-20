"""Style-neutral foundations for narrated Manim concept explainers.

Copy this file into the video workspace, choose a topic-specific palette, and
append one ``TimedScene`` subclass per concept. The helpers encode production
invariants while leaving the visual metaphor and art direction to the author.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

from manim import (
    Arrow,
    BOLD,
    DOWN,
    FadeOut,
    Group,
    LEFT,
    NORMAL,
    RoundedRectangle,
    Scene,
    Text,
    UP,
    VGroup,
    config,
    rate_functions,
)


# Empty keeps the asset portable and lets Manim/Pango choose the platform default.
DEFAULT_FONT = ""
DEFAULT_TEXT_COLOR = "#F4F7FF"
MAX_STATIC_HOLD_S = 3.0
SAFE_FRAME_MARGIN = 0.25

# Stable convenience aliases for authored scenes. Manim does not expose these
# names directly through ``from manim import *`` in every supported release.
ease_out_cubic = rate_functions.ease_out_cubic
ease_in_out_cubic = rate_functions.ease_in_out_cubic


def label(
    text: str,
    size: float,
    *,
    color: str = DEFAULT_TEXT_COLOR,
    font: str = DEFAULT_FONT,
    weight: str = NORMAL,
) -> Text:
    return Text(text, font=font, font_size=size, color=color, weight=weight)


def scene_heading(
    kicker: str,
    title: str,
    *,
    accent: str,
    font: str = DEFAULT_FONT,
) -> VGroup:
    heading = VGroup(
        label(kicker.upper(), 18, color=accent, font=font, weight=BOLD),
        label(title, 36, font=font, weight=BOLD),
    ).arrange(DOWN, buff=0.12, aligned_edge=LEFT)
    return heading.to_corner(UP + LEFT, buff=0.6)


def panel(
    width: float,
    height: float,
    *,
    stroke: str,
    fill: str,
    fill_opacity: float = 0.92,
) -> RoundedRectangle:
    return RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.18,
        stroke_color=stroke,
        stroke_width=2,
        fill_color=fill,
        fill_opacity=fill_opacity,
    )


def worker_grid(
    rows: int,
    columns: int,
    *,
    color: str,
    cell_size: float = 0.34,
    gap: float = 0.1,
) -> VGroup:
    if rows < 1 or columns < 1:
        raise ValueError("worker grid dimensions must be positive")
    cells = VGroup(
        *[
            RoundedRectangle(
                width=cell_size,
                height=cell_size,
                corner_radius=0.05,
                stroke_color=color,
                stroke_width=1.4,
                fill_color=color,
                fill_opacity=0.12,
            )
            for _ in range(rows * columns)
        ]
    )
    cells.arrange_in_grid(rows=rows, cols=columns, buff=gap)
    return cells


def _rectangular_matrix(values: Sequence[Sequence[float]], name: str) -> list[list[float]]:
    matrix = [list(row) for row in values]
    if not matrix or not matrix[0]:
        raise ValueError(f"{name} matrix cannot be empty")
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError(f"{name} matrix must be rectangular")
    return matrix


def verified_matrix_product(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
    *,
    expected: Sequence[Sequence[float]] | None = None,
    absolute_tolerance: float = 1e-9,
) -> list[list[float]]:
    """Calculate a matrix product and optionally reject a mistyped expected result."""
    left_matrix = _rectangular_matrix(left, "left")
    right_matrix = _rectangular_matrix(right, "right")
    if len(left_matrix[0]) != len(right_matrix):
        raise ValueError("matrix dimensions are incompatible for multiplication")
    result = [
        [
            sum(left_matrix[row][inner] * right_matrix[inner][column] for inner in range(len(right_matrix)))
            for column in range(len(right_matrix[0]))
        ]
        for row in range(len(left_matrix))
    ]
    if expected is not None:
        expected_matrix = _rectangular_matrix(expected, "expected")
        same_shape = (
            len(expected_matrix) == len(result)
            and len(expected_matrix[0]) == len(result[0])
        )
        same_values = same_shape and all(
            math.isclose(
                float(result[row][column]),
                float(expected_matrix[row][column]),
                rel_tol=0.0,
                abs_tol=absolute_tolerance,
            )
            for row in range(len(result))
            for column in range(len(result[0]))
        )
        if not same_values:
            raise AssertionError(
                f"displayed matrix result {expected_matrix} does not match calculated result {result}"
            )
    return result


def verified_number(
    calculated: float,
    displayed: float,
    *,
    name: str = "displayed value",
    absolute_tolerance: float = 1e-9,
) -> float:
    """Return a calculated value after checking the number authored on screen."""
    calculated_value = float(calculated)
    if not math.isclose(
        calculated_value,
        float(displayed),
        rel_tol=0.0,
        abs_tol=absolute_tolerance,
    ):
        raise AssertionError(
            f"{name} {displayed} does not match calculated value {calculated_value}"
        )
    return calculated_value


def matrix_grid(
    values: Sequence[Sequence[Any]],
    *,
    color: str,
    cell_size: float = 0.72,
    font: str = DEFAULT_FONT,
) -> VGroup:
    matrix = [list(row) for row in values]
    if not matrix or not matrix[0] or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("matrix grid values must form a non-empty rectangle")
    cells = VGroup()
    for row in matrix:
        for value in row:
            box = RoundedRectangle(
                width=cell_size,
                height=cell_size,
                corner_radius=0.08,
                stroke_color=color,
                stroke_width=1.5,
                fill_color=color,
                fill_opacity=0.10,
            )
            number = label(str(value), 20, font=font)
            cells.add(VGroup(box, number))
    cells.arrange_in_grid(rows=len(matrix), cols=len(matrix[0]), buff=0.08)
    return cells


def flow_arrows(
    start: Any,
    end: Any,
    *,
    lanes: int,
    color: str,
    spread: float = 0.35,
) -> VGroup:
    if lanes < 1:
        raise ValueError("flow must contain at least one lane")
    offsets = [spread * (index - (lanes - 1) / 2) for index in range(lanes)]
    return VGroup(
        *[
            Arrow(
                start + UP * offset,
                end + UP * offset,
                buff=0.12,
                color=color,
                stroke_width=2.5,
                max_tip_length_to_length_ratio=0.12,
            )
            for offset in offsets
        ]
    )


def assert_text_within_safe_frame(
    mobjects: Sequence[Any],
    *,
    margin: float = SAFE_FRAME_MARGIN,
) -> None:
    """Reject active text whose visible bounds touch or cross the safe frame.

    The check walks nested groups and intentionally focuses on text-like Manim
    objects. Full-frame backgrounds and edge-to-edge structural shapes remain
    valid, while titles, labels, equations, and final payoff copy cannot be
    silently cropped in the rendered video.
    """
    if margin < 0:
        raise ValueError("safe-frame margin cannot be negative")
    frame_left = -float(config.frame_width) / 2 + margin
    frame_right = float(config.frame_width) / 2 - margin
    frame_bottom = -float(config.frame_height) / 2 + margin
    frame_top = float(config.frame_height) / 2 - margin
    text_class_names = {
        "Text", "MarkupText", "Paragraph", "Tex", "MathTex", "SingleStringMathTex"
    }
    seen: set[int] = set()
    for root in mobjects:
        family = root.get_family() if hasattr(root, "get_family") else [root]
        for member in family:
            if type(member).__name__ not in text_class_names or id(member) in seen:
                continue
            seen.add(id(member))
            left = float(member.get_left()[0])
            right = float(member.get_right()[0])
            bottom = float(member.get_bottom()[1])
            top = float(member.get_top()[1])
            violations: list[str] = []
            if left < frame_left:
                violations.append(f"left={left:.3f} < {frame_left:.3f}")
            if right > frame_right:
                violations.append(f"right={right:.3f} > {frame_right:.3f}")
            if bottom < frame_bottom:
                violations.append(f"bottom={bottom:.3f} < {frame_bottom:.3f}")
            if top > frame_top:
                violations.append(f"top={top:.3f} > {frame_top:.3f}")
            if violations:
                text = getattr(member, "text", type(member).__name__)
                raise ValueError(
                    f"text {text!r} exceeds the {margin:.2f}-unit safe frame: "
                    + ", ".join(violations)
                )


def load_alignment(path: str | Path) -> dict[str, Any]:
    alignment = json.loads(Path(path).read_text(encoding="utf-8"))
    words = alignment.get("words")
    if not isinstance(words, list) or not words:
        raise ValueError("alignment sidecar does not contain word timings")
    for index, word in enumerate(words):
        if not isinstance(word, dict) or not {"text", "start", "end"}.issubset(word):
            raise ValueError(f"alignment word {index} is missing text, start, or end")
        try:
            start = float(word["start"])
            end = float(word["end"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"alignment word {index} has invalid timing") from exc
        if start < 0 or end < start:
            raise ValueError(f"alignment word {index} has an invalid time range")
    return alignment


def _normalized_words(text: str) -> list[str]:
    return re.findall(r"[\w]+(?:['\u2019-][\w]+)*", text.casefold())


def phrase_window(
    alignment: dict[str, Any], phrase: str, *, occurrence: int = 1
) -> tuple[float, float]:
    """Return the spoken time range for a phrase in an alignment sidecar."""
    if occurrence < 1:
        raise ValueError("occurrence must be at least one")
    target = _normalized_words(phrase)
    if not target:
        raise ValueError("phrase must contain at least one word")
    timed_words = alignment.get("words") or []
    searchable_words: list[tuple[str, dict[str, Any]]] = []
    for index, timed_word in enumerate(timed_words):
        if not isinstance(timed_word, dict):
            raise ValueError(f"alignment word {index} is not an object")
        normalized = _normalized_words(str(timed_word.get("text", "")))
        searchable_words.extend((part, timed_word) for part in normalized)
    flattened = [part for part, _ in searchable_words]
    matches = 0
    for index in range(0, len(flattened) - len(target) + 1):
        if flattened[index:index + len(target)] != target:
            continue
        matches += 1
        if matches == occurrence:
            first_word = searchable_words[index][1]
            last_word = searchable_words[index + len(target) - 1][1]
            return (
                float(first_word["start"]),
                float(last_word["end"]),
            )
    raise ValueError(f"phrase not found in alignment: {phrase!r}")


def phrase_cue(
    alignment: dict[str, Any],
    phrase: str,
    *,
    scene_start_s: float,
    reveal_duration_s: float = 0.0,
    occurrence: int = 1,
) -> float:
    """Return scene-local reveal start so its landing meets the payoff phrase."""
    if scene_start_s < 0:
        raise ValueError("scene start cannot be negative")
    if reveal_duration_s < 0:
        raise ValueError("reveal duration cannot be negative")
    phrase_start, _ = phrase_window(alignment, phrase, occurrence=occurrence)
    return max(0.0, phrase_start - scene_start_s - reveal_duration_s)


class TimedScene(Scene):
    """Scene base that preserves the teaching frame until its final fade."""

    target_duration_s: float | None = None
    background_color = "#101010"
    max_static_hold_s = MAX_STATIC_HOLD_S

    def setup(self) -> None:
        super().setup()
        self.camera.background_color = self.background_color

    def remaining_time(self) -> float | None:
        if self.target_duration_s is None:
            return None
        return float(self.target_duration_s) - float(self.renderer.time)

    def hold(self, duration_s: float, *, purpose: str | None = None) -> None:
        if duration_s < 0:
            raise ValueError("hold duration cannot be negative")
        if duration_s > self.max_static_hold_s and not purpose:
            raise ValueError(
                f"static hold of {duration_s:.2f}s needs an explicit educational purpose"
            )
        if duration_s >= 1 / float(config.frame_rate):
            self.wait(duration_s)

    def wait_until(self, local_time_s: float, *, purpose: str | None = None) -> None:
        """Wait to a scene-local narration cue and reject cues already missed."""
        if local_time_s < 0:
            raise ValueError("cue time cannot be negative")
        wait_s = float(local_time_s) - float(self.renderer.time)
        frame_s = 1 / float(config.frame_rate)
        if wait_s < -frame_s:
            raise ValueError(f"narration cue was missed by {-wait_s:.2f}s")
        if wait_s > 0:
            self.hold(wait_s, purpose=purpose)

    def finish(
        self,
        *,
        fade: bool = True,
        fade_duration_s: float = 0.5,
        validate_safe_frame: bool = True,
        safe_frame_margin: float = SAFE_FRAME_MARGIN,
    ) -> None:
        """Fill the budget on the final teaching state, then fade without blank padding."""
        if fade_duration_s < 0:
            raise ValueError("fade duration cannot be negative")
        if validate_safe_frame:
            assert_text_within_safe_frame(
                self.mobjects,
                margin=safe_frame_margin,
            )
        remaining = self.remaining_time()
        if remaining is not None and remaining < -(1 / float(config.frame_rate)):
            raise ValueError(
                f"scene exceeds its target duration by {-remaining:.2f}s"
            )
        if not fade or not self.mobjects:
            if remaining is not None and remaining > 0:
                self.hold(remaining, purpose="final teaching frame")
            return
        actual_fade = fade_duration_s if remaining is None else min(fade_duration_s, max(0.0, remaining))
        pre_fade_hold = None if remaining is None else max(0.0, remaining - actual_fade)
        if pre_fade_hold:
            self.hold(pre_fade_hold, purpose="hold final teaching state through narration")
        if actual_fade >= 1 / float(config.frame_rate):
            self.play(
                *(FadeOut(mobject) for mobject in list(self.mobjects)),
                run_time=actual_fade,
            )
