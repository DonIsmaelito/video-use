# Manim in the browser worker

Version-1 interaction takes priority: ask `start_video`'s involvement question with
the native question tool if available, otherwise normal chat. Do not repeat it
through `show_video_brief`. Ask only missing duration/destination and wait for answers.
Hands off shows only the final video; Key moments uses selective updates;
Hands on researches online references, then reviews a short sample before the rest.
Legacy projects retain their saved mode or labeled default. Resolve real blockers;
ordinary rendering needs no extra approval.

Use Manim for geometry, mechanisms, equations and data relationships. Palette,
scene count and visual premise follow the subject and user's direction.
Follow the overview's sequential reference search on YouTube, TikTok and X.
Inspect and show each candidate immediately with `show_video_reference`, saving
its evidence and observed attribution through `record_video_references`.
Usually three useful choices, maximum five. Finish with one native choice:
references, **Find another batch**, **Give my input**. Keep feedback across batches.
Show source thumbnails and links; do not invent popularity, motion inspection or
source playback. Stop research when the user selects a direction.
Plan the full arc and a representative snippet from the brief and chosen treatment.
Use `show_video_checkpoint` for native Continue/Refine about its player. Wait for explicit acceptance, then create and review the full video.
Write a short plain chat transition before calling `show_video_preview` to open a
new final player; keep the snippet player unchanged. A sample is not completion.
After selection, call `prepare_video_reference` to download each chosen video.
Read `video_use_guidance(topic="reference-cloning")`; inspect the saved source,
measure its treatment and adapt it to the query before making the snippet.
Use the overview for the complete flow.

## Author less before the first useful preview

Outline the takeaway and narrative arc, then implement one meaningful excerpt
that reveals the central relationship. It can be an interior scene, not necessarily
the opening. Hands off keeps this check internal. Key moments shows useful samples
selectively. Hands on uses `show_video_preview`, then asks the `show_video_checkpoint`
question in native questions or normal chat about that player, without a second
card. Wait for explicit continue/refine before making the rest. Avoid writing the full
film before that review. Simple edits need no creative questionnaire after setup.

For a short idea made of simple 2D geometry and type, `render_video_scene` can
remove the renderer/assembly boilerplate; see the compact `scenes` guide. Use
Manim when semantic transformations, equations or geometry need its richer API.

Manim CE **0.19.x**, FFmpeg and the default LaTeX/MathTex dependencies are ready.
Do not run setup scripts or inventory fonts. `DejaVu Sans`, `DejaVu Serif` and
`Noto Sans` are known choices; use supplied brand fonts when available.

Keep related scenes modular with shared palette, text roles, geometry and timing.
Preserve important objects across beats; cut or transform them when it helps the
explanation. Save a concise visual plan alongside source. Use narration's returned
sentence timings; do not estimate a fresh timeline after speech is generated.
Use returned word timings when labels or emphasis must meet particular spoken
words. Read the current choice and feedback in each task result before rendering
the next scene; after a long authoring gap, refresh project context once.

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

For an early excerpt render only that scene and set
`run_video_step(production_stage="excerpt")`. Remaining scenes use the default
`production_stage="full_video"` after required hands-on acceptance. For independent scenes use
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
encoded MP4 through `review_path`, fix observed issues, export, and deliver the
full video as above. Intermediate review sheets are for inspection; the user
should see actual media according to their mode, never a grid of tiny QA frames.
In interactive modes accompany a substantial draft with a brief sentence about what the user can judge
and what comes next. Sampled frames and measured audio do not establish motion
playback, listening or word-level sync; describe the evidence you actually used.

## Detailed components when needed

- `skills/manim-video/assets/teaching.py`: semantic continuity and visual theme.
- `skills/manim-video/assets/concept_explainer.py`: narration and frame safety.
- `skills/manim-video/references/concept-explainer.md`: extended teaching contract.
- `skills/manim-video/references/mobjects.md`: geometry and layout reference.
- `skills/manim-video/references/equations.md`: equation animation.

These are optional supporting references for the actual problem, not a list to
read before every render. Keep production correctness and factual provenance;
local setup and generic approval checkpoints do not apply to this hosted workflow.
