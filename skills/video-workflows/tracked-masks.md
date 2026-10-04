# Explicit moving privacy masks

Use `helpers/tracked_mask.py` when the sensitive rectangles and their motion are known, such as an authored screen recording. It applies solid rectangular fills on the original source clock after cuts have been made. It does not discover private text, recognize faces, infer tracking, or certify that every sensitive region was supplied.

Prepare a silent edited input with final geometry, square pixels, one video stream, time zero, and a fixed integer frame rate. The helper checks every frame timestamp as well as the input SHA-256; it does not resize, reframe, retime, rotate or silently remove sound. Its bounded scope is SDR, 64–4096 even dimensions, at most 8,388,608 pixels and 300 seconds. Preserve and handle any intended soundtrack separately with a deliberate verified remux.

Write this JSON next to the edited input, replacing the SHA with its actual digest:

```json
{
  "version": 1,
  "source": "edited-silent.mp4",
  "source_sha256": "REPLACE_WITH_ACTUAL_LOWERCASE_SHA256",
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "audio": "none",
  "color": [25, 30, 29],
  "ranges": [[0, 5], [8, 13]],
  "tracks": [{
    "name": "Known email field",
    "intervals": [[0, 5], [8, 13]],
    "keyframes": [[0, 220, 300, 420, 48], [13, 220, 170, 420, 48]],
    "clip": [160, 150, 1500, 760]
  }]
}
```

`ranges` lists the original source intervals in edited playback order. Their lengths must span whole output frames and sum to the edited input frame count. Forward and backward cuts work; each output frame is mapped to `range start + local frame index / fps`. No speed changes or transitions are implied. If the picture was already cropped or resized, author the rectangle coordinates in its final input pixel space.

Each track has half-open active intervals `[start, end)` on that original source clock. Keys are `[seconds, x, y, width, height]`, linearly interpolated, and must cover every active interval. Add sufficient keys to follow nonlinear motion. The optional `clip` is a fixed visible viewport in input pixels; omission uses the whole image. Rectangle edges round outward; viewport edges round inward. Fills are fully opaque with square corners, without blur or feathering. Include a practical pixel margin around private glyphs and review compression at the encoded boundaries.

```sh
python "$VIDEO_USE/helpers/tracked_mask.py" edit/masks.json -o edit/masked.mp4
```

The default refuses an existing target. `--overwrite` atomically replaces only a completed output; source/config paths and their hard links are protected. Both FFmpeg children are reaped and partial output is removed on failure. The JSON result records source/output hashes, dimensions, frame count and silent-audio contract.

Before delivery, inspect **every encoded frame** where private information can appear, particularly source cuts, track starts/ends, viewport edges, scrolling reversals and one-frame transitions. Compare against the preserved private source locally or in the authorized production environment. Check final pixels rather than trusting only geometry or a contact sheet. Keep raw private captures and sensitive text out of public source packages; use a fictional fixture for a public demonstration. A passing coverage check demonstrates the supplied rectangles only.
