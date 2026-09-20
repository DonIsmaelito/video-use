# Browser motion rendering

## Runtime and project boundary

The repository helper [motion_render.mjs](../../../helpers/motion_render.mjs) serves a local HTML composition, calls its absolute-time function, captures Chrome frames, and encodes a video with FFmpeg. It is a direct renderer, not a HyperFrames or Remotion project adapter. Use those frameworks' native render commands for their compositions unless deliberately implementing the direct contract.

Keep dependencies in the isolated animation project or a designated dependency directory, never install them into the video-use root merely for one film. Required tools are Node, compatible Puppeteer Core (or Puppeteer), local Chrome, FFmpeg, and ffprobe. Match Node to the installed Puppeteer package's `engines`; the tested configuration used Node 22.14 with Puppeteer Core 25.10, whose minimum was Node 22.12. Three.js is optional and the demonstrations used 0.186.0. Pin selected package versions and retain the lockfile.

Inspect current flags with `node helpers/motion_render.mjs --help`. `--deps` identifies the project containing Puppeteer; it need not be the same directory as the composition's Three.js bundle. `--chrome` or `CHROME_PATH` selects a browser explicitly when default discovery does not find one.

## Frame contract

The HTML must expose `window.seek(seconds)`. Its returned promise, if any, is awaited. `window.motionReady` is optional and should resolve after initial resources are usable. At time `frame / fps`, all visible state must follow from that time and fixed inputs, independent of previous seek order.

Drive paused animation timelines, procedural geometry, materials, camera, and canvas content from the supplied time. Reset mutable drawing state or assign every affected property. Use seeded data generated once, not random numbers sampled per frame. Keep wall-clock timers and autoplay out of render-critical state.

Explicitly await asynchronous resources that the DOM cannot enumerate: detached `Image` objects used by canvas, decoded image bitmaps, WebGL textures, imported models, shader setup, and dynamically requested media. `document.fonts.ready` does not request a font that has never been used; load required faces explicitly before measuring or drawing. The helper awaits document images and fonts around capture, but it cannot infer an unregistered texture promise inside application code. Include those in `motionReady` or await them in `seek` when the resource changes with time.

Set your logical drawing resolution and camera aspect to the requested width/height. CSS stretching a fixed canvas changes its proportions; changing only the capture viewport does not recompose the scene. For Three.js, use the intended output color space and tone mapping and verify its rendered highlights.

## Local assets

Bundle image, media, font, script, and model dependencies under the served root. The default root is the HTML directory. Use `--root` only when the required local hierarchy spans a wider directory; the HTML must remain inside it. Resolve module imports from local paths or an import map pointing to local bundles.

Remote requests are blocked by default, which exposes hidden CDN dependencies before export. `--allow-remote` exists for an intentional exception, but local files and pinned versions are preferable for a reproducible project. The render manifest records served asset hashes. A valid file path is insufficient if its image is still undecoded when canvas draws it.

## Proof frames and export

Commands below run from the video-use repository root. Substitute the real isolated project and dependency paths.

```bash
node helpers/motion_render.mjs /path/to/scene/index.html \
  -o /path/to/scene/final.mp4 --duration 14 \
  --width 1920 --height 1080 --fps 30 --deps /path/to/dependencies \
  --stills-only --stills 0,2.5,6.2,10.8,13.9 --poster-time 10.8

node helpers/motion_render.mjs /path/to/scene/index.html \
  -o /path/to/scene/final.mp4 --duration 14 \
  --width 1920 --height 1080 --fps 30 --deps /path/to/dependencies \
  --audio /path/to/scene/soundtrack.wav --poster-time 10.8

python3 helpers/motion_qa.py /path/to/scene/final.mp4 \
  --expect-width 1920 --expect-height 1080 --expect-fps 30 \
  --expect-duration 14 --expect-audio
```

Choose a duration whose product with fps is an integer. Still times must be below duration; the last frame of 14 seconds at 30fps is 13.9667 seconds. Use `--overwrite` only when replacing the intended existing final output.

The helper checks repeated and backward seeks before rendering. On mismatch, inspect its expected and observed PNG diagnostics. Accelerated canvas text rasterization can cause cache-dependent pixels; a CPU canvas context may be appropriate when the content uses canvas typography. Do not confuse GPU sampling noise with accumulated animation state, and do not silently skip the check.

The final render directory contains the poster, requested stills, and `render.json` with runtime, frame checks, asset hashes, and export metadata. Still-only runs write `stills.json`. [motion_qa.py](../../../helpers/motion_qa.py) decodes the exported movie, checks delivery properties and audio, and creates a contact sheet plus `qa.json`. Holds and large frame changes are review cues because deliberate pauses and cuts are valid design decisions. These checks do not evaluate artistic quality; apply [critique.md](critique.md) to the visible result.

## Editable handoff

Package the HTML and authored modules, content inputs, local assets, score, required helper versions or repository revision, package manifest/lockfile, and exact render command. Explain where to change copy, palette, timing, and camera or geometry controls. Include fonts only when their terms permit redistribution; otherwise document the needed font and any substitution.

Verify one real content or control edit in a temporary copy when editability is part of the deliverable. Restore the intended values afterward. A browser composition is editable source for this renderer; it is not an editable After Effects or Blender project.
