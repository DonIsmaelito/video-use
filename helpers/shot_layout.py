"""Bounded source crops and picture windows for per-shot video layouts.

All authored coordinates are explicit even pixels. This module builds video
filters only; the existing renderer owns seeking, grading, frame rate and audio.
"""

from __future__ import annotations

import copy
import re
from typing import Any


def _pixel(value: Any, label: str, *, minimum: int = 0, maximum: int = 16384) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value % 2 or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an even integer between {minimum} and {maximum}")
    return value


def layout_dimensions(layout: dict) -> tuple[int, int]:
    if not isinstance(layout, dict):
        raise ValueError("range layout must be an object")
    return (_pixel(layout.get("width"), "layout.width", minimum=2, maximum=7680),
            _pixel(layout.get("height"), "layout.height", minimum=2, maximum=7680))


def build_shot_layout_filters(
    layout: dict, source_width: int, source_height: int, *, max_dimension: int | None = None,
) -> tuple[str, str]:
    """Return source crop and final layout filters, for before/after grading.

    A range uses ``layout: {width, height, crop?, window?, background?}``.
    Crop defaults to the whole source. Window defaults to the whole canvas;
    it accepts x/y/width/height and fit cover|contain. Source pixel coordinates
    never scale for previews; only canvas/window pixels scale together.
    """
    width, height = layout_dimensions(layout)
    allowed = {"width", "height", "crop", "window", "background"}
    if set(layout) - allowed:
        raise ValueError("Unknown layout fields: " + ", ".join(sorted(set(layout) - allowed)))
    if not isinstance(source_width, int) or not isinstance(source_height, int) or min(source_width, source_height) < 2:
        raise ValueError("Source dimensions must be positive decoded pixel dimensions")
    crop = layout.get("crop")
    if crop is None:
        crop_filter = ""
    else:
        if not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}:
            raise ValueError("layout.crop needs x y width height in source pixels")
        x, y = (_pixel(crop[name], f"layout.crop.{name}") for name in ("x", "y"))
        cw, ch = (_pixel(crop[name], f"layout.crop.{name}", minimum=2) for name in ("width", "height"))
        if x + cw > source_width or y + ch > source_height:
            raise ValueError("layout.crop extends outside the source frame")
        crop_filter = f"crop={cw}:{ch}:{x}:{y}"

    raw_window = layout.get("window", {})
    if not isinstance(raw_window, dict) or set(raw_window) - {"x", "y", "width", "height", "fit"}:
        raise ValueError("layout.window supports x y width height and fit only")
    window = copy.deepcopy(raw_window)
    window.setdefault("x", 0)
    window.setdefault("y", 0)
    window.setdefault("width", width)
    window.setdefault("height", height)
    for key in ("x", "y", "width", "height"):
        window[key] = _pixel(window[key], f"layout.window.{key}", minimum=2 if key in {"width", "height"} else 0)
    if window["x"] + window["width"] > width or window["y"] + window["height"] > height:
        raise ValueError("layout.window extends outside the canvas")
    fit = window.get("fit", "cover")
    if fit not in {"cover", "contain"}:
        raise ValueError("layout.window.fit must be cover or contain")
    color = layout.get("background", "#000000")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("layout.background must use #RRGGBB")
    color = "0x" + color[1:]

    if max_dimension is not None:
        _pixel(max_dimension, "max_dimension", minimum=2, maximum=7680)
        factor = min(1.0, max_dimension / max(width, height))
        width, height = max(2, int(width * factor / 2) * 2), max(2, int(height * factor / 2) * 2)
        for key in ("x", "y", "width", "height"):
            minimum = 2 if key in {"width", "height"} else 0
            window[key] = max(minimum, int(window[key] * factor / 2) * 2)
        if window["x"] + window["width"] > width or window["y"] + window["height"] > height:
            raise ValueError("Preview dimensions cannot represent this picture window")

    ww, wh, x, y = (window[key] for key in ("width", "height", "x", "y"))
    mode = "increase" if fit == "cover" else "decrease"
    filters = [f"scale={ww}:{wh}:force_original_aspect_ratio={mode}:force_divisible_by=2"]
    if fit == "cover":
        filters.append(f"crop={ww}:{wh}")
    else:
        filters.append(f"pad={ww}:{wh}:(ow-iw)/2:(oh-ih)/2:color={color}")
    filters.extend([f"pad={width}:{height}:{x}:{y}:color={color}", "setsar=1"])
    return crop_filter, ",".join(filters)
