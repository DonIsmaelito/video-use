"""Prepare full-length product demos for the pinned OpenScreen native renderer.

This module writes projects and evidence; it does not render or approve pictures.
Background units are OpenScreen's native slider units, not the older scene spec.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


OPENSCREEN_VERSION = "1.11.0"
OPENSCREEN_REVISION = "47ab52fd0907ed07336fa1ff868e671d5d5a469f"
OUTPUT_FPS = 60
ZOOM_IN_S = 1.01505 * 1.5
ZOOM_OUT_S = 1.01505
MIN_OVERVIEW_GAP_S = 2.0
MIN_EDGE_OVERVIEW_S = 1.0
DEFAULT_BACKGROUND = {
    "colors": ["#283653", "#101722"],
    "angle": 135,
    "padding": 30,
    "border_radius": 24,
    "shadow": 0.35,
    "motion_blur": 0.15,
}


def read_json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=pairs)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _object(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown {label} keys: {', '.join(sorted(map(str, unknown)))}")
    return value


def _number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be finite and between {low} and {high}")
    return value


def validate_spec(spec: dict, duration_s: float) -> dict:
    """Validate the small authoring contract, including native zoom envelopes.

    Each focus hold lasts 0.25–3 seconds. Native transitions must leave a full
    second of overview at both ends and two seconds between complete envelopes.
    This also prevents OpenScreen's automatic chaining of neighboring zooms.
    """
    _number(duration_s, 0.001, 24 * 3600, "source duration")
    spec = _object(spec, {"schema_version", "background", "zooms"}, "spec")
    version = spec.get("schema_version", 1)
    if type(version) is not int or version != 1:
        raise ValueError("schema_version must be 1")
    background = _object(spec.get("background", {}), DEFAULT_BACKGROUND, "background")
    background = {**DEFAULT_BACKGROUND, **background}
    colors = background["colors"]
    if not isinstance(colors, list) or len(colors) != 2:
        raise ValueError("background.colors requires exactly two colors")
    if any(not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in colors):
        raise ValueError("background.colors requires #RRGGBB colors")
    background["colors"] = [c.lower() for c in colors]
    for key, bounds in {
        "angle": (0, 360), "padding": (0, 100), "border_radius": (0, 200),
        "shadow": (0, 1), "motion_blur": (0, 1),
    }.items():
        _number(background[key], *bounds, f"background.{key}")
    raw_zooms = spec.get("zooms", [])
    if not isinstance(raw_zooms, list):
        raise ValueError("zooms must be an array")
    zooms = []
    last_effect_end = None
    for index, raw in enumerate(raw_zooms):
        label = f"zooms[{index}]"
        _object(raw, {"settle_s", "hold_end_s", "depth", "focus", "reason"}, label)
        required = {"settle_s", "hold_end_s", "depth", "focus", "reason"}
        if required - raw.keys():
            raise ValueError(f"{label} missing: {', '.join(sorted(required - raw.keys()))}")
        settle = round(_number(raw["settle_s"], 0, duration_s, f"{label}.settle_s"), 3)
        end = round(_number(raw["hold_end_s"], 0, duration_s, f"{label}.hold_end_s"), 3)
        if not 0.25 - 1e-9 <= end - settle <= 3 + 1e-9:
            raise ValueError(f"{label} settled hold must last 0.25 to 3 seconds")
        depth = raw["depth"]
        if type(depth) is not int or not 1 <= depth <= 6:
            raise ValueError(f"{label}.depth must be an integer from 1 to 6")
        focus = raw["focus"]
        if not isinstance(focus, list) or len(focus) != 2:
            raise ValueError(f"{label}.focus must be [cx, cy]")
        for value in focus:
            _number(value, 0, 1, f"{label}.focus")
        reason = raw["reason"]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValueError(f"{label}.reason must contain 1 to 500 characters")
        effect_start, effect_end = settle - ZOOM_IN_S, end + ZOOM_OUT_S
        if effect_start < MIN_EDGE_OVERVIEW_S or effect_end > duration_s - MIN_EDGE_OVERVIEW_S:
            raise ValueError(f"{label} must leave at least 1 second of opening and final overview")
        if last_effect_end is not None and effect_start - last_effect_end < MIN_OVERVIEW_GAP_S:
            raise ValueError(f"{label} must be ordered with 2 seconds of overview between zooms")
        last_effect_end = effect_end
        zooms.append({"settle_s": settle, "hold_end_s": end, "depth": depth,
                      "focus": list(focus), "reason": reason.strip()})
    return {"schema_version": 1, "background": background, "zooms": zooms}


def probe_source(source: Path) -> dict:
    """Reject unsupported color, aspect, rotation and timeline inputs explicitly."""
    source = Path(source).resolve(strict=True)
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source),
    ], check=True, capture_output=True, text=True, timeout=60)
    raw = json.loads(result.stdout)
    videos = [s for s in raw.get("streams", []) if s.get("codec_type") == "video"]
    if len(videos) != 1:
        raise ValueError("The import route requires exactly one video stream")
    video = videos[0]
    if video.get("codec_name") not in {"h264", "hevc"} or video.get("pix_fmt") != "yuv420p":
        raise ValueError("The import route requires 8-bit H264 or HEVC yuv420p footage")
    if (video.get("color_range") != "tv" or
            any(video.get(k) != "bt709" for k in ("color_space", "color_transfer", "color_primaries"))):
        raise ValueError("Native rendering requires tagged BT709 limited-range SDR footage; normalize explicitly first")
    sar = video.get("sample_aspect_ratio")
    if sar not in {None, "N/A", "1:1"}:
        raise ValueError("Native rendering requires square source pixels")
    rotations = [video.get("tags", {}).get("rotate", 0)]
    rotations.extend(item.get("rotation", 0) for item in video.get("side_data_list", []))
    try:
        if any(not math.isfinite(float(r)) or float(r) % 360 != 0 for r in rotations):
            raise ValueError("Native rendering requires footage without rotation metadata")
        start = float(video.get("start_time", 0))
        duration = float(video.get("duration", raw.get("format", {}).get("duration", 0)))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Unsupported source timing or rotation: {error}") from error
    if not math.isfinite(start) or abs(start) > 0.001:
        raise ValueError("Native rendering requires a source timeline starting at zero")
    _number(duration, 0.001, 24 * 3600, "source duration")
    width, height = video.get("width"), video.get("height")
    if any(type(n) is not int or n <= 0 or n % 2 for n in (width, height)):
        raise ValueError("Native rendering requires positive even source dimensions")
    audio = [s for s in raw.get("streams", []) if s.get("codec_type") == "audio"]
    if len(audio) > 1:
        raise ValueError("Select or mix the recording's audio tracks before this route")
    if audio:
        try:
            audio_start = float(audio[0].get("start_time", 0))
            audio_duration = float(audio[0].get("duration", "nan"))
        except (TypeError, ValueError) as error:
            raise ValueError("Audio timing must be known before preserving it") from error
        if not math.isfinite(audio_start) or abs(audio_start) > 0.001:
            raise ValueError("Audio must start at zero to preserve the original timeline")
        if not math.isfinite(audio_duration) or audio_duration <= 0:
            raise ValueError("Audio duration must be known before preserving it")
        if audio_start + audio_duration > duration + 1 / OUTPUT_FPS + 0.001:
            raise ValueError("Audio extends beyond the video; resolve the timeline explicitly first")
    return {"width": width, "height": height, "duration_s": duration,
            "codec": video["codec_name"], "pixel_format": video["pix_fmt"],
            "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709",
            "color_range": "tv", "sample_aspect_ratio": "1:1", "rotation": 0,
            "has_audio": bool(audio), "audio_stream_count": len(audio),
            **({"audio_codec": audio[0].get("codec_name"), "audio_duration_s": audio_duration,
                "audio_start_s": audio_start} if audio else {})}


def build_project(copied_source: Path, normalized_spec: dict) -> dict:
    """Build the supported v2 envelope; source duration is probed by OpenScreen."""
    background = normalized_spec["background"]
    c0, c1 = background["colors"]
    zooms = [{"id": f"product-focus-{i + 1}",
              "startMs": round(cue["settle_s"] * 1000) - 500,
              "endMs": round(cue["hold_end_s"] * 1000), "depth": cue["depth"],
              "focus": {"cx": cue["focus"][0], "cy": cue["focus"][1]},
              "focusMode": "manual", "source": "manual"}
             for i, cue in enumerate(normalized_spec["zooms"])]
    return {
        "version": 2,
        "media": {"screenVideoPath": str(Path(copied_source).resolve()), "cursorCaptureMode": "system"},
        "editor": {
            "wallpaper": f"linear-gradient({background['angle']}deg, {c0}, {c1})",
            "shadowIntensity": background["shadow"], "showBlur": False,
            "motionBlurAmount": background["motion_blur"],
            "borderRadius": background["border_radius"], "padding": background["padding"],
            "cropRegion": {"x": 0, "y": 0, "width": 1, "height": 1},
            "zoomRegions": zooms, "cameraFullscreenRegions": [],
            "autoZoomEnabled": False, "autoFocusAll": False,
            "trimRegions": [], "speedRegions": [], "annotationRegions": [],
            "aspectRatio": "16:9", "webcamLayoutPreset": "no-webcam",
            "webcamMaskShape": "rectangle", "webcamMirrored": False,
            "webcamReactiveZoom": False, "webcamSizePreset": 25, "webcamPosition": None,
            "exportQuality": "good", "exportFormat": "mp4", "gifFrameRate": 15,
            "gifLoop": True, "gifSizePreset": "medium", "cursorTheme": "default",
        },
    }


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare_project(source: Path, spec: dict, destination: Path) -> dict:
    """Create a fresh, self-contained input bundle. Never mark an export verified."""
    source, destination = Path(source).resolve(strict=True), Path(destination).resolve()
    if destination.exists():
        raise ValueError(f"Destination already exists; choose a fresh directory: {destination}")
    metadata = probe_source(source)
    normalized = validate_spec(spec, metadata["duration_s"])
    source_hash = sha256_file(source)
    if shutil.disk_usage(destination.parent if destination.parent.exists() else source.parent).free < source.stat().st_size + 16 * 1024 * 1024:
        raise ValueError("Insufficient free space to copy the source into a project bundle")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        media_path = destination / f"recording{source.suffix.lower()}"
        shutil.copy2(source, media_path)
        if sha256_file(media_path) != source_hash:
            raise ValueError("Source bytes changed while preparing the project")
        project_path, spec_path = destination / "demo.openscreen", destination / "demo-spec.json"
        _write_json(project_path, build_project(media_path, normalized))
        _write_json(spec_path, normalized)
        native_duration = min(metadata["duration_s"], math.floor(metadata["duration_s"] * 1000 + 0.5) / 1000)
        frames = max(1, math.ceil((native_duration - 0.001) * OUTPUT_FPS))
        manifest = {
            "schema_version": 1, "status": "prepared", "render_verified": False,
            "openscreen": {"version": OPENSCREEN_VERSION, "revision": OPENSCREEN_REVISION,
                           "requires_cli_dimension_fix": True},
            "artifacts": {
                "source": {"path": media_path.name, "sha256": source_hash, "bytes": media_path.stat().st_size},
                "project": {"path": project_path.name, "sha256": sha256_file(project_path)},
                "spec": {"path": spec_path.name, "sha256": sha256_file(spec_path)},
            },
            "source_metadata": metadata,
            "expected_video": {"width": 1920, "height": 1080, "fps": OUTPUT_FPS,
                               "frame_count": frames, "duration_s": frames / OUTPUT_FPS},
            "timeline": {"source_start_s": 0, "source_end_s": metadata["duration_s"], "speed": 1,
                         "cuts": [], "cursor": "baked source cursor retained; no sidecar copied"},
        }
        manifest_path = destination / "manifest.json"
        _write_json(manifest_path, manifest)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {**manifest, "project_path": str(project_path), "source_path": str(media_path),
            "manifest_path": str(manifest_path)}
