# Paper koi

An original illustrated koi that develops from a scored red square and swims with attached fins and a forked tail. The [module](paper-koi.mjs) owns anatomy, folded planes, grain and pose controls. It is a graphic interpretation of folded paper, not a physically valid origami simulation. Callers own their timeline, page, ink, camera-like staging and soundtrack.

`createPaperKoi({ seed, red, vermilion, dark, cream })` returns `draw(ctx, state)`, a list of pose `controls`, and `dispose()`. It needs a browser DOM to create its small procedural grain canvas. No third-party assets, fonts, dependencies, network calls or animation loops are used. Palette parameters set the principal paper colors; authored secondary red facets retain their fixed tonal relationships.

| State | Meaning |
| --- | --- |
| `x`, `y`, `scale`, `rotation` | Caller-controlled staging in Canvas coordinates; rotation in radians. Defaults: origin, scale 1, rotation 0. |
| `unfold` | 0–1 construction state. The same perimeter becomes the body, then pectoral fins and two tail lobes release in dependency order. Default 1. |
| `swim` | 0–1 amplitude of the swimming deformation and fin pulse. Default 0. |
| `phase` | Absolute swimming phase in radians. No accumulated animation state. Default 0. |
| `bend` | −1 to 1 body-space curvature, strongest at the tail. Default 0. |
| `finLift` | −1 to 1 fine adjustment of the pectoral projection. Default 0. |
| `tailSweep` | Fine tail rotation; values around −1 to 1 are the intended range. Default 0. |
| `shadow` | Opacity multiplier for the soft body shadow. Default 1. |

Draw the whole canvas background before each frame, then call `draw` with all animated values. Omitted values reset to defaults. All body, fins, facial details and tail points use the same deformation mapping; the tail has additional local sweep around its body attachment. During construction one body half projects around the central spine, lifting toward edge-on before settling. The recipe restores the caller's Canvas transform and drawing state. `dispose()` releases its procedural grain canvas; do not draw after disposal.

At scale 1 the fully unfolded hero occupies approximately x −405 to 290 and y −200 to 200 before bend or rotation. Reserve additional room for animated curvature and a rotated tail. Inspect the middle of the unfolding action as well as the full silhouette: the construction pose must read as connected paper rather than separate animated triangles. A near-black eye on the cream eye patch and the tiny barbels should survive final output downscaling.

The portable [demonstration](paper-koi-demo.html) maps the simple prompt “Make a red paper koi unfold from a square and swim through blue ink ripples.” into an eight-second wordless film. It exports deterministic `window.seek(seconds)` and `window.motionReady`, so the repository browser renderer can capture arbitrary and backward time positions. Its original production workspace is `/private/tmp/motion-five-prompts-20260914/01-paper-koi/`.

The library discovery records informing this original recipe are `ordinary-folk-dreams` (character pose), `mediawork-office-motion-tests` (anchored deformation proof), and `mediawork-pinterest-objects` (hinged construction and material logic). These third-party works remain reference-only; none of their artwork or footage is included.

Validation: the final demonstration passed four exact repeated/backward seeks and encoded QA for 240 frames, 1920 × 1080, 30 fps, eight seconds and stereo audio. Full-size proof poses and a 20-sample encoded sequence were visually inspected. A separate `control-proof.html` caller renders `unfold` 0.46 beside 1 with other pose values fixed, demonstrating a visible structural control change; its four repeated/backward seeks also passed. Its evidence lives under the demonstration's `control-proof.render/`. This is frame-sequence review, not a claim of normal-speed playback. Palette variants have not been visually checked.

The demonstration owns its own page grain and expanding blue ink; neither is required to reuse the character. It exercises construction, swimming, phase, curvature, fin lift and tail sweep. The final source and project-local recipe copy share SHA-256 `ba9c10f41c4a25c28a56c62e1d11aa9cbf3c5914f61e85d39141b11bb7db43a9`.
