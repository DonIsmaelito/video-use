"""Render an explicitly silent SDR color comparison from one decoded frame clock.

Original and corrected regions always share coordinates. This bounded RGB curve
is a review treatment, not camera color science, HDR tone mapping or a 3D LUT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont


FIELDS = {"version", "source", "source_sha256", "source_start", "duration", "fps",
          "width", "height", "rgb_coefficients", "wipe", "labels", "audio"}
LABEL_FIELDS = {"original", "corrected", "font", "font_size", "margin", "top"}


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return float(value)


def validate_config(config):
    """Reject ambiguous geometry, clocks and audio choices before starting FFmpeg."""
    if not isinstance(config, dict) or set(config) - FIELDS:
        raise ValueError("Config must contain only documented fields")
    if type(config.get("version", 1)) is not int or config.get("version", 1) != 1:
        raise ValueError("Only config version 1 is supported")
    spec = dict(config)
    if not isinstance(spec.get("source"), str) or not spec["source"]:
        raise ValueError("source must name a local file")
    digest = spec.get("source_sha256")
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
    for key in ("width", "height"):
        if type(spec.get(key)) is not int or not 64 <= spec[key] <= 4096 or spec[key] % 2:
            raise ValueError(f"{key} must be an even integer from 64 to 4096")
    if spec["width"] * spec["height"] > 8_388_608:
        raise ValueError("Output exceeds the bounded pixel budget")
    if type(spec.get("fps")) is not int or not 1 <= spec["fps"] <= 60:
        raise ValueError("fps must be an integer from 1 to 60")
    spec["source_start"] = number(spec.get("source_start", 0), "source_start", 0, 86400)
    spec["duration"] = number(spec.get("duration"), "duration", 1 / spec["fps"], 300)
    frames = spec["duration"] * spec["fps"]
    if not math.isclose(frames, round(frames), rel_tol=0, abs_tol=1e-7):
        raise ValueError("duration must span a whole number of output frames")
    spec["frames"] = round(frames)
    if spec.get("audio") != "none":
        raise ValueError('Set audio to "none" explicitly; this helper makes a silent visual review')
    coefficients = spec.get("rgb_coefficients")
    if not isinstance(coefficients, list) or len(coefficients) != 3:
        raise ValueError("rgb_coefficients must contain three numbers")
    # |c| <= .24 makes the derivative 1+4c(1-2x) positive on [0,1].
    spec["rgb_coefficients"] = [number(c, "rgb_coefficient", -.24, .24) for c in coefficients]
    keys = spec.get("wipe")
    if not isinstance(keys, list) or not 2 <= len(keys) <= 64:
        raise ValueError("wipe needs 2 to 64 [seconds, original_fraction] keys")
    parsed = []
    for key in keys:
        if not isinstance(key, list) or len(key) != 2:
            raise ValueError("Each wipe key must be [seconds, original_fraction]")
        at = number(key[0], "wipe time", 0, spec["duration"])
        fraction = number(key[1], "original_fraction", 0, 1)
        if parsed and at <= parsed[-1][0]:
            raise ValueError("Wipe times must be strictly increasing")
        parsed.append((at, fraction))
    if parsed[0][0] != 0 or parsed[-1][0] != spec["duration"]:
        raise ValueError("Wipe keys must cover exactly 0 through duration")
    spec["wipe"] = parsed
    labels = spec.get("labels")
    if labels is not None:
        if not isinstance(labels, dict) or set(labels) - LABEL_FIELDS:
            raise ValueError("labels must contain only documented fields")
        labels = dict(labels)
        for key in ("original", "corrected", "font"):
            if not isinstance(labels.get(key), str) or not labels[key] or "\n" in labels[key]:
                raise ValueError(f"labels.{key} must be a nonempty single line")
        if len(labels["original"]) > 80 or len(labels["corrected"]) > 80:
            raise ValueError("Comparison labels must be short")
        for key, default, low, high in (("font_size", 30, 8, 120), ("margin", 64, 0, 4096), ("top", 64, 0, 4096)):
            labels[key] = number(labels.get(key, default), f"labels.{key}", low, high)
        spec["labels"] = labels
    return spec


def smooth(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)


def wipe_position(seconds, keys):
    for (start, left), (end, right) in zip(keys, keys[1:]):
        if seconds <= end:
            return left + (right - left) * smooth((seconds - start) / (end - start))
    return keys[-1][1]


def make_lut(coefficients):
    """Endpoint-preserving monotonic curves in normalized nonlinear RGB."""
    x = np.arange(256, dtype=np.float64) / 255
    return np.stack([np.rint(255 * (x + c * 4 * x * (1 - x))).astype(np.uint8)
                     for c in coefficients], axis=1)


def compare_frame(frame, lut, fraction):
    """Copy Original pixels exactly; grade the same positions on the right."""
    edge = round(fraction * frame.shape[1])
    output = frame.copy()
    for channel in range(3):
        output[:, edge:, channel] = lut[frame[:, edge:, channel], channel]
    return output


def badge(text, font, scale):
    padding = max(2, round(18 * scale))
    bounds = font.getbbox(text)
    height = max(round(58 * scale), bounds[3] - bounds[1] + padding)
    width = math.ceil(font.getlength(text)) + 2 * padding
    result = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(result)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=max(1, round(8 * scale)), fill=(22, 25, 26, 195))
    draw.text((padding, (height - bounds[3] + bounds[1]) / 2 - bounds[1]), text,
              font=font, fill=(244, 244, 241, 255))
    return np.asarray(result)


def draw_badge(frame, asset, x, y, opacity):
    height, width = asset.shape[:2]
    alpha = asset[:, :, 3:4].astype(np.float32) / 255 * opacity
    region = frame[y:y + height, x:x + width]
    region[:] = np.rint(region * (1 - alpha) + asset[:, :, :3] * alpha).astype(np.uint8)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ], timeout=30))


def read_exact(stream, size):
    parts = []
    while size:
        part = stream.read(size)
        if not part:
            raise RuntimeError("Source ended before the requested comparison duration")
        parts.append(part)
        size -= len(part)
    return b"".join(parts)


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def render(config_path, output, *, width=None, overwrite=False):
    """Preflight inputs, stream a comparison and atomically install a complete MP4."""
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    spec = validate_config(json.loads(config_path.read_text()))
    source = (config_path.parent / spec["source"]).resolve()
    font_path = (config_path.parent / spec["labels"]["font"]).resolve() if spec.get("labels") else None
    for protected in (config_path, source, font_path):
        if protected is not None and (output == protected or (output.exists() and protected.exists() and output.samefile(protected))):
            raise ValueError("Output must not overwrite a source, font or config file")
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must be an MP4 path")
    if output.exists() and not overwrite:
        raise FileExistsError("Output exists; choose another path or pass --overwrite")
    digest = sha256(source)
    if spec.get("source_sha256") and digest != spec["source_sha256"]:
        raise ValueError("Source SHA-256 mismatch")
    metadata = probe(source)
    videos = [s for s in metadata["streams"] if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    if len(videos) != 1:
        raise ValueError("Source must have exactly one video stream")
    video = videos[0]
    if video.get("color_transfer") in ("smpte2084", "arib-std-b67"):
        raise ValueError("HDR input needs a separate verified SDR conversion first")
    if video.get("sample_aspect_ratio", "1:1") not in ("1:1", "0:1", "N/A"):
        raise ValueError("Anamorphic input needs an explicit square-pixel conversion first")
    rotations = [video.get("tags", {}).get("rotate", 0), *[d.get("rotation", 0) for d in video.get("side_data_list", [])]]
    if any(float(r) % 360 for r in rotations):
        raise ValueError("Rotated input needs an explicit orientation conversion first")
    source_duration = float(video.get("duration") or metadata["format"].get("duration", 0))
    if not math.isfinite(source_duration) or spec["source_start"] + spec["duration"] > source_duration + 1e-6:
        raise ValueError("Requested range extends beyond the source")
    if abs(spec["height"] - spec["width"] * video["height"] / video["width"]) > 2:
        raise ValueError("Comparison dimensions must preserve source aspect ratio")
    if width is not None and (type(width) is not int or not 64 <= width <= spec["width"] or width % 2):
        raise ValueError("Draft width must be an even integer from64 through configured width")
    w = width or spec["width"]
    h = 2 * round(w * spec["height"] / spec["width"] / 2)
    if h < 2:
        raise ValueError("Draft height is too small")
    scale = w / 1920
    labels = None
    if spec.get("labels"):
        lab = spec["labels"]
        geometry_scale = w / spec["width"]
        font = ImageFont.truetype(str(font_path), max(1, round(lab["font_size"] * geometry_scale)))
        original, corrected = (badge(lab[key], font, geometry_scale) for key in ("original", "corrected"))
        margin, top = round(lab["margin"] * geometry_scale), round(lab["top"] * geometry_scale)
        for asset in (original, corrected):
            if asset.shape[1] + 2 * margin > w or asset.shape[0] + top > h:
                raise ValueError("Comparison label does not fit the output canvas")
        labels = original, corrected, margin, top
    fps, frames = spec["fps"], spec["frames"]
    filters = (f'trim=start={spec["source_start"]}:duration={spec["duration"]},setpts=PTS-STARTPTS,'
               f'fps={fps}:start_time=0,scale={w}:{h}:flags=lanczos+accurate_rnd+full_chroma_int')
    decoder = ["ffmpeg", "-v", "error", "-threads", "2", "-noautorotate", "-i", str(source),
               "-map", f'0:{video["index"]}', "-vf", filters, "-frames:v", str(frames), "-an",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    output.parent.mkdir(parents=True, exist_ok=True)
    dec = enc = None
    temporary = None
    lut = make_lut(spec["rgb_coefficients"])
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".grade-", suffix=".mp4", delete=False) as handle:
            temporary = Path(handle.name)
        encoder = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                   "-r", str(fps), "-i", "-", "-an", "-vf",
                   "scale=in_range=full:out_range=tv:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int,format=yuv420p",
                   "-c:v", "libx264", "-threads", "4", "-preset", "fast", "-crf", "18", "-color_range", "tv",
                   "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", str(temporary)]
        with tempfile.TemporaryFile() as decode_errors, tempfile.TemporaryFile() as encode_errors:
            try:
                dec = subprocess.Popen(decoder, stdout=subprocess.PIPE, stderr=decode_errors)
                enc = subprocess.Popen(encoder, stdin=subprocess.PIPE, stderr=encode_errors)
                for index in range(frames):
                    frame = np.frombuffer(read_exact(dec.stdout, w * h * 3), np.uint8).reshape(h, w, 3)
                    fraction = wipe_position(index / fps, spec["wipe"])
                    result = compare_frame(frame, lut, fraction)
                    edge = round(fraction * w)
                    if 0 < edge < w:
                        thickness = max(1, round(2 * scale))
                        result[:, max(0, edge - thickness // 2):min(w, edge + thickness)] = (241, 240, 237)
                    if labels:
                        original, corrected, margin, top = labels
                        fade = max(1, 80 * w / spec["width"])
                        for asset, x, space in ((original, margin, edge), (corrected, w - margin - corrected.shape[1], w - edge)):
                            opacity = smooth((space - margin - asset.shape[1]) / fade)
                            if opacity:
                                draw_badge(result, asset, x, top, opacity)
                    enc.stdin.write(result.tobytes())
                dec.stdout.close()
                enc.stdin.close()
                if dec.wait(timeout=30) != 0 or enc.wait(timeout=30) != 0:
                    raise RuntimeError("FFmpeg comparison failed")
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                stop_process(dec)
                stop_process(enc)
                decode_errors.seek(0)
                encode_errors.seek(0)
                detail = (decode_errors.read(4096) + encode_errors.read(4096)).decode(errors="replace")
                raise RuntimeError(f"Comparison render failed: {exc}\n{detail}") from exc
        final = probe(temporary)
        stream = next(s for s in final["streams"] if s.get("codec_type") == "video")
        if int(stream.get("nb_frames", 0)) != frames or any(s.get("codec_type") == "audio" for s in final["streams"]):
            raise RuntimeError("Encoded comparison frame count or audio does not match the requested output")
        if overwrite:
            temporary.replace(output)
        else:
            os.link(temporary, output)  # Atomic no-clobber, including a concurrently created destination.
        return {"output": str(output), "source_sha256": digest, "width": w, "height": h,
                "fps": fps, "frames": frames, "duration": frames / fps, "audio": "none",
                "method": "One decoded clock and crop; bounded nonlinear RGB curve on the right"}
    finally:
        stop_process(dec)
        stop_process(enc)
        for process, pipe in ((dec, "stdout"), (enc, "stdin")):
            stream = getattr(process, pipe, None)
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except OSError:
                    pass
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--width", type=int, help="Smaller even draft width; aspect ratio is preserved")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(render(args.config, args.output, width=args.width, overwrite=args.overwrite), indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
