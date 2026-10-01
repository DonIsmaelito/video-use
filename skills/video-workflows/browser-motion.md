# Motion design in the browser worker

Version-1 interaction takes priority: `start_video` returns the involvement question.
Use the native question tool if available, otherwise normal chat; do not repeat it
through `show_video_brief` or open a form. Then ask only missing duration/destination
and wait for explicit answers. Hands off shows only
the final result, Key moments uses selective updates, and Hands on settles useful
content/style decisions and reviews a short sample before the rest. Legacy
projects retain their saved mode or labeled default. Resolve real blockers in all modes.

Choose a subject-specific visual idea, hierarchy and signature transformation.
Reuse rendering mechanics, not the same layout or aesthetic for every request.
Diagrams, type, images, footage and 3D can mix when the idea needs them.
In interactive modes, state consequential assumptions briefly before substantial
work. A hands-on reference choice waits for an answer before dependent rendering;
compatible inexpensive preparation may continue. Current choices steer later work.

Build one meaningful short motion excerpt before authoring the entire film;
declare `production_stage="excerpt"` in its `run_video_step`. Hands off keeps it
internal. Key moments shows useful previews selectively. Hands on shows it with
`show_video_preview`, then asks the `show_video_checkpoint` question in native
questions or normal chat about that player, without a second card. Wait for continue/refine
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
served composition directory and use local imports. CPU/software WebGL is
available for bounded scenes, not a photoreal rendering farm.

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
export the exact reviewed MP4, then display its player. Keep editable source,
assets, timings and render instructions. Successful encoding alone is not a
visual-quality judgment.
Only claim motion playback or listening when you actually had that evidence.
Still-frame checks, decoding, loudness and timestamp measurements have narrower
coverage. Fix accidental clipping or unreadable text as defects, not style notes.

For deeper needs request specific references under
`skills/motion-design/references/`: `art-direction.md`, `browser-rendering.md`,
`runtime.md`, `audio-motion.md`, `footage-tracking.md`, `critique.md`. Read only
what helps the piece rather than loading the entire local-machine workflow.
