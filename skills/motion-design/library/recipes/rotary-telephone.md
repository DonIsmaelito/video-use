# Rotary telephone

Original molded telephone geometry: a rounded wedge base, receiver with earpieces and cradle, a ten-hole rotary wheel with fixed finger stop, and a helical cord connected to the receiver and body port. The [module](rotary-telephone.mjs) owns parts and finite pose controls. The caller owns scene, lighting, camera and time. The ring movement and cable are authored kinematics, not a physical solver.

`createRotaryTelephone()` returns `group`, `base`, `handset`, `dial`, `cord`, `setState`, `controls`, and `dispose`. Add `group` to a Three.js scene. There are no labels or numerals in the geometry.

| `setState` input | Meaning |
| --- | --- |
| `assembly` | 0–1 body expansion and dial seating, default 1. |
| `handsetLift` | 0–1 receiver lift and attitude above its cradle, default 0. |
| `dialTurn` | Absolute finger-wheel rotation in radians, default 0. |
| `ring` | 0–1 small receiver vibration amplitude, default 0. |
| `cordLoop` | 0–1 extent of the connected cord's looping path, default 1. |
| `phase` | Absolute vibration phase, default 0. |

Every field resets to its default when omitted. Both cord endpoints are derived from the current receiver/body transforms, including the base's assembly scale. The cord is rebuilt from its absolute centerline and helical offset; no state accumulates between seeks. `dispose()` releases all owned geometry and materials and detaches the group. The Three.js import must resolve through a caller import map or bundler.

The portable [production caller](rotary-telephone-demo.html) accompanies this recipe. Its original project is `/private/tmp/motion-web-batch-20260914/11-rotary-telephone/index.html`. It exposes `window.seek(seconds)` and `window.motionReady`, and deliberately renders an eight-second silent film. Its control variant halves the maximum cord-loop extent while preserving camera, materials, phone geometry and timing. The exact prompt is preserved in that project's `PROMPT.md`.

Related registry IDs: `mediawork-pinterest-objects` for construction/contact logic and `polyhaven-studio-small-09-1k` for the optional CC0 studio environment. The phone and cable are original; reference films are not copied. The HDR stays project-local with its source/license receipt.

Validation: four representative source proofs and all 24 sampled encoded frames were inspected. Final export and the independent control caller each passed four exact repeated/backward seeks. The 240-frame, 1920 × 1080, 30 fps, 8.000-second H.264 export passes technical QA; ffprobe confirms zero audio streams. The native control variant was visually checked. Review is frame-sequence based, with no claim of normal-speed playback. Full evidence is in the production project’s REVIEW.md, final.render/render.json, control-proof.render/stills.json and final.qa/qa.json.
