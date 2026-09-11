"""Cursor styling with explicit provenance for a genuinely cursor-free recording."""
from __future__ import annotations

import math
from pathlib import Path
from urllib.parse import unquote, urlparse


DEFAULT_CURSOR = {"mode": "baked"}
RECORDED_DEFAULTS = {
    "mode": "recorded", "size": 4.5, "smoothing": 0.67,
    "motion_blur": 0.2, "click_bounce": 1.0, "interaction_zooms": True,
    "zoom_depth": 1,
}


def validate_cursor_spec(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("cursor must be an object")
    unknown = raw.keys() - RECORDED_DEFAULTS.keys()
    if unknown:
        raise ValueError(f"Unknown cursor keys: {', '.join(sorted(unknown))}")
    mode = raw.get("mode", "baked")
    if mode not in {"baked", "recorded"}:
        raise ValueError("cursor.mode must be baked or recorded")
    if mode == "baked":
        if raw.keys() - {"mode"}:
            raise ValueError("Cursor effects require mode recorded and an editable-overlay capture")
        return dict(DEFAULT_CURSOR)
    result = {**RECORDED_DEFAULTS, **raw}
    for key, low, high in (("size", .5, 10), ("smoothing", 0, 1),
                           ("motion_blur", 0, 1), ("click_bounce", 0, 5)):
        value = result[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not low <= value <= high):
            raise ValueError(f"cursor.{key} must be a finite number between {low} and {high}")
    if type(result["interaction_zooms"]) is not bool:
        raise ValueError("cursor.interaction_zooms must be boolean")
    if type(result["zoom_depth"]) is not int or not 1 <= result["zoom_depth"] <= 6:
        raise ValueError("cursor.zoom_depth must be an integer from 1 to 6")
    return result


def validate_capture_project(project: dict, project_path: Path, source: Path) -> Path:
    """Check recorder provenance; sidecar presence alone cannot prove a hidden cursor.

    This verifies the recorder's declared contract, not the absence of a cursor
    in arbitrary pixels. Pass its original returned project, never a hand-edited
    mode assertion. Browser Harness must still test its actual capture path.
    """
    if not isinstance(project, dict) or project.get("version") != 2:
        raise ValueError("Expected the original OpenScreen v2 recording project")
    media = project.get("media", {})
    if not isinstance(media, dict) or media.get("cursorCaptureMode") != "editable-overlay":
        raise ValueError("Recording project must declare real editable-overlay capture")
    raw_path = media.get("screenVideoPath")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("Recording project is missing screenVideoPath")
    if raw_path.startswith("file:"):
        url = urlparse(raw_path)
        if url.netloc not in {"", "localhost"}:
            raise ValueError("Recording must reference a local video")
        path = Path(unquote(url.path))
    else:
        path = Path(raw_path)
    if not path.is_absolute():
        path = project_path.parent / path
    if path.resolve(strict=True) != source.resolve(strict=True):
        raise ValueError("Recording project references a different source video")
    sidecar = Path(str(source.resolve()) + ".cursor.json")
    if not sidecar.is_file():
        raise ValueError(f"Editable recording is missing its cursor sidecar: {sidecar}")
    return sidecar


def editor_cursor_settings(cursor: dict) -> dict:
    if cursor["mode"] == "baked":
        return {"cursorShow": False}
    return {"cursorShow": True, "cursorSize": cursor["size"],
            "cursorSmoothing": cursor["smoothing"],
            "cursorMotionBlur": cursor["motion_blur"],
            "cursorClickBounce": cursor["click_bounce"], "cursorClipToBounds": False}
