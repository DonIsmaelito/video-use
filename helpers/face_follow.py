"""Compile measured face tracks to bounded FFmpeg crop runtime commands.

Cropping happens on original source pixels inside the normal segment encode.
No intermediate video, expression per keyframe, retiming or audio filter is
introduced. Ambiguous/lost evidence is a hard failure, never an inferred face.
"""
from __future__ import annotations

from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import tempfile

try:
    from .face_track import finite, probe_source, read_json, sha256, validate_track
    from .shot_layout import layout_dimensions
except ImportError:
    from face_track import finite, probe_source, read_json, sha256, validate_track
    from shot_layout import layout_dimensions


def _even_interval(low, high):
    low, high = math.ceil((low - 1e-8) / 2) * 2, math.floor((high + 1e-8) / 2) * 2
    if low > high:
        raise ValueError("Face and requested head margin do not fit an even-pixel crop")
    return low, high


def _position(desired, low, high, previous, delta, smoothing, deadzone, span, max_speed):
    desired = min(high, max(low, desired))
    if previous is None:
        value = desired
    else:
        distance = desired - previous
        if abs(distance) <= deadzone * span:
            distance = 0
        value = previous + distance * (1 if smoothing == 0 else 1 - math.exp(-delta / smoothing))
    value = min(high, max(low, round(value / 2) * 2))
    if previous is not None and abs(value - previous) > max_speed * span * delta + 2.00001:
        raise ValueError("Required face-follow motion exceeds max_pan_speed; split or use an explicit fixed layout")
    return int(value)


def compile_crop_plan(track, source, timeline, start, duration, layout, spec):
    """Validate evidence and produce source-frame crop positions for one EDL cut."""
    validate_track(track)
    if not isinstance(spec, dict) or set(spec) - {"track", "padding", "smoothing_seconds", "deadzone", "max_pan_speed"}:
        raise ValueError("face_follow supports track padding smoothing_seconds deadzone max_pan_speed")
    observed = track["observations"]
    claimed = observed["source"]
    for key in ("sha256", "bytes", "width", "height", "frame_count", "time_base", "format_start_time", "sample_aspect_ratio", "rotation"):
        if claimed.get(key) != source.get(key):
            raise ValueError(f"Face track does not match current source {key}")
    start = finite(start, "segment start", 0, 3600)
    duration = finite(duration, "segment duration", 1e-6, 120)
    end = start + duration
    shot = observed["shot"]
    if start < shot["start"] - 1e-7 or end > shot["end"] + 1e-7:
        raise ValueError("Requested cut crosses the explicit face-track shot bounds")
    width, height = layout_dimensions(layout)
    if layout.get("crop") is not None:
        raise ValueError("face_follow cannot combine with a second layout.crop")
    window = layout.get("window", {})
    target_width, target_height = window.get("width", width), window.get("height", height)
    if any(type(v) is not int or v < 2 or v % 2 for v in (target_width, target_height)):
        raise ValueError("Face-follow output window needs even positive dimensions")
    sw, sh = source["width"], source["height"]
    aspect = Fraction(target_width, target_height)
    multiple = math.floor(min(sw / aspect.numerator, sh / aspect.denominator) / 2) * 2
    cw, ch = aspect.numerator * multiple, aspect.denominator * multiple
    if multiple < 2:
        raise ValueError("Source cannot provide an exact even-pixel crop at this aspect ratio")
    padding = spec.get("padding", {})
    if not isinstance(padding, dict) or set(padding) - {"horizontal", "top", "bottom"}:
        raise ValueError("Face padding supports horizontal top bottom fractions of the detected box")
    px = finite(padding.get("horizontal", .2), "horizontal padding", 0, 1)
    pt = finite(padding.get("top", .4), "top padding", 0, 1)
    pb = finite(padding.get("bottom", .15), "bottom padding", 0, 1)
    smoothing = finite(spec.get("smoothing_seconds", .12), "smoothing_seconds", 0, 2)
    deadzone = finite(spec.get("deadzone", .04), "deadzone", 0, .25)
    max_speed = finite(spec.get("max_pan_speed", 3), "max_pan_speed", .1, 20)
    # FFmpeg subtracts the input seek offset after rescaling it onto the video
    # stream time base (nearest, ties away from zero). Simply subtracting float
    # seconds is late by up to half a source tick, enough to miss a crop command
    # at a frame boundary when the container has a nonzero start time.
    time_base = Fraction(source["time_base"])
    shift = (Fraction(source["format_start_time"]) + Fraction(f"{start:.6f}")) / time_base
    magnitude = abs(shift)
    rounded = (2 * magnitude.numerator + magnitude.denominator) // (2 * magnitude.denominator)
    shift_ticks = rounded if shift >= 0 else -rounded
    frames = [frame for frame in track["frames"] if frame["time"] < end - 1e-9 and frame["end"] > start + 1e-9]
    if not frames or frames[0]["time"] > start + 1e-7 or frames[-1]["end"] < end - 1e-7:
        raise ValueError("Face track has incomplete coverage of the requested cut")
    positions = []
    previous = None
    for frame in frames:
        actual = timeline[frame["index"]] if 0 <= frame["index"] < len(timeline) else {}
        if any(frame.get(key) != actual.get(key) for key in ("index", "pts", "time", "end")):
            raise ValueError("Face track frame PTS differ from actual decoded source timestamps")
        if frame["end"] - frame["time"] < 1 / 240:
            raise ValueError("Face-follow supports frame intervals of at least 1/240 second")
        if frame["state"] != "selected":
            raise ValueError(f"Face evidence is {frame['state']} at {frame['time']:.6f}s; use a new reviewed shot or explicit fallback")
        x, y, w, h = frame["bbox"]
        required = [x - px * w, y - pt * h, x + (1 + px) * w, y + (1 + pb) * h]
        if required[0] < 0 or required[1] < 0 or required[2] > sw or required[3] > sh:
            raise ValueError("Requested head margin extends outside the actual source; a crop cannot restore missing pixels")
        xlo, xhi = _even_interval(max(0, required[2] - cw), min(sw - cw, required[0]))
        ylo, yhi = _even_interval(max(0, required[3] - ch), min(sh - ch, required[1]))
        delta = frame["time"] - previous["source_time"] if previous else 0
        cx = _position(x + w / 2 - cw / 2, xlo, xhi, previous["x"] if previous else None,
                       delta, smoothing, deadzone, cw, max_speed)
        cy = _position(y + h / 2 - ch * .4, ylo, yhi, previous["y"] if previous else None,
                       delta, smoothing, deadzone, ch, max_speed)
        row = {"source_frame": frame["index"], "source_time": frame["time"], "source_end": frame["end"],
               "segment_time": float((frame["pts"] - shift_ticks) * time_base), "x": cx, "y": cy,
               "face_bbox": frame["bbox"], "required_bounds": required, "confidence": frame["confidence"]}
        positions.append(row)
        previous = row
    return {"schema": "video-use.face-crop-plan.v1", "source_sha256": source["sha256"],
            "observations_sha256": track["observations_sha256"], "selection": track["selection"],
            "shot": shot, "segment": {"start": start, "end": end},
            "source_size": [sw, sh], "crop_size": [cw, ch], "target_window_size": [target_width, target_height],
            "input_time_base": str(time_base), "input_pts_shift_ticks": shift_ticks,
            "settings": {"padding": {"horizontal": px, "top": pt, "bottom": pb}, "smoothing_seconds": smoothing,
                         "deadzone": deadzone, "max_pan_speed": max_speed},
            "method": "per-source-frame sendcmd crop in the normal segment encode; no audio or clock modification",
            "frames": positions}


