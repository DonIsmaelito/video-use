#!/usr/bin/env python3
"""Validate and assemble saved editable scenes, with an optional narration track.

Source coordinates stay unchanged: higher quality renders use a larger backing
canvas. Every scene is preflighted before any frames are rendered. Cached videos
are keyed by normalized source, renderer code and actual output dimensions.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

try:
    from .render_scene import HERE, RUNTIME, render_scene, validate_scene
except ImportError:
    from render_scene import HERE, RUNTIME, render_scene, validate_scene

SCENE_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}")
MAX_SCENES = 12
MAX_DURATION = 180


def _number(value, name, low, high):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{name} must be a finite number between {low} and {high}")
    return value


def validate_spec(value):
    """Validate the bounded assembly contract without accessing files or tools."""
    allowed = {
        "scene_ids",
        "quality",
        "width",
        "height",
        "fps",
        "narration_path",
        "narration_offset",
        "audio_normalization",
    }
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Unsupported assembly options")
    ids = value.get("scene_ids")
    if (
        not isinstance(ids, list)
        or not 1 <= len(ids) <= MAX_SCENES
        or any(not isinstance(i, str) or not SCENE_ID.fullmatch(i) for i in ids)
    ):
        raise ValueError(
            "scene_ids needs 1–12 ordered IDs of letters, numbers, underscores or hyphens"
        )
    quality = value.get("quality", "draft")
    if quality not in {"draft", "final"}:
        raise ValueError("quality must be draft or final")
    out = {"scene_ids": list(ids), "quality": quality}
    for key, high in (("width", 3840), ("height", 3840), ("fps", 30)):
        number = _number(value.get(key, 0), key, 0, high)
        if int(number) != number or (
            key != "fps" and number and (number < 180 or number % 2)
        ):
            raise ValueError(
                f"{key} must be an integer"
                + (" and an even dimension of at least 180" if key != "fps" else "")
            )
        out[key] = int(number)
    if bool(out["width"]) != bool(out["height"]):
        raise ValueError("Supply both width and height, or omit both")
    path = value.get("narration_path", "")
    if not isinstance(path, str) or len(path) > 500 or "\x00" in path:
        raise ValueError("Invalid narration_path")
    offset = _number(
        value.get("narration_offset", 0), "narration_offset", 0, MAX_DURATION
    )
    if offset and not path:
        raise ValueError("narration_offset requires narration_path")
    preset = value.get("audio_normalization", "web")
    if preset not in {"web", "none"}:
        raise ValueError("audio_normalization must be web or none")
    return out | {
        "narration_path": path,
        "narration_offset": offset,
        "audio_normalization": preset,
    }


def workspace_path(root, path):
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Assembly paths must stay inside the workspace")
    return resolved


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
    )


def preflight(value, root):
    """Load every source and aggregate errors before launching a renderer."""
    spec = validate_spec(value)
    sources, errors = {}, []
    for scene_id in dict.fromkeys(spec["scene_ids"]):
        try:
            path = workspace_path(root, f"edit/scenes/{scene_id}.json")
            if path.stat().st_size > 1_000_000:
                raise ValueError("Scene JSON exceeds 1 MB")
            sources[scene_id] = validate_scene(json.loads(path.read_text()))
        except (OSError, ValueError, TypeError) as error:
            errors.extend(
                f"{scene_id}: {item}" for item in getattr(error, "errors", [str(error)])
            )
    if errors:
        raise ValueError(
            "Assembly preflight failed before rendering:\n" + "\n".join(errors)
        )
    first = sources[spec["scene_ids"][0]]
    width, height = spec["width"], spec["height"]
    if not width:
        short = 1080 if spec["quality"] == "final" else 540
        # Integer multiples of the reduced even ratio preserve uncommon aspect
        # ratios exactly rather than silently squeezing/cropping their content.
        divisor = math.gcd(first["width"], first["height"])
        rw, rh = first["width"] // divisor, first["height"] // divisor
        multiple = max(2, round(short / min(rw, rh) / 2) * 2)
        width, height = rw * multiple, rh * multiple
    if width > 3840 or height > 3840 or width * height > 8_294_400:
        raise ValueError(
            "Output dimensions exceed the renderer limits; provide a smaller width and height"
        )
    fps = spec["fps"] or (30 if spec["quality"] == "final" else 15)
    scenes, total_frames = [], 0
    for scene_id in spec["scene_ids"]:
        scene = sources[scene_id]
        if width * scene["height"] != height * scene["width"]:
            raise ValueError(
                f"{scene_id}: all scenes must match the output aspect ratio"
            )
        frames = math.ceil(scene["duration"] * fps - 1e-9)
        scenes.append(
            {
                "scene_id": scene_id,
                "title": scene_id.replace("_", " "),
                "seconds": frames / fps,
                "frame_count": frames,
            }
        )
        total_frames += frames
    duration = total_frames / fps
    if duration > MAX_DURATION:
        raise ValueError(
            "Assembly exceeds 180 seconds; divide the project into shorter pieces"
        )
    audio = None
    if spec["narration_path"]:
        audio = workspace_path(root, spec["narration_path"])
        media = probe(audio)
        if not any(s.get("codec_type") == "audio" for s in media.get("streams", [])):
            raise ValueError("narration_path has no audio stream")
        audio_duration = float(media["format"]["duration"])
        if not math.isfinite(audio_duration) or audio_duration <= 0:
            raise ValueError("Narration duration is invalid")
        if spec["narration_offset"] + audio_duration > duration + 1e-6:
            raise ValueError(
                f"Narration ends at {spec['narration_offset'] + audio_duration:.3f}s but scenes end at {duration:.3f}s; lengthen the scenes or revise narration instead of truncating it"
            )
    return spec | {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "frame_count": total_frames,
        "scenes": scenes,
        "sources": sources,
        "audio": audio,
    }


def renderer_fingerprint():
    digest = hashlib.sha256()
    for path in (
        HERE / "render_scene.py",
        HERE / "scene_runtime.mjs",
        HERE / "motion_render.mjs",
        RUNTIME / "motion.mjs",
    ):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def cached_scene(root, scene, width, height, fps, renderer, *, chrome=None, deps=None):
    key = hashlib.sha256(
        json.dumps(
            {
                "source": scene,
                "width": width,
                "height": height,
                "fps": fps,
                "renderer": renderer,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    directory = workspace_path(root, f"edit/.assembly-cache/{key}")
    directory.mkdir(parents=True, exist_ok=True)
    output, receipt = directory / "scene.mp4", directory / "complete.json"
    with (directory / "lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if output.is_file() and receipt.is_file():
            try:
                saved = json.loads(receipt.read_text())
                if not isinstance(saved, dict):
                    saved = {}
            except (OSError, ValueError):
                saved = {}
            if saved.get("sha256") == hashlib.sha256(output.read_bytes()).hexdigest():
                return {
                    "video_path": str(output),
                    "reused": True,
                    "warnings": saved.get("warnings", []),
                }
        rendered = render_scene(
            scene,
            output,
            overwrite=True,
            output_width=width,
            output_height=height,
            output_fps=fps,
            chrome=chrome,
            deps=deps,
        )
        pending = receipt.with_suffix(".tmp")
        pending.write_text(
            json.dumps(
                {
                    "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                    "warnings": rendered.get("warnings", []),
                }
            )
        )
        pending.replace(receipt)
    return {
        "video_path": str(output),
        "reused": False,
        "warnings": rendered.get("warnings", []),
    }


def narration_filter(audio, preset):
    """Measure first, then use FFmpeg's speech-oriented web loudness preset."""
    if preset == "none":
        return "anull", {"preset": "none"}
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(audio),
            "-vn",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    measurement = json.loads(
        result.stderr[result.stderr.rfind("{") : result.stderr.rfind("}") + 1]
    )
    fields = {
        "measured_I": "input_i",
        "measured_TP": "input_tp",
        "measured_LRA": "input_lra",
        "measured_thresh": "input_thresh",
        "offset": "target_offset",
    }
    values = {key: float(measurement[source]) for key, source in fields.items()}
    if not all(math.isfinite(number) for number in values.values()):
        return "anull", {
            "preset": "web",
            "applied": False,
            "reason": "No measurable audible signal",
        }
    expression = "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:" + ":".join(
        f"{k}={v}" for k, v in values.items()
    )
    return expression, {
        "preset": "web",
        "applied": True,
        "target_lufs": -16,
        "true_peak_limit_dbtp": -1.5,
        "input_lufs": values["measured_I"],
    }


