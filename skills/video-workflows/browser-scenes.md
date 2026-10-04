# Short editable motion scenes

`render_video_scene` handles drawing, deterministic animation, encoding and draft
publication from compact data. Use it for a useful 2D visual idea: a relationship,
transformation, diagram, chart or typographic moment. You supply the design. This
is not a text-to-video model or a replacement for custom Manim, footage or 3D.

Version-1 interaction takes priority: `start_video` returns the involvement question.
Follow `question.presentation` below; do not repeat it
through `show_video_brief`. Then ask only missing duration/destination
and wait for explicit answers. Hands off shows
only the final video, Key moments uses selective updates, and Hands on researches
real online references before creation and short sample review. Legacy projects keep
their saved mode or labeled default. Real blockers still need resolution.

Aim for four distinct, feasible short references from YouTube, TikTok and X,
shown consecutively; maximum five, no filler. Search quickly; use `inspect_social_reference` for attribution. Save its receipt
with `record_video_references offer(more_expected=true)`, then append to that round.
Show each `new_link_cards` with `show_video_reference` immediately: thumbnail,
original link, brief fit explanation and sourced engagement only.
Inspect a thumbnail/still; metadata is provisional. Neither proves motion or sound. One brief browser attempt per candidate: stop at
blocked playback or login; no repeated scrolling, studio detours or frame sampling.
Use `research_budget`; finish at four, or give a concrete `partial_reason` for fewer.
Ask ONE reference question with every choice, **Find another batch**, and
**Give my input** using native questions or normal chat. Respect an early selection.
New batches exclude prior works. Save evidence, close the browser; inspect the
chosen treatment before creation.
For involvement, basics, approach and sample review, follow `question.presentation`:
`inline_choices` displays and saves clicks; never repeat it. Otherwise use the
native question tool if available or normal chat. Use supplied reference choices.

Plan the full arc and a representative snippet from the brief and chosen treatment.
Use `show_video_checkpoint` for Continue/Refine about its player. Wait for explicit acceptance, then create and review the full video.
Write a short plain chat transition before calling `show_video_preview` to open a
new final player; keep the snippet player unchanged. A sample is not completion.
After selection, call `prepare_video_reference` to download each chosen video.
Read `video_use_guidance(topic="reference-cloning")`; inspect the saved source,
measure its treatment and adapt it to the query before making the snippet.
Use the overview for the complete flow.

Pass `project_id`, a new `request_id`, stable `scene_id`, `note`, the current
`creative_revision`, and `scene`. For the first sample, explicitly pass
`production_stage="excerpt"`; the default `full_video` is remaining production,
which hands-on mode waits to start until sample acceptance. The same scene ID with changed data and a new
request ID updates the saved composition. It returns an editable JSON path and
MP4 path. In interactive modes use `preview_delivery.open` to show that exact clip
once. Hands on asks the `show_video_checkpoint` question through native
questions or normal chat about that player; no second card. Wait for explicit
continue/refine before the rest; Key moments continues with selective updates.
Hands off keeps samples internal. Read current choices/feedback before later
renders. Tool defaults are preview settings, not user requirements.

## Drawing data

- Scene: `duration` (0.1–20 seconds), `width`, `height` (even,180–1920), `fps`
  (1–30), `background` (hex), `marks` (1–100). Defaults:960×540,15fps. Duration
  rounds up to whole frames and the result reports the exact value. Use the
  requested frame grid for final scenes; do not round each section independently
  and assume their sum still matches a requested total.
- Mark: unique `id`, `kind`, `x`, `y`. Kinds: `text`, `rect`, `ellipse`, `line`,
  `polygon`, `arc`, `wave`. Geometry is local to the mark's origin; rectangles,
  ellipses and text use top-left origin plus `w`,`h`. Marks paint in list order.
- Appearance: `color` (text/stroke hex), `fill` (shape hex or `transparent`),
  `stroke_width`, `radius` (rect corners), `opacity` (0–1), `rotation` (degrees),
  `scale`. Rotation and scale use the local origin, not the object's center.
- Text: `text`, `size`, `font` (`sans`, `bold`, `serif`), `align`
  (`left`,`center`,`right`). Text fits inside `w`,`h`; explicit `\n` makes lines.
  Choose generous bounds and readable type, not a long paragraph shrunk to fit.
- Line/polygon: `points:[[x,y],...]`, local coordinates. An omitted line points
  list uses `[0,0]` to `[w,h]`. Animate position/rotation/scale of this geometry.
  Arc uses `start`,`end` degrees; wave uses `cycles`,`phase` degrees across `w`
  with amplitude `h/2` around its origin.
