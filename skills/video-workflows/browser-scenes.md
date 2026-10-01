# Short editable motion scenes

`render_video_scene` handles drawing, deterministic animation, encoding and draft
publication from compact data. Use it for a useful 2D visual idea: a relationship,
transformation, diagram, chart or typographic moment. You supply the design. This
is not a text-to-video model or a replacement for custom Manim, footage or 3D.

Pass `project_id`, a new `request_id`, stable `scene_id`, `note`, the current
`creative_revision`, and `scene`. The same scene ID with changed data and a new
request ID updates the saved composition. It returns an editable JSON path and
MP4 path. Execute `display_action` when the first real player is needed, then
keep working; there is no required approval pause.

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
crossfade separate marks to change them. All motion is deterministic from time.

For example, a marker can arrive, hold, then move as another element responds:

```json
{"id":"marker","kind":"ellipse","x":100,"y":250,"w":24,"h":24,
 "fill":"#356CE8","stroke_width":0,
 "keyframes":[{"time":0,"ease":"outCubic"},{"time":1,"x":350},
              {"time":2,"x":350},{"time":3,"x":620}]}
```

Optional `narration_path` selects existing project audio; `narration_start` is
the explicit source-audio offset for this excerpt. No audio or words are invented.

## Reuse

The helper is also available in `run_video_step` for batching/assembling scenes:

```sh
python /opt/video-use/helpers/render_scene.py edit/scenes/idea.json \
  -o edit/scenes/idea.mp4 --overwrite
```

Keep composition coordinates and final raster dimensions consistent. Reuse the
generated clip or JSON in the full film; match codecs, dimensions and fps before
concatenating. Use `production_timing` for the assembled video's actual durations.
Inspect encoded motion and labels; a valid composition is not a quality verdict.
