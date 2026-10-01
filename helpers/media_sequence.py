#!/usr/bin/env python3
"""Compose supplied stills and timed audio without choosing a story or style.

    python helpers/media_sequence.py edit/sequence.json -o edit/draft.mp4

Inputs are local files; relative paths resolve beside the JSON. Images can be
photos, rasterized slides, diagrams, or authored artwork. This helper supplies
timing, fit, optional pan/zoom and waveform mechanics. Captions and editorial
overlays remain the responsibility of render.py and are applied afterwards.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageColor, ImageOps


MAX_DURATION = 3600
MAX_FRAMES = 108000
MAX_FILE_BYTES = 512 * 1024 * 1024


def number(value, name: str, low: float, high: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return result


def integer(value, name: str, low: int, high: int) -> int:
    result = number(value, name, low, high)
    if int(result) != result:
        raise ValueError(f"{name} must be an integer")
    return int(result)


def keys(value, allowed: set[str], name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    unexpected = set(value) - allowed
    if unexpected:
        raise ValueError(f"Unknown {name} fields: {', '.join(sorted(unexpected))}")
    return value


def color(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Colors must be six-digit #RRGGBB values")
    return value


def local_file(value, base: Path) -> Path:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("A nonempty local file path is required")
    path = (base / value).resolve()
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError(f"Input must be a nonempty local file no larger than 512 MiB: {path.name}")
    return path


class Runner:
    """Bound the entire render, including probes and final full-decode checks."""

    def __init__(self, timeout: float):
        self.deadline = time.monotonic() + number(timeout, "timeout", 1, 3600)

    def run(self, command: list[str], *, max_seconds: float | None = None) -> str:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Media composition exceeded its time limit")
        try:
            result = subprocess.run(
                command, capture_output=True, text=True,
                timeout=min(remaining, max_seconds) if max_seconds else remaining,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Media composition exceeded its time limit") from exc
        if result.returncode:
            raise ValueError(f"{Path(command[0]).name} failed: {result.stderr[-3000:].strip()}")
        return result.stdout

    def probe(self, path: Path) -> dict:
        return json.loads(self.run([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
        ], max_seconds=30))


def ffmpeg() -> list[str]:
    return ["ffmpeg", "-hide_banner", "-v", "error", "-nostdin", "-y",
            "-threads", "2", "-filter_threads", "1", "-filter_complex_threads", "1"]


def video_encoding() -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-threads", "2", "-pix_fmt", "yuv420p"]


def coordinates(value, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain [x, y] values between 0 and 1")
    return tuple(number(v, name, 0, 1) for v in value)


def normalize(spec: dict, base: Path, runner: Runner) -> dict:
    keys(spec, {"version", "mode", "width", "height", "fps", "background", "items",
                "audio", "cover", "waveform", "duration"}, "composition")
    if spec.get("version", 1) != 1:
        raise ValueError("Only composition version 1 is supported")
    mode = spec.get("mode", "sequence")
    if mode not in {"sequence", "audio"}:
        raise ValueError("mode must be sequence or audio")
    width = integer(spec.get("width", 1920), "width", 16, 3840)
    height = integer(spec.get("height", 1080), "height", 16, 3840)
    if width % 2 or height % 2 or width * height > 3840 * 2160:
        raise ValueError("Dimensions must be even and at most 3840 × 2160 pixels in area")
    try:
        rate = Fraction(str(spec.get("fps", 30)))
        number(float(rate), "fps", 1, 60)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("fps must be a number or rational rate between 1 and 60") from exc
    fps = float(rate)
    background = color(spec.get("background", "#000000"))
    tracks = spec.get("audio", [])
    if not isinstance(tracks, list) or len(tracks) > 8:
        raise ValueError("audio must be an array of at most eight tracks")
    audio = []
    for index, track in enumerate(tracks):
        keys(track, {"file", "start", "source_start", "duration", "gain", "loop", "fade"}, "audio track")
        file = local_file(track.get("file"), base)
        probe = runner.probe(file)
        stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not stream:
            raise ValueError(f"Audio track {index + 1} contains no audio stream")
        source_duration = number(stream.get("duration") or probe.get("format", {}).get("duration"), "source audio duration", .001, 86400)
        source_start = number(track.get("source_start", 0), "source_start", 0, source_duration)
        start = number(track.get("start", 0), "audio start", 0, MAX_DURATION)
        loop = track.get("loop", False)
        if not isinstance(loop, bool):
            raise ValueError("loop must be true or false")
        duration = track.get("duration")
        if loop and duration is None:
            raise ValueError("Looped audio requires an explicit duration")
        duration = number(duration if duration is not None else source_duration - source_start, "audio duration", .001, MAX_DURATION)
        if not loop and duration > source_duration - source_start + .025:
            raise ValueError("Audio duration exceeds the available source; use loop explicitly for repeated music")
        audio.append({"file": file, "start": start, "source_start": source_start,
                      "duration": duration, "gain": number(track.get("gain", 1), "gain", 0, 4),
                      "loop": loop, "fade": number(track.get("fade", .03), "fade", 0, 10)})
    items = spec.get("items", [])
    if mode == "audio":
        if not audio:
            raise ValueError("Audio mode requires at least one audio track")
        if items:
            raise ValueError("Use sequence mode for multiple images")
        duration = number(spec.get("duration", max(a["start"] + a["duration"] for a in audio)), "duration", .05, MAX_DURATION)
        cover = spec.get("cover", {})
        keys(cover, {"file", "fit", "motion"}, "cover")
        items = [{**cover, "duration": duration}]
    elif "cover" in spec or "duration" in spec:
        raise ValueError("Sequence duration comes from items; cover and duration apply only in audio mode")
    if not isinstance(items, list) or not 1 <= len(items) <= 120:
        raise ValueError("A sequence requires between one and 120 items")
    timeline = []
    total = 0.0
    previous_frame = 0
    for index, item in enumerate(items):
        keys(item, {"file", "duration", "fit", "motion"}, "image item")
        file = local_file(item["file"], base) if item.get("file") else None
        if file is None and mode != "audio":
            raise ValueError("Sequence items require an image file")
        duration = number(item.get("duration"), "item duration", 1 / fps, MAX_DURATION)
        total += duration
        # Round cumulative boundaries upward so the last spoken syllable is
        # never shortened merely to land on a video-frame boundary.
        end_frame = math.ceil(total * fps - 1e-9)
        frames = end_frame - previous_frame
        if frames < 1:
            raise ValueError("Every image must last at least one output frame")
        fit = item.get("fit", "contain")
        if fit not in {"contain", "cover"}:
            raise ValueError("fit must be contain or cover")
        motion = item.get("motion", {})
        keys(motion, {"zoom_start", "zoom_end", "focus_start", "focus_end", "easing"}, "motion")
        zoom_start = number(motion.get("zoom_start", 1), "zoom_start", 1, 3)
        zoom_end = number(motion.get("zoom_end", zoom_start), "zoom_end", 1, 3)
        focus_start = coordinates(motion.get("focus_start", [.5, .5]), "focus_start")
        focus_end = coordinates(motion.get("focus_end", list(focus_start)), "focus_end")
        easing = motion.get("easing", "linear")
        if easing not in {"linear", "smooth"}:
            raise ValueError("motion.easing must be linear or smooth")
        timeline.append({"index": index, "file": file, "fit": fit, "frames": frames,
                         "start": previous_frame / fps, "duration": frames / fps,
                         "zoom_start": zoom_start, "zoom_end": zoom_end,
                         "focus_start": focus_start, "focus_end": focus_end, "easing": easing})
        previous_frame = end_frame
    if total > MAX_DURATION or previous_frame > MAX_FRAMES:
        raise ValueError("Composition exceeds 3600 seconds or 108000 frames; split it into sections")
    duration = previous_frame / fps
    if any(a["start"] + a["duration"] > duration + .001 for a in audio):
        raise ValueError("Audio would be truncated; extend the images or explicitly trim the audio track duration")
    waveform = spec.get("waveform")
    if waveform is not None:
        if not audio:
            raise ValueError("A waveform requires an audio track")
        keys(waveform, {"x", "y", "width", "height", "color", "track"}, "waveform")
        waveform = {"x": integer(waveform.get("x", 0), "waveform.x", 0, width - 2),
                    "y": integer(waveform.get("y", height * 3 // 4), "waveform.y", 0, height - 2),
                    "width": integer(waveform.get("width", width), "waveform.width", 2, width),
                    "height": integer(waveform.get("height", height // 4), "waveform.height", 2, height),
                    "color": color(waveform.get("color", "#FFFFFF")),
                    "track": integer(waveform.get("track", 0), "waveform.track", 0, len(audio) - 1)}
        if waveform["x"] + waveform["width"] > width or waveform["y"] + waveform["height"] > height:
            raise ValueError("Waveform must fit inside the output canvas")
    return {"mode": mode, "width": width, "height": height, "rate": str(rate), "fps": fps,
            "background": background, "timeline": timeline, "audio": audio, "waveform": waveform,
            "frames": previous_frame, "duration": duration, "requested_duration": total}


def image_canvas(item: dict, config: dict, output: Path) -> None:
    size = (config["width"], config["height"])
    canvas = Image.new("RGB", size, ImageColor.getrgb(config["background"]))
    if item["file"]:
        with Image.open(item["file"]) as source:
            if source.width * source.height > 40_000_000:
                raise ValueError("Source images are limited to 40 megapixels; resize the source first")
            if getattr(source, "n_frames", 1) > 1:
                raise ValueError("Sequence inputs must be still images; extract an intentional frame first")
            source = ImageOps.exif_transpose(source).convert("RGBA")
            fitted = (ImageOps.fit(source, size, method=Image.Resampling.LANCZOS)
                      if item["fit"] == "cover" else ImageOps.contain(source, size, method=Image.Resampling.LANCZOS))
            canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2), fitted)
    canvas.save(output)


def image_filter(item: dict, config: dict) -> str:
    progress = f"on/{max(1, item['frames'] - 1)}"
    if item["easing"] == "smooth":
        progress = f"({progress})*({progress})*(3-2*({progress}))"
    def interpolate(a, b):
        return f"({a:.9f}+({b - a:.9f})*({progress}))"
    zoom = interpolate(item["zoom_start"], item["zoom_end"])
    x = interpolate(item["focus_start"][0], item["focus_end"][0])
    y = interpolate(item["focus_start"][1], item["focus_end"][1])
    return (f"zoompan=z='{zoom}':x='(iw-iw/zoom)*{x}':y='(ih-ih/zoom)*{y}':"
            f"d={item['frames']}:s={config['width']}x{config['height']}:fps={config['rate']},setsar=1")


def mix_audio(base_video: Path, config: dict, output: Path, runner: Runner) -> None:
    command = ffmpeg() + ["-i", str(base_video)]
    graph = []
    for i, track in enumerate(config["audio"]):
        if track["loop"]:
            command += ["-stream_loop", "-1"]
        command += ["-ss", str(track["source_start"]), "-i", str(track["file"])]
        fade = min(track["fade"], track["duration"] / 2)
        chain = (f"[{i + 1}:a:0]atrim=duration={track['duration']:.9f},asetpts=PTS-STARTPTS,"
                 f"aresample=48000,aformat=channel_layouts=stereo,volume={track['gain']:.9f},"
                 f"afade=t=in:d={fade:.9f},afade=t=out:st={track['duration'] - fade:.9f}:d={fade:.9f},"
                 f"adelay={round(track['start'] * 48000)}S:all=1,apad,atrim=duration={config['duration']:.9f}")
        waveform = config["waveform"]
        graph.append(chain + (f",asplit=2[a{i}][waveaudio]" if waveform and waveform["track"] == i else f"[a{i}]"))
    n = len(config["audio"])
    graph.append("".join(f"[a{i}]" for i in range(n)) +
                 f"amix=inputs={n}:normalize=0:duration=longest,alimiter=limit=0.98:latency=1[aout]")
    waveform = config["waveform"]
    if waveform:
        graph.append(f"[waveaudio]showwaves=s={waveform['width']}x{waveform['height']}:"
                     f"mode=line:rate={config['rate']}:colors={waveform['color']},format=rgba[wave]")
        graph.append(f"[0:v][wave]overlay=x={waveform['x']}:y={waveform['y']}:shortest=1,format=yuv420p[vout]")
    command += ["-filter_complex", ";".join(graph), "-map", "[vout]" if waveform else "0:v:0", "-map", "[aout]"]
    command += video_encoding() if waveform else ["-c:v", "copy"]
    command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", str(config["duration"]),
                "-movflags", "+faststart", "-f", "mp4", str(output)]
    runner.run(command)


def compose(spec: dict, output: Path, *, base: Path | None = None, timeout: float = 1800) -> dict:
    """Render atomically; an error leaves an existing output and every input intact."""
    started = time.monotonic()
    runner = Runner(timeout)
    config = normalize(spec, (base or Path.cwd()).resolve(), runner)
    output = output.resolve()
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must have an .mp4 extension")
    inputs = {item["file"] for item in config["timeline"]} | {track["file"] for track in config["audio"]}
    if output in inputs:
        raise ValueError("Output must not overwrite a source input")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".media-sequence-", dir=output.parent) as temporary:
        work = Path(temporary)
        segments = []
        for item in config["timeline"]:
            image = work / f"image-{item['index']:03d}.png"
            segment = work / f"part-{item['index']:03d}.mp4"
            image_canvas(item, config, image)
            runner.run(ffmpeg() + ["-i", str(image), "-vf", image_filter(item, config),
                       "-frames:v", str(item["frames"]), "-an", *video_encoding(), str(segment)])
            image.unlink()
            segments.append(segment)
        # Only generated filenames enter the concat syntax, never supplied paths.
        manifest = work / "concat.txt"
        manifest.write_text("".join(f"file '{segment.name}'\n" for segment in segments))
        silent = work / "silent.mp4"
        runner.run(ffmpeg() + ["-f", "concat", "-safe", "1", "-i", str(manifest),
                   "-map", "0:v:0", "-c:v", "copy", "-movflags", "+faststart", str(silent)])
        complete = work / "complete.mp4"
        if config["audio"]:
            mix_audio(silent, config, complete, runner)
        else:
            silent.rename(complete)
        probe = runner.probe(complete)
        stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        duration = float(stream.get("duration") or probe["format"]["duration"])
        if (stream["width"], stream["height"], stream["pix_fmt"]) != (config["width"], config["height"], "yuv420p"):
            raise ValueError("Encoded video dimensions or pixel format differ from the specification")
        if abs(duration - config["duration"]) > 1 / config["fps"] + .005:
            raise ValueError("Encoded video duration differs from the image timeline")
        runner.run(ffmpeg() + ["-xerror", "-i", str(complete), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"])
        complete.replace(output)
    return {"version": 1, "output": str(output), "mode": config["mode"], "duration": duration,
            "requested_duration": config["requested_duration"], "width": config["width"], "height": config["height"],
            "fps": config["rate"], "frames": int(stream.get("nb_frames", config["frames"])),
            "audio_tracks": len(config["audio"]), "waveform": bool(config["waveform"]),
            "codec": stream["codec_name"], "pixel_format": stream["pix_fmt"], "full_decode_verified": True,
            "timeline": [{"file": str(i["file"]) if i["file"] else None, "start": i["start"],
                          "duration": i["duration"], "frames": i["frames"]} for i in config["timeline"]],
            "elapsed_seconds": round(time.monotonic() - started, 3)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    try:
        if args.spec.stat().st_size > 1024 * 1024:
            raise ValueError("Composition JSON must be at most 1 MiB")
        if args.spec.resolve() == args.output.resolve():
            raise ValueError("Output must not overwrite the composition JSON")
        report = compose(json.loads(args.spec.read_text()), args.output, base=args.spec.resolve().parent, timeout=args.timeout)
        print(json.dumps(report, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, Image.DecompressionBombError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