- Optional `parent` names another mark whose transform/opacity also applies.
  Use local coordinates for children; no cycles. The parent itself also draws.

## Motion

Each mark may have `keyframes:[{time,...numeric properties,ease}]`. Values are
absolute; omitted properties retain their previous value. Times strictly
increase within the scene. A key's easing controls its outgoing interval:
`linear`, `smooth`, `inCubic`, `outCubic`, `inOutCubic`, `outBack`. The base pose
is time0 unless explicitly replaced. Colors/text/points are fixed per mark;
crossfade separate marks to change them. Numeric `phase` is supported for wave
animation, in degrees; a changing phase moves the wave while fixed phase is static.
All motion is deterministic from time.

For example, a marker can arrive, hold, then move as another element responds:

```json
{"id":"marker","kind":"ellipse","x":100,"y":250,"w":24,"h":24,
 "fill":"#356CE8","stroke_width":0,
 "keyframes":[{"time":0,"ease":"outCubic"},{"time":1,"x":350},
              {"time":2,"x":350},{"time":3,"x":620}]}
```

Optional `narration_path` selects existing project audio; `narration_start` is
the explicit source-audio offset for this excerpt. No audio or words are invented.
Use `word_timings` for labels meant to meet particular spoken words.

For a moving marker or repeated flow, add `motion_path` rather than calculating
corner keyframes for every copy:

```json
{"id":"flow","kind":"ellipse","x":220,"y":160,"w":12,"h":12,
 "fill":"#356CE8","stroke_width":0,
 "motion_path":{"points":[[0,0],[340,0],[340,170],[0,170]],
                "seconds":3,"closed":true,"loop":true,"count":8}}
```

Path points are offsets from the mark's animated x/y. `seconds` is a constant-speed
traversal of the entire polyline. `closed` connects the endpoint to the start;
an open looping path deliberately jumps back. Optional `start` defaults to zero.
For loops, copies appear together at start, spaced backward by `stagger` seconds
(default `seconds/count`). Without looping, each copy appears at its staggered
start, traverses once and holds the endpoint. `orient` adds segment direction to
rotation. At most 32 copies per mark and 400 total; children cannot attach to a
repeated parent. Use this only where the repeated motion has a clear meaning.

`render_video_scene(validate_only=true)` reports all validation errors without
rendering. The helper's `--validate` does the same for local scene JSON, with scene,
mark, keyframe and invalid value where applicable. Useful before a complex custom
batch; ordinary rendering/assembly also validates before expensive work. Do not
add a validation tool call to every trivial edit. Successful validation establishes
schema correctness, not design or animation quality.

## Assemble without a generator script

After the first excerpt and any required hands-on acceptance, use `assemble_video` with `project_id`, a new `request_id`,
current `creative_revision`, and ordered `scene_ids`. To author remaining scenes
in that call, pass `scenes={scene_id:scene_data,...}`; omitted IDs reuse saved JSON
under `edit/scenes/`. No separate scene registry or handwritten concat is required.
The whole batch is validated before rendering. Compatible renders are reused,
actual `production_timing` is recorded, and the assembled draft is available for review.

Add `narration_path` and `narration_offset` for the continuous mix. Quality `draft`
defaults to 960×540 at 15 fps for a landscape 16:9 composition; `final` defaults to
1920×1080 at 30 fps, preserving the authored aspect ratio. Optional `width`, `height`
and `fps` override delivery; dimensions must preserve the composition's aspect.
Coordinate geometry is scaled consistently, so do not rewrite every mark to
increase resolution. Choose final quality after the draft communicates clearly.

Assembly accepts up to 12 scenes and 180 seconds total. It handles narration mixing
and optional `audio_normalization="web"` (default) or `"none"`. Use the latter when
preserving an intentional mix is important. Check measured audio after assembly;
normalization is not listening, source verification or proof of narrative sync.
A sample assembled from multiple clips explicitly uses `production_stage="excerpt"`;
the default `full_video` remains gated by hands-on sample acceptance. Routine
technical fixes need no additional approval.

## Custom reuse

The helper remains available in `run_video_step` for custom pipelines:

```sh
python /opt/video-use/helpers/render_scene.py edit/scenes/idea.json \
  -o edit/scenes/idea.mp4 --overwrite
```

Keep composition coordinates and final raster dimensions consistent. Reuse the
generated clip or JSON in the full film; match codecs, dimensions and fps before
concatenating. Use `production_timing` for the assembled video's actual durations.
Inspect encoded motion and labels; a valid composition is not a quality verdict.
