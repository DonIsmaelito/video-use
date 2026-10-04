# Replay a Video Use library example

This archive preserves an authored example: its prompt, editable source, local assets, and project notes. Start with `edit/README.md` for that example's build order. Pasting its prompt into an agent starts a new interpretation; rendering the saved source reproduces the saved composition. Setup and visual verification are still required.

## 1. Get the recorded framework

Read the producer Git commit and snapshot information in `video-use-framework.json`. Older packages may instead record `frameworkCommit` in their provenance or in the companion `verification.json` linked from the example's published provenance. Keep the original archive. The snapshot SHA-256 identifies the production framework snapshot; it is not a Git commit and cannot be passed to `git checkout`.

Use a separate clone so replay does not change an existing Video Use installation. Replace the placeholders below with the recorded commit and your extracted folder; the project folder is the one containing `edit/`.

```sh
VIDEO_USE_ROOT="$HOME/Developer/video-use-replay"
VIDEO_USE_COMMIT="<recorded frameworkCommit>"
VIDEO_PROJECT_ROOT="/absolute/path/to/extracted-example"

git clone https://github.com/browser-use/video-use "$VIDEO_USE_ROOT"
git -C "$VIDEO_USE_ROOT" checkout --detach "$VIDEO_USE_COMMIT"
```

If that commit is unavailable from the public repository, obtain the matching published framework revision or snapshot from the example's maintainer. A production snapshot may contain branch changes beyond its recorded base commit; compare any recorded framework file hashes before claiming the same implementation. A current checkout can be used for a new render, but does not establish an exact replay of an unavailable snapshot. Retain its version and inspect the result.

## 2. Install tools and locked dependencies

Install Python 3.10+, `uv`, Node.js 22.12+, npm, Chrome or Chromium, and FFmpeg with `ffprobe`. These are external system requirements; `puppeteer-core` does not install a browser. See the checked-out repository's `install.md` for platform setup. Pure browser motion replay needs no transcription API key. A project that actually reruns transcription or another hosted tool has additional requirements in its own README.

```sh
uv sync --project "$VIDEO_USE_ROOT" --locked
source "$VIDEO_USE_ROOT/.venv/bin/activate"
cd "$VIDEO_PROJECT_ROOT"
npm ci --prefix edit/runtime
ffmpeg -version
ffprobe -version
node --version
```

Use the dependency directory named in the example's README if it differs from `edit/runtime`. Keep `package.json`, `package-lock.json`, and the framework's `uv.lock` together with their matching revisions. Use `npm ci`, not an update that replaces the recorded dependency versions. `dependencies.json` and render manifests record observed production versions; they are useful comparisons, not installers for every external tool. Install any project-specific dependencies documented by its build scripts as well.

## 3. Translate the container commands

Run the example's README commands from the extracted project folder, preserving its rendering, compositing, and audio stages:

| Production path or argument | Local replacement |
| --- | --- |
| `/opt/video-use/helpers/...` | `"$VIDEO_USE_ROOT/helpers/..."` |
| `--deps /opt/video-use/skills/motion-design/runtime` | `--deps edit/runtime`, or the packaged dependency directory |
| `--chrome /usr/bin/chromium` | Omit it to use browser discovery, or pass the installed browser executable |
| `/results/.../project/...` | The corresponding path below `"$VIDEO_PROJECT_ROOT"` |

Chrome discovery checks common macOS and Linux locations. For another installation, export `CHROME_PATH` with the full executable path, for example:

```sh
export CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

For a single HTML composition, the existing renderer accepts the following command shape. Substitute the entry file and delivery values from the example's README; additional compositing or audio commands may still be required to produce its final video.

```sh
node "$VIDEO_USE_ROOT/helpers/motion_render.mjs" edit/index.html \
  -o edit/replay.mp4 --deps edit/runtime \
  --duration 24 --width 1920 --height 1080 --fps 30
```

When the package instead includes `motion-project.json`, the manifest supplies the delivery settings. After restoring its required assets, use the existing project wrapper:

```sh
python "$VIDEO_USE_ROOT/helpers/motion_project.py" check /path/to/manifest-folder
python "$VIDEO_USE_ROOT/helpers/motion_project.py" render /path/to/manifest-folder \
  --deps /absolute/path/to/packaged/runtime --output /path/to/replay.mp4 --qa
```

A package with bundled `_video_use/` helpers may use those according to its own README. Do not invent a motion manifest for a package that uses authored scripts. Some examples have a one-source EDL pointing at their completed authored film; rebuild that source first rather than rendering an EDL over its own missing output.

## 4. Restore excluded media

Public library archives exclude raw audio/video and generated exports. Follow `edit/README.md` and `edit/provenance.json` to restore inputs before rendering.

- **Original synthesized audio:** run the included generator and use its documented output path. For example, the Pebble package provides `python edit/tool-proposals/tactile-audio/synthesize.py edit/assets/tactile.wav`. Preserve its seed and settings, then run its compositing step. Do not apply this command to examples without that script; silent examples need no audio file.
- **Licensed footage or audio:** obtain the recorded asset from its original source page or public download URL, check the recorded license and current availability, and save it at the path expected by the project. Preserve the required credits. Permission to publish an edited video does not necessarily permit redistributing the raw source file. Source hashes, where recorded, can verify that the acquired input matches; unavailable media requires an explicitly documented replacement and a new visual review.
- **Original screen recordings:** follow the project's capture/recreation instructions. A substitute recording changes the edit and must be checked against its timings.

## 5. Verify the result and preserve edits

Run the README's QA command with the example's actual dimensions, duration, frame rate, and audio expectations. Inspect the encoded video and frames, including text, diagram meaning, cut boundaries, and the final hold. Mechanical QA does not establish visual quality or semantic correctness.

Dependency locks and a recorded framework revision preserve important inputs, but Chrome builds, GPU drivers, operating systems, fonts, and FFmpeg versions can still change pixels or encoded bytes. A successful local replay is not a promise of an identical MP4 hash.

If the package has `checksums.json`, check the untouched package before editing. Preserve it as the reference; move the old checksum file outside a working copy before intentional source edits, then check and repackage the edited version with new checksums. Keep bundled licenses and attribution alongside any redistributed source. Record changed assets, dependencies, and content in the edited project's provenance.
