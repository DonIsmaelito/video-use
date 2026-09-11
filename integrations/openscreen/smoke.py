#!/usr/bin/env python3
"""Exercise the actual native runtime with a 4:3 picture and original AAC audio."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "helpers"))
from openscreen import export_project
from openscreen_project import prepare_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--app", type=Path, default=Path("/Applications/Openscreen.app"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = args.out.resolve()
    base.mkdir(parents=True, exist_ok=False)
    source = base / "square-and-tone.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i",
        "color=c=black:s=640x480:r=60:d=2,drawbox=x=220:y=140:w=200:h=200:color=white:t=fill",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-bsf:v", "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
        "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", str(source)], check=True)
    prepared = prepare_project(source, {"schema_version": 1, "zooms": [],
                                       "background": {"colors": ["#283653", "#101722"], "angle": 135}},
                               base / "project")
    output = base / "native-smoke.mp4"
    result = export_project(Path(prepared["manifest_path"]), args.runtime, args.app, output)
    rgb = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(output),
                                   "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    points = [i // 3 for i in range(0, len(rgb), 3)
              if rgb[i] > 245 and rgb[i + 1] > 245 and rgb[i + 2] > 245]
    if not points:
        raise AssertionError("Native picture lost the white square")
    xs, ys = [p % 1920 for p in points], [p // 1920 for p in points]
    width, height = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    if width < 200 or abs(width - height) > 2:
        raise AssertionError(f"Source geometry distorted: square became {width}x{height}")

    def audio_hash(path):
        packets = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                           "-map", "0:a:0", "-c", "copy", "-f", "adts", "-"])
        return hashlib.sha256(packets).hexdigest()
    if audio_hash(source) != audio_hash(output):
        raise AssertionError("Delivered AAC differs from original recording audio")
    report = {"status": "passed", "native_render": True, "square_pixels": [width, height],
              "original_aac_identical": True, "frames": 120,
              "export_result": str(Path(result["evidence_path"]) / "result.json")}
    (base / "smoke-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
