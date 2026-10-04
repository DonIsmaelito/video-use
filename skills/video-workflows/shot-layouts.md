# Per-shot crops and picture windows

Use a range's `layout` when shots need different source crops or picture windows
on one delivery canvas. This supports a useful stock edit such as a full-frame
opening, a wider detail shot inside a portrait matte, and a full-frame ending.
It is separate from global `treatment.canvas`, which applies one layout after
joining all shots, and from the output-clock camera path in
[continuous-reframing.md](continuous-reframing.md).

```json
{
  "source": "coffee-machine",
  "start": 1.3,
  "end": 2.7,
  "layout": {
    "width": 1080,
    "height": 1920,
    "background": "#18130f",
    "crop": {"x": 240, "y": 0, "width": 1440, "height": 1080},
    "window": {"x": 60, "y": 520, "width": 960, "height": 720, "fit": "contain"}
  }
}
```

All coordinates are explicit even pixel integers, including zero origins. The
crop uses the original decoded source's coordinates and must fit inside it;
omit it to use the whole source. The window uses output-canvas coordinates and
must fit inside the canvas; omit it to fill that canvas. `cover` fills the window
with a centered crop; `contain` keeps the entire selected source region with
matte bars. Choose a source crop to direct attention before using either fit.
Only `#RRGGBB` matte colors are accepted. Canvas sides are bounded to 2–7680px.
This is intended for square-pixel, normally oriented footage; normalize unusual
sample-aspect ratios or rotation metadata before choosing source pixel crops.

When any EDL range uses `layout`, every range must supply it with the same canvas
width and height. Crop, window, background and fit may differ between ranges.
The renderer rejects missing or inconsistent canvases before extraction.
Use the normal `helpers/render.py` entrypoint; no monkeypatch or second renderer
is required. Direct callers can pass the same object to `extract_segment` as
`layout=...` or use `helpers/shot_layout.py`'s filter builder.

The pipeline applies source cropping, optional same-aspect reframing and color
grading before picture-window placement. Matte colors therefore do not inherit
the source's grade. Preview and draft rendering scale the canvas and window to
at most 1280px on the longest side without changing source crop coordinates or
mutating the EDL. Global treatment, graphics and captions still run after video
concatenation. The existing extractor owns the common frame rate and source
audio timing; the layout filters never reset timestamps.

Inspect each selected source range and actual encoded frames around every join.
A technically valid rectangle can still crop out an important action or leave
text unreadable. The café example's typography and original score remain its
editable composition, not hidden behavior of this primitive.
