#!/usr/bin/env python3
"""Build the pinned OpenScreen CLI using the installed app's native renderer."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import subprocess

SHA = "47ab52fd0907ed07336fa1ff868e671d5d5a469f"
PATCH_DIR = Path(__file__).resolve().parent / "patches"
PATCHES = (
    PATCH_DIR / "cli-source-dimensions.patch",
    PATCH_DIR / "cli-cursor-settings.patch",
    PATCH_DIR / "cli-wallpaper-file-url.patch",
)


def run(command, cwd=None):
    subprocess.run(command, cwd=cwd, check=True)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stamp(runtime, app):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=runtime, text=True).strip()
    if revision != SHA:
        raise ValueError("Expected the pinned OpenScreen v1.11.0 checkout")
    for patch in PATCHES:
        run(["git", "apply", "--reverse", "--check", str(patch)], runtime)
    addon = app / "Contents/Resources/electron/native/bin/darwin-arm64/compositor_view.node"
    files = list((runtime / "dist").rglob("*")) + list((runtime / "dist-electron").rglob("*"))
    if not files or not (runtime / "dist/index.html").exists():
        raise ValueError("Run npm run build-vite before stamping the runtime")
    files += list((runtime / "src/cli").rglob("*.ts*"))
    files.append(runtime / "src/components/video-editor/projectPersistence.ts")
    files.append(runtime / "electron/native-bridge/services/compositorViewService.ts")
    native_dir = addon.parent
    native_files = {str(p.relative_to(native_dir)): digest(p)
                    for p in native_dir.rglob("*") if p.is_file()}
    manifest = {"schema_version": 1, "upstream_sha": SHA,
                "patches": {patch.name: digest(patch) for patch in PATCHES},
                "native_addon_sha256": digest(addon),
                "native_files": native_files,
                "files": {str(p.relative_to(runtime)): digest(p) for p in files if p.is_file()}}
    (runtime / "video-use-runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Runtime ready: {runtime}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--app", type=Path, default=Path("/Applications/Openscreen.app"))
    parser.add_argument("--stamp-existing", action="store_true",
                        help="Record a checkout already patched, tested and built")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("This first integration is tested on Apple Silicon macOS only")
    app, runtime = args.app.resolve(), args.runtime.resolve()
    with (app / "Contents/Info.plist").open("rb") as f:
        version = plistlib.load(f)["CFBundleShortVersionString"]
    if version != "1.11.0":
        raise ValueError("Install official OpenScreen 1.11.0 first; see README")
    if not args.stamp_existing:
        if runtime.exists():
            raise ValueError("Choose a new runtime directory; existing work is never replaced")
        run(["git", "clone", "--depth", "1", "--branch", "v1.11.0",
             "https://github.com/getopenscreen/openscreen.git", str(runtime)])
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=runtime, text=True).strip()
        if revision != SHA:
            raise ValueError("Upstream tag changed; refusing to install an unpinned runtime")
        for patch in PATCHES:
            run(["git", "apply", str(patch)], runtime)
        run(["npm", "ci"], runtime)
        run(["npx", "vitest", "--run", "src/cli/probedVideoMetadata.test.ts",
             "src/cli/cursorSettings.test.ts",
             "electron/native-bridge/services/compositorViewService.test.ts",
             "src/components/video-editor/projectPersistence.test.ts"], runtime)
        run(["npx", "tsc", "--noEmit"], runtime)
        run(["npx", "tsc", "-p", "tsconfig.test.json", "--noEmit"], runtime)
        run(["npm", "run", "build-vite"], runtime)
    stamp(runtime, app)


if __name__ == "__main__":
    main()
