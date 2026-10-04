# Continuous framing across an edit

Use `treatment.reframe.keyframes` for a deliberate zoom or pan that follows the
finished output clock. `helpers/render.py` applies it once after joining the
source cuts, before canvas treatment, graphics and captions. It does not restart
at a cut, and it uses the actual assembled video dimensions and rational frame
rate. It does not track a subject automatically.

```json
{
  "treatment": {
    "reframe": {
      "interpolation": "smooth",
      "keyframes": [
        {"time": 0, "zoom": 1, "focus_x": 0.65, "focus_y": 0.35},
        {"time": 1.5, "zoom": 1.35},
        {"time": 8, "zoom": 1.35},
        {"time": 9.5, "zoom": 1}
      ]
    }
  }
}
```

Times are seconds from the beginning of the completed edit. Supply 1–24 keys
with strictly increasing, finite, nonnegative times. Omitted zoom/focus fields
inherit the previous key (initial defaults: zoom 1, focus 0.5/0.5). Zoom is 1–3;
normalized focus is 0–1. Focus selects the available crop position: 0 is the
left/top edge, 0.5 is centered, and 1 is the right/bottom edge. At zoom 1 there
is no space to pan. The first/last state holds outside the keyed interval.

Interpolation may be `smooth` (cubic smoothstep, the default), `linear`, or `hold`.
This is bounded numerical input, not an arbitrary FFmpeg expression. Static
per-range `reframe` remains available for independent shot framing; animated
keys belong under the global `treatment.reframe`, where the output clock and
dimensions are known. A change between shots can still be abrupt because the
source image changes; continuous coordinates do not imply subject continuity.

No extra dependency or monkeypatch is required. The existing FFmpeg final
composite performs the motion at the video's actual frame rate, including
fractional rates, and preserves the audio stream. It keeps the input canvas
size; use the separate `treatment.canvas` to choose a delivery aspect ratio.
For a large zoom, inspect full-size encoded frames for softness, pixel stepping,
cropped controls, safe areas, and reading time. Inspect moving frames and both
sides of every cut; a successful render is not a quality review.
