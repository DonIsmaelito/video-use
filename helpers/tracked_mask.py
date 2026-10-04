"""Opaque, explicitly authored rectangles on the source clock of a silent edit.

This applies known geometry; it does not find sensitive content or certify that
an author supplied every required mask. The input must already have its cuts,
square pixels, fixed frame rate and final geometry. No scaling or audio changes
are hidden in this step.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np


FIELDS = {"version", "source", "source_sha256", "width", "height", "fps", "audio",
          "ranges", "tracks", "color"}
TRACK_FIELDS = {"name", "intervals", "keyframes", "clip"}


def number(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return float(value)


def rectangle(value, width, height, label, *, clip=False):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{label} must be [x, y, width, height]")
    x, y, w, h = [number(v, label, -8192, 8192) for v in value]
    if w <= 0 or h <= 0:
        raise ValueError(f"{label} needs positive width and height")
    if clip and (x < 0 or y < 0 or x + w > width or y + h > height):
        raise ValueError("clip must stay within the input frame")
    return [x, y, w, h]


def validate_config(config):
    """Validate all clocks and geometry before a decoder or encoder is started."""
    if not isinstance(config, dict) or set(config) - FIELDS:
        raise ValueError("Config contains unsupported fields")
    spec = dict(config)
    if type(spec.get("version")) is not int or spec["version"] != 1:
        raise ValueError("version must be 1")
    if not isinstance(spec.get("source"), str) or not spec["source"]:
        raise ValueError("source must name a local edited video")
    if not isinstance(spec.get("source_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", spec["source_sha256"]):
        raise ValueError("source_sha256 must bind this mask plan to its edited input")
    for key in ("width", "height"):
        if type(spec.get(key)) is not int or not 64 <= spec[key] <= 4096 or spec[key] % 2:
            raise ValueError(f"{key} must be an even integer from 64 through 4096")
    if spec["width"] * spec["height"] > 8_388_608:
        raise ValueError("Input exceeds the bounded pixel budget")
    if type(spec.get("fps")) is not int or not 1 <= spec["fps"] <= 60:
        raise ValueError("fps must be an integer from 1 through 60")
    if spec.get("audio") != "none":
        raise ValueError('Set audio to "none" explicitly; only silent input and output are supported')
    color = spec.get("color", [25, 30, 29])
    if not isinstance(color, list) or len(color) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in color):
        raise ValueError("color must contain three integer RGB bytes")
    spec["color"] = color
    ranges = spec.get("ranges")
    if not isinstance(ranges, list) or not 1 <= len(ranges) <= 256:
        raise ValueError("ranges needs 1 through 256 source-clock [start, end] pairs")
    parsed, frames = [], 0
    for pair in ranges:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each range must be [start, end]")
        start, end = [number(v, "source range", 0, 86400) for v in pair]
        count = (end - start) * spec["fps"]
        if count < 1 or not math.isclose(count, round(count), rel_tol=0, abs_tol=1e-7):
            raise ValueError("Each range must cover a positive whole number of output frames")
        parsed.append((start, end, frames, round(count)))
        frames += round(count)
    if frames / spec["fps"] > 300:
        raise ValueError("Masking is bounded to 300 seconds")
    spec["ranges"], spec["frames"] = parsed, frames
    tracks = spec.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 128:
        raise ValueError("tracks needs 1 through 128 explicit rectangle tracks")
    parsed_tracks = []
    for track in tracks:
        if not isinstance(track, dict) or set(track) - TRACK_FIELDS:
            raise ValueError("Track contains unsupported fields")
        if "name" in track and (not isinstance(track["name"], str) or len(track["name"]) > 200):
            raise ValueError("Track name must be a short string")
        intervals = track.get("intervals")
        if not isinstance(intervals, list) or not 1 <= len(intervals) <= 256:
            raise ValueError("Each track needs explicit active intervals")
        active = []
        for pair in intervals:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("Each active interval must be [start, end]")
            a, b = [number(v, "active interval", 0, 86400) for v in pair]
            if a >= b or (active and a < active[-1][1]):
                raise ValueError("Active intervals must be positive, ordered and nonoverlapping")
            active.append((a, b))
        keys = track.get("keyframes")
        if not isinstance(keys, list) or not 2 <= len(keys) <= 512:
            raise ValueError("Each track needs 2 through 512 [seconds, x, y, width, height] keys")
        parsed_keys = []
        for key in keys:
            if not isinstance(key, list) or len(key) != 5:
                raise ValueError("Each key must be [seconds, x, y, width, height]")
            at = number(key[0], "key time", 0, 86400)
            if parsed_keys and at <= parsed_keys[-1][0]:
                raise ValueError("Key times must be strictly increasing")
            parsed_keys.append([at, *rectangle(key[1:], spec["width"], spec["height"], "mask")])
        if parsed_keys[0][0] > active[0][0] or parsed_keys[-1][0] < active[-1][1]:
            raise ValueError("Keys must span every active interval; extrapolation is not allowed")
        clip = rectangle(track.get("clip", [0, 0, spec["width"], spec["height"]]),
                         spec["width"], spec["height"], "clip", clip=True)
        parsed_tracks.append({"name": track.get("name", ""), "intervals": active,
                              "keyframes": parsed_keys, "clip": clip})
    spec["tracks"] = parsed_tracks
    return spec


def source_time(spec, frame_index):
    """Map an output frame to the original source clock with exact cut indices."""
    if type(frame_index) is not int or not 0 <= frame_index < spec["frames"]:
        raise ValueError("Output frame is outside the edit")
    for start, _, first, count in spec["ranges"]:
        if frame_index < first + count:
            return start + (frame_index - first) / spec["fps"]
    raise AssertionError("Unreachable frame")


def mask_boxes(spec, seconds):
    """Return clipped pixel bounds; fractional mask edges round outward."""
    for track in spec["tracks"]:
        if not any(a <= seconds + 1e-9 < b for a, b in track["intervals"]):
            continue
        for left, right in zip(track["keyframes"], track["keyframes"][1:]):
            if seconds <= right[0] + 1e-9:
                u = max(0., min(1., (seconds - left[0]) / (right[0] - left[0])))
                x, y, w, h = [a + (b - a) * u for a, b in zip(left[1:], right[1:])]
                cx, cy, cw, ch = track["clip"]
                # Half-open pixel rectangles. The clip rounds inward so a
                # scroll viewport never paints into neighboring interface.
                x0, y0 = max(math.floor(x), math.ceil(cx)), max(math.floor(y), math.ceil(cy))
                x1, y1 = min(math.ceil(x + w), math.floor(cx + cw)), min(math.ceil(y + h), math.floor(cy + ch))
                if x0 < x1 and y0 < y1:
                    yield x0, y0, x1, y1
                break


def apply_masks(frame, spec, seconds):
    output = frame.copy()
    for x0, y0, x1, y1 in mask_boxes(spec, seconds):
        output[y0:y1, x0:x1] = spec["color"]
    return output


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_exact(stream, size):
    blocks = []
    while size:
        block = stream.read(size)
        if not block:
            raise RuntimeError("Edited input ended before its declared frame count")
        blocks.append(block)
        size -= len(block)
    return b"".join(blocks)


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def verify_frame_clock(source, spec, time_base):
    """Check actual presentation times; matching average rates do not prove CFR."""
    frames = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(source)
    ], timeout=300))["frames"]
    if len(frames) != spec["frames"]:
        raise ValueError("Edited input frame count differs from the cut map")
    tick = float(Fraction(time_base))
    if not math.isfinite(tick) or tick <= 0 or tick > 1 / spec["fps"]:
        raise ValueError("Input clock precision cannot express the declared frame rate")
    tolerance = tick / 2 + 1e-6  # e.g. Matroska rounds a 24fps clock to 1ms.
    for index, frame in enumerate(frames):
        stamp = float(frame.get("best_effort_timestamp_time", "nan"))
        if not math.isfinite(stamp) or abs(stamp - index / spec["fps"]) > tolerance:
            raise ValueError("Input frame timestamps are not the declared fixed clock")


def render(config_path, output, *, overwrite=False):
    """Bind geometry to its edited input and install only a complete silent MP4."""
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    spec = validate_config(json.loads(config_path.read_text()))
    source = (config_path.parent / spec["source"]).resolve()
    for protected in (source, config_path):
        if output == protected or (output.exists() and protected.exists() and output.samefile(protected)):
            raise ValueError("Output must not overwrite source or config")
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must be MP4")
    if output.exists() and not overwrite:
        raise FileExistsError("Output exists; use a new path or --overwrite")
    if sha256(source) != spec["source_sha256"]:
        raise ValueError("Edited source SHA-256 mismatch; update the mask plan deliberately")
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(source)
    ], timeout=30))
    streams = probe["streams"]
    if len(streams) != 1 or streams[0].get("codec_type") != "video":
        raise ValueError("Input must have one video stream and no audio or other streams")
    video = streams[0]
    if (video["width"], video["height"]) != (spec["width"], spec["height"]):
        raise ValueError("Mask dimensions must exactly match input pixels")
    if any(Fraction(video.get(k, "0/1")) != spec["fps"] for k in ("r_frame_rate", "avg_frame_rate")):
        raise ValueError("Input must already use the declared fixed frame rate")
    if abs(float(video.get("start_time", 0))) > 1e-6:
        raise ValueError("Input must start at time zero")
    if video.get("sample_aspect_ratio", "1:1") not in ("1:1", "0:1", "N/A"):
        raise ValueError("Input must have square pixels")
    if video.get("color_transfer") in ("smpte2084", "arib-std-b67"):
        raise ValueError("Convert HDR to verified SDR before authoring masks")
    rotations = [video.get("tags", {}).get("rotate", 0), *[d.get("rotation", 0) for d in video.get("side_data_list", [])]]
    if any(float(v) % 360 for v in rotations):
        raise ValueError("Normalize rotation before authoring masks")
    if video.get("nb_frames", "N/A") != "N/A" and int(video["nb_frames"]) != spec["frames"]:
        raise ValueError("Edited input frame count differs from the cut map")
    verify_frame_clock(source, spec, video.get("time_base", "0/1"))
    w, h = spec["width"], spec["height"]
    output.parent.mkdir(parents=True, exist_ok=True)
    decoder = encoder = None
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".tracked-mask-") as work:
        temporary = Path(work) / "complete.mp4"
        with tempfile.TemporaryFile() as decode_error, tempfile.TemporaryFile() as encode_error:
            try:
                decoder = subprocess.Popen([
                    "ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0", "-vsync", "0",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
                ], stdout=subprocess.PIPE, stderr=decode_error)
                encoder = subprocess.Popen([
                    "ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                    "-r", str(spec["fps"]), "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast",
                    "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)
                ], stdin=subprocess.PIPE, stderr=encode_error)
                for index in range(spec["frames"]):
                    raw = read_exact(decoder.stdout, w * h * 3)
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
                    encoder.stdin.write(apply_masks(frame, spec, source_time(spec, index)).tobytes())
                if decoder.stdout.read(1):
                    raise RuntimeError("Edited input contains more frames than the cut map")
                decoder.stdout.close()
                if decoder.wait(timeout=30):
                    raise RuntimeError("Input decoder failed")
                encoder.stdin.close()
                if encoder.wait(timeout=60):
                    raise RuntimeError("Mask encoder failed")
            finally:
                stop_process(decoder)
                stop_process(encoder)
                for process, pipe in ((decoder, "stdout"), (encoder, "stdin")):
                    if process is not None and getattr(process, pipe) is not None:
                        getattr(process, pipe).close()
        # Hard-link installation refuses an output created during the render.
        # Explicit overwrite uses atomic replacement, never partial writes.
        if overwrite:
            os.replace(temporary, output)
        else:
            os.link(temporary, output)
    return {"output": str(output), "sha256": sha256(output), "source_sha256": spec["source_sha256"],
            "width": w, "height": h, "frames": spec["frames"], "fps": spec["fps"],
            "duration": spec["frames"] / spec["fps"], "audio": "none",
            "scope": "Explicit rectangle tracks only; inspect every encoded frame for coverage"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    print(json.dumps(render(args.config, args.output, overwrite=args.overwrite), indent=2))


if __name__ == "__main__":
    main()
