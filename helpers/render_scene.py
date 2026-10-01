#!/usr/bin/env python3
"""Render one editable, bounded 2D motion composition without authored code.

Geometry is local to each mark's origin. A parent's transform and opacity also
apply to its children; marks are painted in list order. Keyframes contain
absolute values, and omitted properties retain their preceding value. Easing
belongs to the outgoing key. Duration rounds up to an integral frame count.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / "skills" / "motion-design" / "runtime"
MAX_BYTES = 120_000
KINDS = {"text", "rect", "ellipse", "line", "polygon", "arc", "wave"}
EASINGS = {"linear", "inCubic", "outCubic", "inOutCubic", "smooth", "outBack"}
NUMBERS = {
    "x": (-7680, 7680, 0),
    "y": (-7680, 7680, 0),
    "w": (0, 3840, 100),
    "h": (0, 3840, 100),
    "size": (12, 240, 42),
    "stroke_width": (0, 40, 3),
    "radius": (0, 1920, 0),
    "opacity": (0, 1, 1),
    "rotation": (-3600, 3600, 0),
    "scale": (0, 8, 1),
    "start": (-3600, 3600, 0),
    "end": (-3600, 3600, 180),
    "cycles": (0.1, 30, 3),
    "phase": (-360000, 360000, 0),
}
MARK_KEYS = set(NUMBERS) | {
    "id",
    "kind",
    "color",
    "fill",
    "text",
    "font",
    "align",
    "points",
    "keyframes",
    "parent",
    "motion_path",
}


class SceneValidationError(ValueError):
    """A bounded collection of actionable scene errors, without partial writes."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join(errors))


def _number(value, label, low, high):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label} must be a finite number")
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def _keys(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unsupported {label} fields: {', '.join(sorted(unknown))}")


def _color(value, label):
    if not isinstance(value, str) or not re.fullmatch(
        r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3}(?:[0-9a-fA-F]{2})?)?|transparent", value
    ):
        raise ValueError(f"{label} must be a hex color or transparent")
    return value


def _keyframes(raw, index, duration):
    label = f"marks[{index}] (id={repr(raw.get('id'))[:80]})"
    keys = raw.get("keyframes", [])
    if not isinstance(keys, list) or len(keys) > 24:
        return [], [f"{label}.keyframes must be a list of at most 24 keyframes"]
    normalized, errors, previous = [], [], -1
    for key_index, key in enumerate(keys):
        key_label = f"{label}.keyframes[{key_index}]"
        try:
            _keys(key, set(NUMBERS) | {"time", "ease"}, key_label)
            time_label = (
                f"{key_label}.time={repr(key.get('time'))[:80]} "
                f"(scene duration {duration:g}s)"
            )
            when = _number(key.get("time"), time_label, 0, duration)
            if when <= previous:
                raise ValueError(
                    f"{time_label} must be greater than the previous keyframe time "
                    f"{previous:g}s; keyframe times must be strictly increasing"
                )
            previous = when
            curve = key.get("ease", "inOutCubic")
            if not isinstance(curve, str) or curve not in EASINGS:
                raise ValueError(f"{key_label}.ease is an unknown easing")
            k = {"time": when, "ease": curve}
            # Stable field ordering preserves exact retries after restarts.
            for prop in NUMBERS:
                if prop in key:
                    low, high, _ = NUMBERS[prop]
                    k[prop] = _number(key[prop], f"{key_label}.{prop}", low, high)
            if raw.get("kind") == "text" and any(
                k.get(prop, 1) < 1 for prop in ("w", "h")
            ):
                raise ValueError(
                    f"{key_label}: animated text bounds must remain positive"
                )
            normalized.append(k)
        except ValueError as error:
            errors.append(str(error))
    return normalized, errors