def assemble_scenes(value, output, *, root=None, chrome=None, deps=None):
    root = Path(root or Path.cwd()).resolve()
    output = workspace_path(root, output)
    if output.suffix.lower() != ".mp4":
        raise ValueError("Assembly output must end in .mp4")
    plan = preflight(value, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    renderer = renderer_fingerprint()
    unique_ids = list(dict.fromkeys(plan["scene_ids"]))

    def render(scene_id):
        return cached_scene(
            root,
            plan["sources"][scene_id],
            plan["width"],
            plan["height"],
            plan["fps"],
            renderer,
            chrome=chrome,
            deps=deps,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        rendered = dict(zip(unique_ids, pool.map(render, unique_ids)))
    scenes = [scene | rendered[scene["scene_id"]] for scene in plan["scenes"]]
    concat = output.with_suffix(".concat.txt")
    concat.write_text(
        "".join(
            "file '" + scene["video_path"].replace("'", "'\\''") + "'\n"
            for scene in scenes
        )
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
    ]
    normalization = None
    if plan["audio"]:
        expression, normalization = narration_filter(
            plan["audio"], plan["audio_normalization"]
        )
        # Delay is a timeline offset, not a seek into or a trim of the source.
        filters = f"{expression},aresample=48000,adelay={round(plan['narration_offset'] * 1000)}:all=1,apad"
        command.extend(
            [
                "-i",
                str(plan["audio"]),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-af",
                filters,
                "-ac",
                "2",
                "-ar",
                "48000",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]
        )
    else:
        command.extend(["-map", "0:v:0", "-an"])
    command.extend(
        [
            "-c:v",
            "copy",
            "-t",
            str(plan["duration"]),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    subprocess.run(command, check=True, stdout=sys.stderr)
    actual = probe(output)
    video = next(s for s in actual["streams"] if s["codec_type"] == "video")
    duration = float(video.get("duration") or actual["format"]["duration"])
    if abs(duration - plan["duration"]) > 1 / plan["fps"] + 0.001:
        raise ValueError(
            "Assembled video duration does not match its scene frame counts"
        )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"],
        check=True,
        stdout=sys.stderr,
    )
    report = {
        k: plan[k]
        for k in ("quality", "width", "height", "fps", "duration", "frame_count")
    }
    report.update(
        {
            "output": str(output),
            "scenes": scenes,
            "audio_normalization": normalization,
            "production_timing": {
                "scenes": [
                    {"title": scene["title"], "seconds": scene["seconds"]}
                    for scene in scenes
                ],
                "narration_offset": plan["narration_offset"],
            },
        }
    )
    output.with_suffix(".assembly.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--chrome")
    parser.add_argument("--deps", type=Path)
    args = parser.parse_args()
    if args.spec.stat().st_size > 50_000:
        parser.error("Assembly options exceed 50 KB")
    print(
        json.dumps(
            assemble_scenes(
                json.loads(args.spec.read_text()),
                args.output,
                chrome=args.chrome,
                deps=args.deps,
            )
        )
    )


if __name__ == "__main__":
    main()
