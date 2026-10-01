# Manim in the browser worker

Use Manim when geometry, a mechanism, equations or data relationships carry the
explanation. It does not prescribe a dark palette, a scene count or a title-card
format. Choose the visual premise for the subject and the user's direction.

## Author less before the first useful preview

Outline the takeaway and narrative arc, then implement one meaningful excerpt
that reveals the central relationship. It can be an interior scene, not necessarily
the opening. Show it in chat while further scenes remain easy to change. Continue
without mandatory approval. Avoid writing a full multi-hundred-line film before
the user sees any motion. For simple edits, go straight to the requested result.

For a short idea made of simple 2D geometry and type, `render_video_scene` can
remove the renderer/assembly boilerplate; see the compact `scenes` guide. Use
Manim when semantic transformations, equations or geometry need its richer API.

Manim CE **0.19.2**, FFmpeg and the default LaTeX/MathTex dependencies are ready.
Do not run setup scripts or inventory fonts. `DejaVu Sans`, `DejaVu Serif` and
`Noto Sans` are known choices; use supplied brand fonts when available.

Keep related scenes modular with shared palette, text roles, geometry and timing.
Preserve important objects across beats; cut or transform them when it helps the
explanation. Save a concise visual plan alongside source. Use narration's returned
sentence timings; do not estimate a fresh timeline after speech is generated.

At 960x540 preview size, ordinary labels generally need about 18–22 visible pixels
(roughly Manim font_size 36–44 in its default frame). This is a readability starting
point, not a rigid type scale. Inspect actual text widths and density. If labels
compete, simplify or reveal them in sequence; do not make them tiny. Center a
dominant subject with adequate room for annotations. Avoid long empty openings.

Give each arrow and mark a consistent meaning across its label and narration.
Check the signs, relationships and movement rather than inferring correctness
from a plausible diagram. Fix acknowledged meaning errors before exporting.

## Render and assemble using returned paths

The helper writes one JSON result to stdout, with ordered `videos`, `rendered`
and `reused` fields. Manim's own logs go to stderr.

```sh
python /opt/video-use/helpers/render_manim_cached.py \
  edit/animations/mechanism.py Mechanism --quality preview > edit/mechanism.json
```

For an early excerpt render only that scene. For independent scenes use
`run_video_step.components` (maximum two concurrent renders), distinct manifest
paths, and a final assembly command. Name explicit `--dependency` files when local
images/data affect the render. Do not disable caching. A visual correction should
render only affected scenes; audio-only corrections should reuse scene MP4s.

Read ordered `videos` from those manifests; never `find` or `ls -t` to select an
MP4. For example, a Python assembly script can load the manifests in story order,
write an FFmpeg concat list and call FFmpeg with `check=True`. Concatenate only
matching resolution/fps/codec clips, then mix the recorded audio once. Preserve
the requested duration and ensure the final words fit. Audio offsets are explicit;
do not accumulate scene timing drift by guessing every chapter's frame count.

Save actual ordered scene durations in the assembled step's `production_timing`;
rough story estimates are not evidence of narration alignment.

Use `--quality final` only after the draft communicates clearly. Inspect the
encoded MP4 through `review_path`, fix observed issues, export, and call
`show_video_preview`. Intermediate review sheets are for inspection; the user
should see a playable draft rather than a grid of tiny QA frames.

## Detailed components when needed

- `skills/manim-video/assets/teaching.py`: semantic continuity and visual theme.
- `skills/manim-video/assets/concept_explainer.py`: narration and frame safety.
- `skills/manim-video/references/concept-explainer.md`: extended teaching contract.
- `skills/manim-video/references/mobjects.md`: geometry and layout reference.
- `skills/manim-video/references/equations.md`: equation animation.

These are optional supporting references for the actual problem, not a list to
read before every render. Keep production correctness and factual provenance;
local setup and generic approval checkpoints do not apply to this hosted workflow.