def _motion_path(value, label, duration):
    allowed = {
        "points",
        "seconds",
        "start",
        "loop",
        "closed",
        "count",
        "stagger",
        "orient",
    }
    _keys(value, allowed, label)
    points = value.get("points")
    if not isinstance(points, list) or not 2 <= len(points) <= 200:
        raise ValueError(f"{label}.points needs 2–200 points")
    out = {"points": []}
    for index, point in enumerate(points):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"{label}.points[{index}] must contain x and y")
        out["points"].append(
            [_number(v, f"{label}.points[{index}]", -7680, 7680) for v in point]
        )
    if sum(math.dist(a, b) for a, b in zip(out["points"], out["points"][1:])) <= 0:
        raise ValueError(f"{label} needs a path with positive length")
    out["seconds"] = _number(value.get("seconds"), f"{label}.seconds", 1 / 120, 120)
    out["start"] = _number(value.get("start", 0), f"{label}.start", 0, duration)
    count = _number(value.get("count", 1), f"{label}.count", 1, 32)
    if int(count) != count:
        raise ValueError(f"{label}.count must be an integer")
    out["count"] = int(count)
    for key in ("loop", "closed", "orient"):
        out[key] = value.get(key, False)
        if not isinstance(out[key], bool):
            raise ValueError(f"{label}.{key} must be a boolean")
    default_stagger = out["seconds"] / count if out["loop"] else 0
    out["stagger"] = _number(
        value.get("stagger", default_stagger), f"{label}.stagger", 0, 120
    )
    return out


