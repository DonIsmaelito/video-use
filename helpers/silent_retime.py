"""Make a bounded silent replay derivative with explicit source-time provenance.

One H.264 encode changes speed by frame repetition/drop. No optical flow, sound
removal, source replacement, automatic tracking or speech retiming is implied.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

try:
    from .face_track import probe_source, sha256
except ImportError:
    from face_track import probe_source, sha256


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return float(value)


def settings(start, end, speed, fps):
    start = number(start, "start", 0, 3600)
    end = number(end, "end", 0, 3600)
    speed = number(speed, "speed", .25, 2)
    if not 0 < end - start <= 120:
        raise ValueError("Select a positive source interval of at most 120 seconds")
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("fps must be an integer from 1 to 60")
    duration = (end - start) / speed
    frames = duration * fps
    if duration > 300 or not math.isclose(frames, round(frames), abs_tol=1e-7, rel_tol=0) or frames < 1:
        raise ValueError("Retimed duration must span whole output frames and be at most 300 seconds")
    return start, end, speed, fps, round(frames)


def _probe(path, *, count_frames=False):
    count = ["-count_frames"] if count_frames else []
    return json.loads(subprocess.run(["ffprobe", "-v", "error", *count, "-show_streams", "-show_format",
                                      "-of", "json", str(path)], capture_output=True, check=True, timeout=180).stdout)


def _new_output(path, temporary):
    """Reserve exclusively, then replace with the already completed file.

    Modal volumes do not support hard links. An exclusive empty reservation
    prevents overwriting a concurrent producer; incomplete encoded bytes never
    appear at the final path. A reader seeing the brief reservation fails closed.
    """
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    own = None
    try:
        own = os.fstat(descriptor)
        current = os.stat(path, follow_symlinks=False)
        if (own.st_dev, own.st_ino) != (current.st_dev, current.st_ino):
            raise FileExistsError("Output reservation changed")
        os.replace(temporary, path)
    except BaseException:
        try:
            current = os.stat(path, follow_symlinks=False)
            if own is not None and (own.st_dev, own.st_ino) == (current.st_dev, current.st_ino):
                Path(path).unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(descriptor)


def retime(source, output, *, start, end, speed, fps=30, source_sha256=None):
    start, end, speed, fps, frames = settings(start, end, speed, fps)
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must be an MP4")
    if output.is_symlink() or output.exists():
        raise FileExistsError("Output already exists; choose a new path")
    if output.resolve() == source:
        raise ValueError("Output must not replace source media")
    if source_sha256 is not None and (not isinstance(source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)):
        raise ValueError("source_sha256 must be a lowercase SHA256")
    metadata = _probe(source)
    streams = metadata.get("streams", [])
    if any(s.get("codec_type") == "audio" for s in streams):
        raise ValueError("Source must be silent; do not discard or retime speech with this helper")
    videos = [s for s in streams if s.get("codec_type") == "video"]
    if len(videos) != 1 or videos[0].get("disposition", {}).get("attached_pic"):
        raise ValueError("Source must contain one ordinary video stream")
    video = videos[0]
    width, height = video.get("width", 0), video.get("height", 0)
    if not all(type(v) is int and 2 <= v <= 4096 and v % 2 == 0 for v in (width, height)) or width * height > 8_388_608:
        raise ValueError("Source must have even dimensions up to 4096 and at most 8388608 pixels")
    if video.get("color_transfer") in ("smpte2084", "arib-std-b67"):
        raise ValueError("HDR footage needs a separately reviewed SDR conversion")
    identity, timeline = probe_source(source)
    if source_sha256 is not None and identity["sha256"] != source_sha256:
        raise ValueError("Source SHA256 mismatch")
    if start < timeline[0]["time"] - 1e-7 or end > timeline[-1]["end"] + 1e-7:
        raise ValueError("Requested range lies outside the actual video timeline")
    selected = [f for f in timeline if f["time"] < end and f["end"] > start]
    if not selected:
        raise ValueError("Requested range has no source frames")
    origin, base = Fraction(identity["format_start_time"]), Fraction(identity["time_base"])
    ticks = (origin + Fraction(str(start))) / base
    ratio = Fraction(str(speed))
    shift = f"({ticks.numerator}/{ticks.denominator})"
    factor = f"({ratio.numerator}/{ratio.denominator})"
    # Select actual display-order frames, retaining the frame covering start.
    # -copyts keeps the measured input PTS; fps fixes a deliberate output clock.
    hold = (selected[-1]["end"] - selected[-1]["time"]) / speed + 1 / fps
    filters = (f"select='between(n,{selected[0]['index']},{selected[-1]['index']})',"
               f"setpts=(PTS-{shift})/{factor},fps={fps}:start_time=0:round=near,"
               f"tpad=stop_mode=clone:stop_duration={hold:.9f}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".silent-retime-", dir=output.parent) as folder:
        temp = Path(folder) / "complete.mp4"
        command = ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-copyts", "-noautorotate", "-i", str(source),
                   "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", filters,
                   "-frames:v", str(frames), "-fps_mode", "passthrough", "-c:v", "libx264", "-crf", "16",
                   "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temp)]
        subprocess.run(command, capture_output=True, check=True, timeout=600)
        actual = _probe(temp, count_frames=True)
        encoded = actual["streams"]
        if len(encoded) != 1 or encoded[0].get("codec_type") != "video":
            raise ValueError("Retimed output is not a single silent video stream")
        encoded = encoded[0]
        if (encoded.get("width"), encoded.get("height"), int(encoded.get("nb_read_frames", 0))) != (width, height, frames):
            raise ValueError("Retimed frame count or geometry differs from the requested contract")
        if Fraction(encoded["avg_frame_rate"]) != fps or abs(float(encoded.get("start_time", 0))) > 1e-6 or abs(float(encoded["duration"]) - frames / fps) > .001:
            raise ValueError("Retimed output clock differs from the requested contract")
        if sha256(source) != identity["sha256"]:
            raise ValueError("Source changed during retiming")
        report = {"schema": "video-use.silent-retime.v1", "source": identity,
                  "source_interval": {"start": start, "end": end}, "speed": speed,
                  "source_first_frame": selected[0], "source_last_frame": selected[-1],
                  "output": {"file": output.name, "sha256": sha256(temp), "width": width, "height": height,
                             "fps": fps, "frames": frames, "duration": frames / fps, "audio_streams": 0},
                  "mapping": "Output t samples source start + speed*t on its actual PTS clock; CFR rounding may repeat/drop adjacent source frames",
                  "method": "One H264 derivative encode with frame repetition/drop; no optical flow or audio processing",
                  "warning": "This derivative has a new source hash and clock; do not reuse original-source tracks or transcript timestamps"}
        _new_output(output, temp)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--speed", type=float, required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--source-sha256")
    args = parser.parse_args(argv)
    try:
        result = retime(args.source, args.output, start=args.start, end=args.end, speed=args.speed,
                        fps=args.fps, source_sha256=args.source_sha256)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
