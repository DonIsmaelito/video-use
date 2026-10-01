"""Render immutable original reference clips with the video-use motion harness."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
SAMPLES = {
    "diagram": (
        "Diagram-led",
        "Show the mechanism through geometry and relationships.",
    ),
    "editorial": (
        "Editorial motion",
        "Illustration, bold type and a more tactile visual story.",
    ),
    "captions_quiet": (
        "Quiet captions",
        "Restrained subtitles that keep attention on the speaker.",
    ),
    "captions_bold": (
        "Emphasized captions",
        "Higher contrast and stronger emphasis for short clips.",
    ),
    "demo_focus": (
        "Interface focus",
        "Readable actions, focused zooms and restrained callouts.",
    ),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--deps", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "samples": {}}
    for key, (label, description) in SAMPLES.items():
        source = BASE / "source" / f"{key}.html"
        source.write_text(
            (BASE / "source/scene.html").read_text().replace("__KIND__", key)
        )
        target = out / f"{key}.mp4"
        subprocess.run(
            [
                "node",
                str(ROOT / "helpers/motion_render.mjs"),
                str(source),
                "-o",
                str(target),
                "--deps",
                a.deps,
                "--duration",
                "4",
                "--width",
                "960",
                "--height",
                "540",
                "--fps",
                "24",
                "--preset",
                "fast",
                "--poster-time",
                "2.8",
                "--stills",
                "0.6,1.6,2.8",
                "--overwrite",
            ],
            check=True,
        )
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest["samples"][key] = {
            "label": label,
            "description": description,
            "sha256": sha,
            "file": f"{key}.mp4",
            "duration": 4,
            "width": 960,
            "height": 540,
            "authored": True,
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
