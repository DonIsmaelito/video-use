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
| Batch 3 café film proposed a per-shot canvas adapter and a fixed original music composition | Under review for the following snapshot. Preserve the exact project implementation and licensed-source acquisition records. Do not promote the fixed café palette, 20-second score, or 30 fps adapter as a general tool | Shared mixed-rate extraction is being checked with actual encoded fixtures; original source/EDL and signal metrics accompany the example |

Source-package review also found generated browser `.render` work directories,
Manim draft/final caches and QA directories among allowed image/JSON files.
The shared archiver now excludes those known generated paths while retaining
authored code, small reusable assets, explicit legal notices and replay metadata.
README instructions now require fresh-machine engine setup and actual bundled
paths instead of assuming the original `/opt/video-use` container.
