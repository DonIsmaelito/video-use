# One clear thought

An original sixteen-second typography film. The exact short brief is in `prompt.txt`; specific art direction and font provenance are separately recorded in `creative-contract.md`.

Edit `content.json` to replace every visible phrase, color, and construction seed. Copy is measured with the bundled fonts, so longer words scale to the authored line width. `scene.mjs` owns the film's composition and shot rhythm; `lib/motion.mjs` is a copied reusable, theme-free numeric/typographic runtime. Author a different film for a different idea instead of dispatching prompt keywords into this one.

Serve this directory through a local HTTP server, open `index.html`, and call `playPreview()` in the browser console for real-time playback. `seek(seconds)` reconstructs any frame in any order, after local fonts and content have loaded. File URLs do not support module/data loading correctly.

From the video-use repository root, render with the existing browser helper and an installed Puppeteer dependency directory:

```sh
node helpers/motion_render.mjs skills/motion-design/examples/kinetic-type/index.html \
  -o /path/to/output/one-clear-thought.mp4 --duration 16 \
  --width 1920 --height 1080 --fps 30 --poster-time 14 \
  --deps /path/to/dependency-project
```

The browser scene has no npm dependencies. Rendering requires Node, Puppeteer Core, Chrome, FFmpeg, and ffprobe as described in `references/browser-rendering.md`. Fonts and OFL redistribution notices are bundled. The runtime copy is byte-identical to `skills/motion-design/runtime/motion.mjs` when delivered; update the copy if you change shared mechanics.

The prompt alone is not a guarantee of exact future composition. Replaying the packaged source, content, fonts, and renderer is the mechanism for exact reproduction. No example selection or prompt-to-output lookup is included in this scene or runtime.