def validate_scene(value: dict) -> dict:
    """Validate untrusted data and return a detached scene with stable defaults."""
    _keys(value, {"duration", "width", "height", "fps", "background", "marks"}, "scene")
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise ValueError("Scene data exceeds 120 KB; author one smaller motion excerpt")
    fps = _number(value.get("fps", 15), "fps", 1, 30)
    if int(fps) != fps:
        raise ValueError("fps must be an integer")
    duration = _number(value.get("duration"), "duration", 0.1, 20)
    out = {"duration": math.ceil(duration * fps - 1e-9) / fps, "fps": int(fps)}
    for key, default in (("width", 960), ("height", 540)):
        number = _number(value.get(key, default), key, 180, 1920)
        if int(number) != number or int(number) % 2:
            raise ValueError(f"{key} must be an even integer")
        out[key] = int(number)
    out["background"] = _color(value.get("background", "#11141e"), "background")
    marks = value.get("marks")
    if not isinstance(marks, list) or not 1 <= len(marks) <= 100:
        raise ValueError("Provide 1 to 100 marks")
    keyframe_data = {
        index: _keyframes(raw, index, out["duration"])
        for index, raw in enumerate(marks)
        if isinstance(raw, dict)
    }
    errors = [error for _, errors in keyframe_data.values() for error in errors]
    if errors:
        raise SceneValidationError(errors)
    ids, clean = set(), []
    for index, raw in enumerate(marks):
        label = f"marks[{index}]"
        _keys(raw, MARK_KEYS, label)
        ident = raw.get("id")
        if (
            not isinstance(ident, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", ident)
            or ident in ids
        ):
            raise ValueError(
                "Every mark needs a unique id of letters, digits, underscores or hyphens"
            )
        ids.add(ident)
        kind = raw.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError(f"{label}.kind is unsupported")
        m = {"id": ident, "kind": kind}
        for key, (low, high, default) in NUMBERS.items():
            if kind == "text" and key in {"w", "h"}:
                default = 560 if key == "w" else 100
            m[key] = _number(raw.get(key, default), f"{label}.{key}", low, high)
        m["color"] = _color(raw.get("color", "#ffffff"), f"{label}.color")
        m["fill"] = (
            None if raw.get("fill") is None else _color(raw["fill"], f"{label}.fill")
        )
        m["text"] = raw.get("text", "")
        if not isinstance(m["text"], str) or len(m["text"]) > 500:
            raise ValueError(f"{label}.text must be at most 500 characters")
        m["font"], m["align"] = raw.get("font", "sans"), raw.get("align", "left")
        if m["font"] not in ("sans", "bold", "serif") or m["align"] not in (
            "left",
            "center",
            "right",
        ):
            raise ValueError(f"{label} has an unsupported font or alignment")
        if kind == "text" and (m["w"] < 1 or m["h"] < 1):
            raise ValueError("Text needs positive width and height for fitting")
        points = raw.get("points", [])
        if not isinstance(points, list) or len(points) > 200:
            raise ValueError(f"{label}.points must contain at most 200 points")
        m["points"] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError("Each point must contain x and y")
            m["points"].append([_number(v, "point", -7680, 7680) for v in point])
        if kind == "polygon" and len(m["points"]) < 3:
            raise ValueError("Polygons need at least three points")
        if kind == "line" and not m["points"]:
            m["points"] = [[0, 0], [m["w"], m["h"]]]
        if kind == "line" and len(m["points"]) < 2:
            raise ValueError("Lines need at least two points")
        parent = raw.get("parent")
        if parent is not None and (not isinstance(parent, str) or parent == ident):
            raise ValueError("parent must name a different mark")
        m["parent"] = parent
        m["keyframes"] = keyframe_data[index][0]
        if raw.get("motion_path") is not None:
            m["motion_path"] = _motion_path(
                raw["motion_path"],
                f"{label} (id={ident!r}).motion_path",
                out["duration"],
            )
        clean.append(m)
    lookup = {m["id"]: m for m in clean}
    for m in clean:
        seen, parent = {m["id"]}, m["parent"]
        while parent is not None:
            if parent not in lookup or parent in seen:
                raise ValueError("Parents must exist and may not form cycles")
            if lookup[parent].get("motion_path", {}).get("count", 1) > 1:
                raise ValueError(
                    f"Parent {parent!r} has repeated path instances; attach children to a single-instance mark"
                )
            seen.add(parent)
            if len(seen) > 8:
                raise ValueError("Parent transforms may be at most eight levels deep")
            parent = lookup[parent]["parent"]
    out["marks"] = clean
    if sum(m.get("motion_path", {}).get("count", 1) for m in clean) > 400:
        raise ValueError("A scene may contain at most 400 expanded path instances")
    if len(json.dumps(out, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise ValueError(
            "Normalized scene exceeds 120 KB; author one smaller motion excerpt"
        )
    return out


def scene_validation_report(value):
    """Cheap, read-only preflight. No files, subprocesses or renderer are used."""
    try:
        scene = validate_scene(value)
    except (ValueError, TypeError, OverflowError) as error:
        return {"valid": False, "errors": getattr(error, "errors", [str(error)])}
    return {
        "valid": True,
        "errors": [],
        "duration": scene["duration"],
        "frame_count": round(scene["duration"] * scene["fps"]),
        "marks": len(scene["marks"]),
        "instances": sum(
            m.get("motion_path", {}).get("count", 1) for m in scene["marks"]
        ),
    }


def prepare_scene(value: dict, directory: Path) -> dict:
    """Write data and fixed trusted runtime separately; never interpolate HTML."""
    scene = validate_scene(value)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "scene.json").write_text(
        json.dumps(scene, ensure_ascii=False, indent=2)
    )
    shutil.copyfile(HERE / "scene_runtime.mjs", directory / "scene_runtime.mjs")
    shutil.copyfile(RUNTIME / "motion.mjs", directory / "motion.mjs")
    (directory / "index.html").write_text(
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        "html,body{margin:0;overflow:hidden}canvas{display:block;width:100vw;height:100vh}"
        '</style></head><body><canvas id="scene"></canvas><script type="module">'
        'import {boot} from "./scene_runtime.mjs";boot();</script></body></html>'
    )
    return scene


def render_scene(
    value: dict,
    output: Path,
    *,
    audio: Path | None = None,
    audio_start=0,
    overwrite=False,
    chrome=None,
    deps=None,
    output_width=None,
    output_height=None,
    output_fps=None,
) -> dict:
    output = output.resolve()
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must end in .mp4")
    if output.exists() and not overwrite:
        raise ValueError("Output exists; provide --overwrite intentionally")
    _number(audio_start, "audio start", 0, 86400)
    if audio_start and audio is None:
        raise ValueError("Audio start requires an audio source")
    scene = validate_scene(value)
    width = scene["width"] if output_width is None else output_width
    height = scene["height"] if output_height is None else output_height
    fps = scene["fps"] if output_fps is None else output_fps
    for name, value in (("output_width", width), ("output_height", height)):
        _number(value, name, 180, 3840)
        if int(value) != value or value % 2:
            raise ValueError(f"{name} must be an even integer")
    _number(fps, "output_fps", 1, 30)
    if int(fps) != fps:
        raise ValueError("output_fps must be an integer")
    if width * scene["height"] != height * scene["width"]:
        raise ValueError(
            "Output dimensions must preserve the authored scene aspect ratio"
        )
    if width * height > 8_294_400:
        raise ValueError("Output exceeds 8,294,400 pixels")
    duration = math.ceil(scene["duration"] * fps - 1e-9) / fps
    directory = output.with_suffix(".scene")
    prepare_scene(scene, directory)
    audio_source = None
    if audio is not None:
        audio = audio.resolve(strict=True)
        audio_source = directory / "narration.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(audio_start),
                "-i",
                str(audio),
                "-t",
                str(duration),
                "-vn",
                "-ac",
                "2",
                "-ar",
                "48000",
                str(audio_source),
            ],
            check=True,
            stdout=sys.stderr,
        )
    command = [
        "node",
        str(HERE / "motion_render.mjs"),
        str(directory / "index.html"),
        "-o",
        str(output),
        "--duration",
        str(duration),
        "--width",
        str(width),
        "--height",
        str(height),
        "--fps",
        str(fps),
        "--deps",
        str(deps or RUNTIME),
        "--crf",
        "20",
        "--preset",
        "veryfast",
    ]
    if audio_source:
        command.extend(["--audio", str(audio_source)])
    if overwrite:
        command.append("--overwrite")
    if chrome:
        command.extend(["--chrome", str(chrome)])
    subprocess.run(command, check=True, stdout=sys.stderr)
    manifest_path = output.with_suffix(".render") / "render.json"
    manifest = json.loads(manifest_path.read_text())
    return {
        "output": str(output),
        "duration": duration,
        "frame_count": round(duration * fps),
        "width": width,
        "height": height,
        "fps": fps,
        "source": str(directory / "scene.json"),
        "manifest": str(manifest_path),
        "warnings": manifest.get("warnings", []),
        "audio_source": str(audio) if audio else None,
        "audio_start": audio_start,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Report all invalid keyframes without rendering or writing files",
    )
    parser.add_argument("--output-width", type=int)
    parser.add_argument("--output-height", type=int)
    parser.add_argument("--output-fps", type=int)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--audio-start", type=float, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--chrome")
    parser.add_argument("--deps", type=Path)
    args = parser.parse_args()
    try:
        # Pretty-printed editable JSON can be larger than its validated data.
        if args.scene.stat().st_size > 1_000_000:
            raise ValueError("Scene JSON file exceeds 1 MB")
        value = json.loads(args.scene.read_text())
    except (OSError, UnicodeError, ValueError) as error:
        if args.validate:
            print(json.dumps({"valid": False, "errors": [str(error)]}))
            return 2
        parser.error(str(error))
    if args.validate:
        report = scene_validation_report(value)
        print(json.dumps(report))
        return 0 if report["valid"] else 2
    if args.output is None:
        parser.error("-o/--output is required unless --validate is used")
    result = render_scene(
        value,
        args.output,
        audio=args.audio,
        audio_start=args.audio_start,
        overwrite=args.overwrite,
        chrome=args.chrome,
        deps=args.deps,
        output_width=args.output_width,
        output_height=args.output_height,
        output_fps=args.output_fps,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    raise SystemExit(main())
