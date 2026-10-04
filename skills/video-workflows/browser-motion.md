# Motion design in the browser worker

Version-1 interaction takes priority: `start_video` returns the involvement question.
Follow `question.presentation` below; do not repeat it
through `show_video_brief`. Then ask only missing duration/destination
and wait for explicit answers. Hands off shows only
the final result, Key moments uses selective updates, and Hands on researches real
online references before creating, then reviews a short sample before the rest. Legacy
projects retain their saved mode or labeled default. Resolve real blockers in all modes.

Choose a subject-specific visual idea, hierarchy and signature transformation.
Reuse rendering mechanics, not the same layout or aesthetic for every request.
Diagrams, type, images, footage and 3D can mix when the idea needs them.
Follow the overview's sequential YouTube, TikTok and X research protocol.
Aim for four distinct, feasible references, maximum five; never pad a batch.
Inspect relevant media frames before recommending, save evidence and show each
`show_video_reference` thumbnail/link immediately. Metadata is a discovery lead;
stills prove neither motion nor sound. Stop at blocked playback and use
`research_budget`; explain fewer choices with `partial_reason`.
Ask once: references, **Find another batch**, **Give my input**. Preserve early
selection and preferences. Follow `question.presentation`: `inline_choices`
already saves clicks; otherwise use the native question tool if available or normal chat.

Plan the full arc and a representative snippet from the brief and chosen treatment.
Use `show_video_checkpoint` for Continue/Refine about its player. Wait for explicit acceptance, then create and review the full video.
Write a short plain chat transition before calling `show_video_preview` to open a
new final player; keep the snippet player unchanged. A sample is not completion.
After selection, call `prepare_video_reference` to download each chosen video.
Read `video_use_guidance(topic="reference-cloning")`; inspect the saved source,
measure its treatment and adapt it to the query before making the snippet.
Use the overview for the complete flow.

Build one meaningful short motion excerpt before authoring the entire film;
declare `production_stage="excerpt"` in its `run_video_step`. Hands off keeps it
internal. Key moments shows useful previews selectively. Hands on shows it with
`show_video_preview`, then asks the `show_video_checkpoint` question about that player via `question.presentation`; do not create a second card yourself. Wait for continue/refine
before remaining `production_stage="full_video"` work. Do not substitute an
arbitrary first frame for the sample. Precise edits need no creative questionnaire.

## Installed runtime and deterministic composition

Python/Pillow, Node, Chromium, FFmpeg and Puppeteer are installed. Use known fonts
DejaVu Sans/Serif or Noto Sans, or supplied brand assets. No setup, installs, font
inventory or remote CDNs. Work under `/workspace/edit/animations/` with local
images, fonts, scripts and models.

For HTML/Canvas/SVG/Three.js, expose `window.seek(seconds)`. Every state follows
from absolute time, independent of previous seeks. Await asset decoding and
fonts in optional `window.motionReady`. Use seeded values rather than per-frame
randomness. A renderer does not infer visual design from a text prompt.

Puppeteer dependencies are in `/opt/video-use/skills/motion-design/runtime`.
Three.js is bundled there in `node_modules/three`; copy needed bundles into the
served composition directory and use local imports. Use bounded procedural scenes;
prove uncertain geometry/material in the actual worker before promising a reference
treatment. Blender, GSAP and Remotion are not bundled. Use direct time functions,
not CDN imports or runtime installs.

```sh
node /opt/video-use/helpers/motion_render.mjs edit/animations/scene/index.html \
  -o edit/animations/scene/draft.mp4 --duration 5 \
  --width 960 --height 540 --fps 15 \
  --deps /opt/video-use/skills/motion-design/runtime
```

Use the actual excerpt duration and an integral frame count. Choose composition
coordinates that scale to the viewport; changing capture dimensions must not
distort the design. For later replacements add `--overwrite` intentionally.
For delivered quality use the requested dimensions, generally 1920x1080 at30fps.
The helper supports `--audio` for supplied/mixed audio and `--stills-only --stills`
for targeted inspection. Its seek-consistency checks catch stateful animations;
fix the state instead of silently disabling the checks.

## Production judgment

Keep text readable at chat-player size. Measure strings, allow safe margins and
use clear contrast. Let motion direct attention to one meaningful event. Choose
holds for comprehension, transitions for continuity, and rhythm for the actual
voiceover/music. Do not substitute generic entrances for a visual explanation.

Use narration's returned duration and sentence timing to align the film. Use
word timings for a label tied to a spoken word; do not infer that alignment from
a whole sentence's duration. Batch file writes/render/publication with
`run_video_step`, supplying the actual
`preview_path`. Render independent components with separate outputs and assemble
only after all succeed. Reuse picture for audio-only changes. Poll only active
tasks. Display useful drafts according to the mode; keep hands-off checks internal
and honor the hands-on sample decision before rendering the rest.

Use `review_path` for final encoded inspection, repair concrete visible defects,
export the exact reviewed MP4, then write a short plain chat transition and call
`show_video_preview` to open a new final player. Keep editable source,
assets, timings and render instructions. Successful encoding alone is not a
visual-quality judgment.
Only claim motion playback or listening when you actually had that evidence.
Still-frame checks, decoding, loudness and timestamp measurements have narrower
coverage. Fix accidental clipping or unreadable text as defects, not style notes.

For deeper needs request specific references under
`skills/motion-design/references/`: `art-direction.md`, `browser-rendering.md`,
`runtime.md`, `audio-motion.md`, `footage-tracking.md`, `critique.md`. Read only
what helps the piece rather than loading the entire local-machine workflow.
