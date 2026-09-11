#!/usr/bin/env python3
"""Test actual native cursor exports using explicitly synthetic footage/telemetry.

This is a renderer regression fixture, not evidence of a real OS recording.
Pillow and NumPy are existing Video Use dependencies. No capture permissions or
physical mouse input are used. Both native exports run sequentially.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "helpers"))
from openscreen import export_project
from openscreen_project import prepare_project


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def fixture(base):
    image = Image.new("RGB", (1280, 720), "#1d3449")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except OSError:
        font = small = ImageFont.load_default()
    draw.rounded_rectangle((28, 28, 1252, 125), radius=14, fill="#28475e")
    draw.text((54, 46), "PRODUCT WORKSPACE", font=font, fill="#edf4ff")
    draw.text((55, 87), "SYNTHETIC CURSOR TEST  /  NOT A REAL RECORDING", font=small, fill="#a0c8de")
    draw.rounded_rectangle((28, 149, 217, 691), radius=12, fill="#28475e")
    for y, label in ((181, "Projects"), (235, "Assets"), (289, "Exports")):
        draw.text((49, y), label, font=small, fill="#b8d9e6")
    draw.rounded_rectangle((243, 149, 1252, 691), radius=12, fill="#365e77")
    # A unique color fiducial measures the camera independently of the cursor.
    draw.rectangle((660, 215, 739, 294), fill="#f626e6")
    still = base / "synthetic-ui.png"
    image.save(still)
    source = base / "synthetic-ui.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-n", "-loop", "1", "-framerate", "60", "-i", str(still),
        "-t", "15", "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-bsf:v", "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
        "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", str(source),
    ], check=True)
    samples = []
    for frame in range(901):
        t = frame / 60
        if t < 2.5:
            x, y = .35, .58
        elif t < 3.5:
            x, y = .35 + .05 * (t - 2.5), .58
        elif t < 7:
            x, y = .4, .58
        elif t < 9:
            x, y = .4 + .02 * (t - 7) / 2, .58 + .12 * (t - 7) / 2
        elif t < 10:
            x, y = .42, .7
        elif t < 11.5:
            x, y = .42 + .22 * (t - 10) / 1.5, .7
        else:
            x, y = .64, .7
        event = {240: "click", 249: "mouseup", 600: "click", 690: "mouseup"}.get(frame, "move")
        samples.append({"timeMs": round(t * 1000, 3), "cx": x, "cy": y,
                        "cursorType": "arrow", "interactionType": event,
                        "visible": True, "assetId": None})
    write_json(Path(str(source) + ".cursor.json"), {
        "version": 2, "provider": "native", "samples": samples, "assets": [],
    })
    capture = base / "synthetic-capture.openscreen"
    write_json(capture, {
        "version": 2,
        "media": {"screenVideoPath": str(source), "cursorCaptureMode": "editable-overlay"},
        "editor": {},
    })
    write_json(base / "fixture-provenance.json", {
        "synthetic": True, "real_capture": False, "source_contains_cursor": False,
        "description": "Generated UI and authored 60 Hz cursor telemetry for renderer testing only",
        "click_s": 4, "drag_start_s": 10, "drag_end_s": 11.5,
        "duration_s": 15,
    })
    return source, capture


def frame_at(path, seconds):
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path),
        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    return np.frombuffer(raw, dtype=np.uint8).reshape(1080, 1920, 3)


def bbox(mask, label):
    ys, xs = np.nonzero(mask)
    if len(xs) < 10:
        raise AssertionError(f"Missing {label} in encoded frame")
    return {"x": int(xs.min()), "y": int(ys.min()),
            "width": int(xs.max() - xs.min() + 1),
            "height": int(ys.max() - ys.min() + 1), "pixels": len(xs)}


def measure(frame):
    r, g, b = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
    marker = bbox((r > 185) & (g < 100) & (b > 170), "magenta camera fiducial")
    mask = (r > 215) & (g > 215) & (b > 215)
    mask[:400, :] = False
    mask[880:, :] = False
    mask[:, :400] = False
    mask[:, 1650:] = False
    cursor = bbox(mask, "white cursor edge")
    return {"marker": marker, "cursor": cursor}


def check(base, outputs):
    measurements = {}
    moments = [2, 3.9, 4.05, 4.17, 4.5, 10.2, 11.3, 14]
    contact = Image.new("RGB", (960 * 2, 540 * len(moments)), "#142537")
    for column, (name, path) in enumerate(outputs.items()):
        measurements[name] = {}
        for row, seconds in enumerate(moments):
            frame = frame_at(path, seconds)
            measurements[name][str(seconds)] = measure(frame)
            tile = Image.fromarray(frame).resize((960, 540), Image.Resampling.LANCZOS)
            ImageDraw.Draw(tile).text((12, 12), f"SYNTHETIC TEST  {name}  {seconds}s", fill="white")
            contact.paste(tile, (column * 960, row * 540))
    contact.save(base / "encoded-cursor-contact-sheet.jpg", quality=90)
    write_json(base / "cursor-measurements.json", measurements)
    control, polished = measurements["control"], measurements["polished"]
    size_ratio = polished["2"]["cursor"]["height"] / control["2"]["cursor"]["height"]
    if size_ratio < 1.35:
        raise AssertionError(f"Enlarged cursor did not reach native output: ratio={size_ratio}")
    click_press = polished["4.05"]["cursor"]["height"]
    click_rebound = polished["4.17"]["cursor"]["height"]
    if click_rebound < click_press * 1.2:
        raise AssertionError("Native click bounce did not compress and rebound the cursor")
    zoom_ratio = polished["4.5"]["marker"]["width"] / polished["2"]["marker"]["width"]
    if zoom_ratio < 1.08:
        raise AssertionError(f"Click-driven camera zoom missing: ratio={zoom_ratio}")
    marker_shift = polished["10.2"]["marker"]["x"] - polished["11.3"]["marker"]["x"]
    control_shift = control["10.2"]["marker"]["x"] - control["11.3"]["marker"]["x"]
    if marker_shift < 20 or abs(control_shift) > 2:
        raise AssertionError(f"Drag camera follow missing: shift={marker_shift}, control={control_shift}")
    if abs(polished["14"]["marker"]["width"] - control["14"]["marker"]["width"]) > 2:
        raise AssertionError("Camera did not return to final overview")
    return {"cursor_height_ratio": size_ratio, "click_press_height": click_press,
            "click_rebound_height": click_rebound, "click_zoom_ratio": zoom_ratio,
            "drag_camera_shift_px": marker_shift, "control_camera_shift_px": control_shift,
            "final_overview_restored": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--app", type=Path, default=Path("/Applications/Openscreen.app"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = args.out.resolve()
    base.mkdir(parents=True, exist_ok=False)
    source, capture = fixture(base)
    outputs, exports = {}, {}
    for name in ("control", "polished"):
        polished = name == "polished"
        spec = {
            "schema_version": 1, "zooms": [],
            "background": {"colors": ["#246174", "#172b48"], "angle": 135},
            "cursor": {"mode": "recorded", "size": 4.5 if polished else 3,
                       "smoothing": .67, "motion_blur": .2,
                       "click_bounce": 1.0 if polished else 0,
                       "interaction_zooms": polished, "zoom_depth": 1},
        }
        prepared = prepare_project(source, spec, base / f"{name}-project", recording_project=capture)
        output = base / f"synthetic-{name}.mp4"
        exports[name] = export_project(Path(prepared["manifest_path"]), args.runtime, args.app, output)
        outputs[name] = output
    checks = check(base, outputs)
    report = {"status": "passed", "synthetic_fixture": True, "real_capture_tested": False,
              "native_render": True, "frames_per_export": 900, "checks": checks,
              "exports": {name: str(Path(result["evidence_path"]) / "result.json")
                          for name, result in exports.items()}}
    write_json(base / "cursor-smoke-result.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
