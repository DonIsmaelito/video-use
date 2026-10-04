# Tool decisions from the useful workflow campaign

The parent reviews project-local proposals before changing the framework.
Existing films retain their original producer commit and snapshot; subsequent
containers receive the updated shared tools. Projects and public source bundles
keep their own editable composition code and dependency notices.

| Evidence | Shared decision | Verification |
| --- | --- | --- |
| Batch 1 desk film needed original taps/slides; `motion_audio.py` analyzes sound but does not synthesize it | Added `helpers/tactile_audio.py` and its motion-design reference. Deterministic event input, exact stereo PCM length, bounds and overlap headroom checks; procedural sounds, not recorded Foley | Focused duration, boundary, determinism and clipping tests; later workshop/onboarding films used the helper |
| Batch 2 screen tutorial exposed AAC padding and extra video time at joins | Fixed `helpers/render.py` in `eb577c7`: copy video packets, join independently decoded audio on each measured video clock, and encode one continuous audio stream | Real 44.1/48 kHz pulses across two cuts, default extraction/B frames, source A/V offsets, silence and video-only cases; seven tests also passed in production FFmpeg 5.1.9 |
| The screen tutorial's crop adapter assumed 30 fps and landscape dimensions and monkeypatched rendering | Added bounded global `treatment.reframe.keyframes` to `helpers/visuals.py`, connected through the normal final compositor. Existing static reframing, still-image animation and planar tracking did not implement this edited-video output clock | Actual encoded crop positions and continuous clock across two joins, landscape/portrait, 24 and 30000/1001 fps, interpolation modes, zoom, frame counts and invalid input; combined 32 encoded/validation tests passed in production FFmpeg 5.1.9 |
| Batch 3 refill/onboarding/webhook films | Existing Three.js, Manim, browser rendering and tactile audio were sufficient. Their scene geometry, UI choreography and route drawing remain editable project code | Parent and independent visual/semantic review; no unsupported claim of automatic 3D collision proof or listening review |
| Batch 3 café film exposed a missing initial frame for silent 24/23.976-to-30 fps cuts starting between source frames | The shared extractor now fills that initial gap with the FPS filter's `start_time=0`, preserving video/audio timestamps instead of resetting one stream | Reproduced both silent failures before the fix; 36 timing/framing checks passed on production FFmpeg 5.1.9, including audio pulses and decoded flashes across three mixed-rate cuts |
| Café shots needed source-pixel crops and changing picture windows on one portrait matte | Added `helpers/shot_layout.py` and `ranges[].layout` to normal extraction. Explicit bounded crop/window rectangles, cover/contain, immutable preview scaling and consistent concat dimensions; matte color is applied after grading | Actual encoded source-quadrant colors, matte/letterbox positions, preview scaling, per-shot changes, audio presence and exact frame counts; invalid rectangles and mixed canvases rejected |
| Café's original 20-second rhythmic bed | Keep the authored synthesis source with this film. Its fixed score, palette and 30 fps adapter are composition choices, not a general-purpose music or rendering API | Preserve original music events/audio and licensed-source provenance when making the approved visual correction |
| Batch 4 MCP film proposed a DOM bounds/collision auditor | Keep project-local for now: it hardcodes viewport, margins, duration and pointer offsets, and its SVG endpoint comparison does not transform to viewport coordinates. Existing encoded-frame review remains required; general promotion would require those fixes and meaningful visibility/transform tests | Producer's project-specific dense DOM checks plus independent encoded transition review; no claim of a generic optical-layout guarantee |
| Batch 4 campaign film requested 4:5 but portrait defaults produced 9:16 | Runner now honors explicit `aspect`, derives a missing dimension, and rejects contradictory explicit dimensions. Repair retains the original prompt and reflows the scene into 1080×1350 | Normalization checks cover 4:5, 4:3, partial dimensions and contradictions; subsequent batch manifests are validated before launch |

Source-package review also found generated browser `.render` work directories,
Manim draft/final caches and QA directories among allowed image/JSON files.
The shared archiver now excludes those known generated paths while retaining
authored code, small reusable assets, explicit legal notices and replay metadata.
README instructions now require fresh-machine engine setup, scoped MIT grants
for original code, and actual bundled paths from the extracted project root.
The runner supplies its exact public producer manifest before authoring, retains
shell replay scripts, and excludes generated Manim text/TeX caches and research
pages. Additional regenerated assets can declare bounded project-relative
exclusions in `edit/source-exclusions.json`; required legal notices must remain.
