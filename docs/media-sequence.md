# Still sequences and audio-first videos

`helpers/media_sequence.py` composes local images and timed audio into an H.264
MP4. It is a timing and rendering primitive: the agent chooses the material,
story, typography, music, composition, and whether movement helps. It does not
choose a genre, impose a template, generate narration, retrieve remote files,
or rasterize source documents.

Use it for photos, rasterized slides, authored infographics, product images,
podcast cover art, or any other supplied still imagery. Rasterize document pages
or slides first and preserve their source relationship. Use `render.py` for
footage edits, graphics and captions; use the browser/Manim renderers for
original scenes. Existing `motion_audio.py` extracts audio features for custom
audio-reactive animation beyond a simple waveform.

```sh
python /opt/video-use/helpers/media_sequence.py edit/sequence.json -o edit/draft.mp4
```

Paths in the JSON resolve relative to the JSON's directory. The output argument
resolves relative to the command's working directory. The only dependencies are
Pillow, FFmpeg and FFprobe, all already present in the browser worker. No model,
network access or paid provider is called.

## Sequence example

These values illustrate the contract, not a recommended visual style. Supply
real narration duration before deciding the timeline. Each boundary rounds
upward to the next frame; cumulative rounding avoids timing drift. The JSON
report includes the actual frame-aligned timeline.

```json
{
  "version": 1,
  "mode": "sequence",
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "background": "#EAE7DE",
  "items": [
    {"file": "slides/introduction.png", "duration": 4.2, "fit": "contain"},
    {"file": "photos/product.png", "duration": 5.8, "fit": "cover",
     "motion": {"zoom_start": 1, "zoom_end": 1.12,
                "focus_start": [0.5, 0.5], "focus_end": [0.6, 0.5],
                "easing": "smooth"}}
  ],
  "audio": [
    {"file": "narration.wav", "start": 0, "gain": 1},
    {"file": "music.wav", "duration": 10, "gain": 0.12, "loop": true}
  ]
}
```

`contain` preserves the whole image and fills unused canvas with `background`.
`cover` crops to fill the canvas. EXIF orientation and image transparency are
honored. Movement applies to the fitted canvas: `zoom_start`/`zoom_end` are
between 1 and 3; focus coordinates are normalized 0–1 crop positions. At zoom 1
the entire fitted canvas is visible, so moving focus alone has no visible
effect. Omit `motion` for a static hold. Supported interpolation is `linear` or
`smooth`; custom choreography belongs in an authored animation renderer.

Every `audio` item supports a timeline `start`, source trim `source_start`,
playback `duration`, linear `gain` between 0 and 4, and explicit `loop` boolean.
Without a duration, a non-looped track uses all remaining source audio. Looped
tracks require a duration. Use a pretrimmed music file when its loop must repeat
a particular region. Each track receives a 30 ms boundary fade, configurable
through `fade` in seconds (zero disables it). Tracks mix at supplied gains with
a final limiter; there is no automatic ducking or creative volume balancing.

Audio longer than the image timeline causes a clear error instead of silently
losing speech. Extend the last image, change the edit, or supply an explicit
audio duration. Video items concatenate without re-encoding. A plain soundtrack
is muxed onto that video without another video encode.

## Audio-first example

```json
{
  "version": 1,
  "mode": "audio",
  "width": 1080,
  "height": 1080,
  "fps": 24,
  "background": "#171222",
  "cover": {"file": "episode-artwork.png", "fit": "contain"},
  "audio": [{"file": "episode.wav"}],
  "waveform": {"x": 90, "y": 850, "width": 900, "height": 120,
               "color": "#DCCBFF", "track": 0}
}
```

Audio mode derives duration from the latest audio endpoint. An explicit
top-level `duration` can extend it but cannot silently shorten supplied tracks.
Omit `cover` for a solid background, and omit `waveform` for a plain cover video.
The waveform uses actual samples from the selected zero-indexed audio track,
including its trim, delay and gain. Coordinates and size are output pixels.
Waveform compositing requires an additional video encode. Captions are still
applied afterwards through the existing captions-last renderer.

## Limits and verification

- Canvas dimensions must be even, between 16 and 3840 pixels per side, and no
  greater than 3840×2160 in pixel area. Rational frame rates such as
  `"30000/1001"` are accepted, between 1 and 60 fps.
- At most 120 images, eight audio tracks, 3600 seconds, or 108000 output frames
  per job. Split longer projects into sections. The default whole-job timeout
  is 1800 seconds; `--timeout` accepts 1–3600 seconds. Worker quotas still apply.
- Local source files are at most 512 MiB; still images are at most 40 megapixels.
  Animated image files must be deliberately converted to a selected frame or
  actual video before use. Composition JSON is at most 1 MiB through the CLI.
- FFmpeg uses two encoder threads and one filter thread. Files are composed in
  an isolated temporary directory. Failed renders preserve previous output and
  source files; successful output replaces its target atomically.
- A successful command emits one JSON report to stdout with actual dimensions,
  frame count, duration, timeline, codec, track count and elapsed time. Errors
  emit JSON to stderr and a nonzero exit status. Output is H.264, yuv420p,
  faststart MP4; audio is 48 kHz AAC. Every success includes a full video/audio
  decode check. This establishes media integrity, not creative quality.

Inspect representative frames, boundaries and the full video at playback speed.
Use the browser MCP `review_path` and export verification after any final caption
or graphic pass. Retain the composition JSON and referenced source assets as
the editable project. Variants are separate authored JSON specs and can run
through the existing bounded parallel jobs without another template system.
