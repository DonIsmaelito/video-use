# Glass staircase

An original group of beveled colored tiles that cascades from an aligned stack into a radial spiral staircase. The [module](glass-staircase.mjs) owns tile geometry, material layers and absolute deformation state. The caller owns environment, camera, stage and timing. Real-time transmission and alpha blending approximate layered glass; this is not ray tracing or structural engineering.

`createGlassStaircase({ tileCount = 20, turns = 1.10 })` returns `group`, `tiles`, `setState`, `controls` and `dispose`. Tile count clamps to integers 10–30; turns clamps to 0.65–1.4. The shared original tile geometry includes small curved corners, thickness and beveled edges. Colored edge lines help retain the tread outline through overlapping transparent layers.

| `setState` input | Meaning |
| --- | --- |
| `cascade` | 0–1 progression of the staggered lower-to-upper release, default 1. |
| `spread` | 0.75–1.25 radial spread of the completed staircase, default 1. |
| `settle` | 0–1 damping of small residual vertical motion, default 1. |
| `phase` | Absolute residual-motion phase, default 0. |

All fields reset to defaults when omitted. Treads retain their vertical order and each long axis points radially into the completed staircase. The same part receives position, orientation and temporary lift from its local cascade value; no per-frame integration or animation loop is used. `dispose()` releases shared geometry and all owned materials, then detaches the group. Three.js must resolve through the caller's import map or bundler.

The portable [production caller](glass-staircase-demo.html) accompanies this recipe. Its original project is `/private/tmp/motion-web-batch-20260914/12-glass-staircase/index.html`. It exposes `window.seek(seconds)` and `window.motionReady` for an eight-second silent film. Its independent variant changes `turns` from 1.10 to 0.80 while retaining all 20 tiles, camera, lighting and timing. The exact prompt is preserved in that project's `PROMPT.md`.

Related registry IDs: `tendril-ibm-sovereign` for destination-led ordering of glass units, `ordinary-folk-webflow` for planes becoming a spatial arrangement, and `polyhaven-studio-small-09-1k` for optional CC0 studio reflections. The staircase geometry is original. Reference films remain reference-only; the HDR is acquired project-locally with its receipt.

Validation: four representative source proofs and all 24 sampled encoded frames were inspected. Final export and the independent control caller each passed four exact repeated/backward seeks. The 240-frame, 1920 × 1080, 30 fps, 8.000-second H.264 export passes technical QA; ffprobe confirms zero audio streams. The native control variant was visually checked. Review is frame-sequence based, with no claim of normal-speed playback. Full evidence is in the production project’s REVIEW.md, final.render/render.json, control-proof.render/stills.json and final.qa/qa.json.
