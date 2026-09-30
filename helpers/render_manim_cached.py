"""Render named Manim scenes once per source/settings version; reuse for audio edits.

python /opt/video-use/helpers/render_manim_cached.py edit/animations/script.py \
    SceneOne SceneTwo --quality preview
Outputs JSON with ordered video paths. Mix audio and mux those files separately.
Pass --dependency for non-Python inputs that affect the animation.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def render(source, scenes, quality="preview", dependencies=(), output=None):
    source = Path(source).resolve()
    # Adjacent Python helpers participate in invalidation. Audio does not unless
    # explicitly named as a dependency: mixing it should not rerender visuals.
    inputs = sorted(
        set(source.parent.glob("*.py"))
        | {source}
        | {Path(p).resolve() for p in dependencies}
    )
    settings = {"preview": (960, 540, 15), "final": (1920, 1080, 30)}[quality]
    digest = hashlib.sha256(json.dumps(settings).encode())
    for path in inputs:
        digest.update(str(path).encode())
        digest.update(path.read_bytes())
    root = (
        Path(output or source.parent / "media" / "video-use-cache").resolve()
        / digest.hexdigest()[:20]
    )
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.json"
    cached = json.loads(manifest.read_text()) if manifest.exists() else {}
    missing = [
        name
        for name in scenes
        if not cached.get(name) or not Path(cached[name]).is_file()
    ]
    if missing:
        width, height, fps = settings
        subprocess.run(
            [
                "manim",
                "-r",
                f"{width},{height}",
                "--frame_rate",
                str(fps),
                "--progress_bar",
                "none",
                "--media_dir",
                str(root),
                str(source),
                *missing,
            ],
            check=True,
            stdout=__import__("sys").stderr,
        )
        for name in missing:
            files = list(root.glob(f"videos/{source.stem}/*/{name}.mp4"))
            if len(files) != 1:
                raise RuntimeError(f"Expected one rendered output for {name}")
            cached[name] = str(files[0])
        manifest.write_text(json.dumps(cached, indent=2))
    return {
        "quality": quality,
        "rendered": missing,
        "reused": [s for s in scenes if s not in missing],
        "videos": [cached[s] for s in scenes],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("scenes", nargs="+")
    parser.add_argument("--quality", choices=("preview", "final"), default="preview")
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    print(
        json.dumps(
            render(args.source, args.scenes, args.quality, args.dependency, args.output)
        )
    )


if __name__ == "__main__":
    main()
