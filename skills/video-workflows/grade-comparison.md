# Synchronized color comparisons

Use `helpers/grade_comparison.py` for a silent original/corrected wipe over one
local SDR clip. It decodes each frame once, keeps the original pixels on the left
and grades the same coordinates on the right. Both halves share the crop, output
clock and playback speed. No model, service or new dependency is required.

```json
{
  "version": 1,
  "source": "sources/river.mp4",
  "source_start": 0,
  "duration": 20,
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "audio": "none",
  "rgb_coefficients": [0.020, 0.012, 0.002],
  "wipe": [[0, 1], [3, 1], [7, 0.5], [14, 0.5], [17, 0], [20, 0]],
  "labels": {
    "original": "Original",
    "corrected": "Warm neutral",
    "font": "assets/inter-regular.ttf",
    "font_size": 30,
    "margin": 64,
    "top": 64
  }
}
```

All paths resolve from the JSON file. Optionally supply `source_sha256` to reject
changed input bytes. The helper reports the measured source hash either way.
`audio: "none"` is required: this explicitly creates a silent visual review even
if the input has sound. For a sound-bearing deliverable, decide its treatment and
mux the verified original range separately with the existing audio workflow.

```sh
python /path/to/video-use/helpers/grade_comparison.py edit/comparison.json -o edit/draft.mp4 --width 960
python /path/to/video-use/helpers/grade_comparison.py edit/comparison.json -o edit/comparison.mp4
```

The source is untouched; existing outputs require `--overwrite`. The helper
validates the range, dimensions, labels and input hash before rendering. A failed
render terminates its FFmpeg processes and removes its partial temporary output.
Only a complete encoded file replaces the destination.

Wipe keys are `[output_seconds, original_fraction]`, with strictly increasing
times covering zero through the exact duration. Fractions range from zero (fully
corrected) to one (fully original), joined with cubic smoothstep. Labels are
optional; supplied labels fade out before their side becomes too narrow. A thin
divider appears between the regions. They do not imply a color measurement.

Each RGB coefficient defines `y = x + c * 4 * x * (1-x)` in normalized nonlinear
RGB, rounded to eight bits. Coefficients are bounded to ±0.24 to preserve order and
black/white endpoints. This is a modest review treatment, not a camera transform,
3D LUT, HDR grade, automatic correction or guarantee against clipping already in
the source. H.264/chroma subsampling can slightly change exported pixels.

Use a square-pixel, unrotated SDR source and matching aspect ratio. Convert HDR,
anamorphic or orientation metadata explicitly before comparison. Duration must
span whole output frames, up to 300 seconds; the integer frame rate is 1–60. Even
dimensions are 64–4096, up to 8,388,608 pixels. Draft width can only reduce the
configured width. Reframing/stretching and sound editing belong in separate steps.

Inspect the encoded original, split and corrected holds, plus frames around each
wipe transition. Check source correspondence, labels, detail in highlights and
shadows, and whether the correction actually serves the brief. A successful
render or numeric check does not replace visual review.
