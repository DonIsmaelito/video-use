# Short editable motion scenes

`render_video_scene` handles drawing, deterministic animation, encoding and draft
publication from compact data. Use it for a useful 2D visual idea: a relationship,
transformation, diagram, chart or typographic moment. You supply the design. This
is not a text-to-video model or a replacement for custom Manim, footage or 3D.

Version-1 interaction takes priority: `start_video` returns the involvement question.
Use the native question tool if available, otherwise normal chat; do not repeat it
through `show_video_brief` or open a form. Then ask only missing duration/destination
and wait for explicit answers. Hands off shows
only the final video, Key moments uses selective updates, and Hands on researches
real online references before creation and short sample review. Legacy projects keep
their saved mode or labeled default. Real blockers still need resolution.

The registry supplies search locations/access notes, not fixed media suggestions.
Search and inspect fresh query-specific references with host tools. For Hands on,
derive a visual search intent and adaptively choose relevant curated
collections, not the first two sources. Scan candidates cheaply, inspect promising
finalists (2–3), batch independent queries when supported, and stop once useful
choices exist. Compare brief fit, design, evidence and feasible adaptation to offer
2–3 distinct approaches. Save intent, queries and evaluation reasons. Separate
factual research. Source research verified no playback: page claims are attributed;
actually viewed images support palette/layout, not motion or sound. State evidence
limits and source URLs in native chat/links/images, not forms. Refine only relevant
attributes, retain likes/dislikes and ask only what is unclear. Use approved traits
in the sample. A supplied reference, exact edit or explicit skip can delegate search
with saved user words. Missing search or suitable curated coverage needs a reference
or delegation, not arbitrary web discovery or cached substitutes. Choosing a
reference does not import media. The overview details this loop.

Pass `project_id`, a new `request_id`, stable `scene_id`, `note`, the current
`creative_revision`, and `scene`. For the first sample, explicitly pass
`production_stage="excerpt"`; the default `full_video` is remaining production,
which hands-on mode waits to start until sample acceptance. The same scene ID with changed data and a new
request ID updates the saved composition. It returns an editable JSON path and
MP4 path. In interactive modes use `preview_delivery.open_if_missing` when a real
player is needed. Hands on asks the `show_video_checkpoint` question through native
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
actual `production_timing` is recorded, and the assembled draft reaches the player.

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