def command_text(plan):
    """One bounded numeric command per changed position; no user expressions."""
    lines = []
    previous = None
    for frame in plan["frames"]:
        position = (frame["x"], frame["y"])
        if position == previous:
            continue
        # sendcmd parses microseconds. A 10 us lead prevents a rounded command
        # from missing its exact rational source-frame boundary by one frame.
        # Supported frame intervals are >= 1/240 s, much larger than this lead.
        time = max(0, frame["segment_time"] - .000010)
        lines.append(f"{time:.6f} crop@face_follow x {position[0]}, crop@face_follow y {position[1]};")
        previous = position
    return "\n".join(lines) + "\n"


@contextmanager
def prepared_crop(spec, source_path, start, duration, layout, output_path):
    """Own temporary filter commands and clean them even when FFmpeg fails."""
    if not isinstance(spec, dict) or not isinstance(spec.get("track"), (str, Path)):
        raise ValueError("face_follow.track must name a selected face-track JSON file")
    track_path = Path(spec["track"]).resolve()
    source_path, output_path = Path(source_path).resolve(), Path(output_path).resolve()
    if output_path in {source_path, track_path} or output_path.with_suffix(".face-follow.json") in {source_path, track_path}:
        raise ValueError("Face-follow output must not overwrite source footage or track evidence")
    track = read_json(track_path)
    source, timeline = probe_source(source_path)
    plan = compile_crop_plan(track, source, timeline, start, duration, layout, spec)
    commands = command_text(plan)
    plan["track_sha256"] = hashlib.sha256(track_path.read_bytes()).hexdigest()
    plan["commands_sha256"] = hashlib.sha256(commands.encode()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="video-use-face-follow-", dir="/tmp") as temporary:
        command_path = Path(temporary) / "crop.commands"
        command_path.write_text(commands)
        cw, ch = plan["crop_size"]
        first = plan["frames"][0]
        filters = f"sendcmd=filename={command_path},crop@face_follow={cw}:{ch}:{first['x']}:{first['y']}:exact=1"
        yield filters, plan
        if sha256(source_path) != source["sha256"] or sha256(track_path) != plan["track_sha256"]:
            raise ValueError("Source or track evidence changed during the face-follow encode")
