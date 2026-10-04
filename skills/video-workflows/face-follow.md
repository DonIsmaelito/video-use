# Measured face following for edited footage

Use `helpers/face_track.py` and the normal `helpers/render.py` when a real
visible face should remain inside a portrait or square crop. This is measured
face detection followed by conservative spatial association. It is not person
recognition, head segmentation, automatic shot detection, or active-speaker
detection. A face box with an added head margin is a framing heuristic; review
the real hair/head outline in source and final frames.

The small official MIT YuNet model, model manifest and license are bundled in
`assets/models/yunet/`. They are pinned by source commit and SHA256. Install the
`motion-tracking` extra for OpenCV 4.x, plus FFmpeg/FFprobe. No model/provider
secret is required. Do not replace the pinned model with a new export without
checking its OpenCV compatibility and repeating the encoded tests.

## Observe then select

Acquire the actual licensed/source-authorized video first, preserve its URL,
hash, native dimensions and source-time mapping, and obtain word-timed speech
evidence before selecting speech cuts. Detection accepts one explicit continuous
shot of at most 120 seconds, and measures **every decoded frame** (up to 14400).
It retains source frame indices and integer PTS rather than assigning synthetic
timestamps from an assumed frame rate. Square pixels and zero metadata rotation
are required; normalize other sources once, retaining both hashes and the
conversion record, before tracking or transcribing that normalized source.

```sh
python "$FRAMEWORK/helpers/face_track.py" detect edit/source.mp4 \
  --start 1 --end 12 --sheet edit/face-observations.jpg \
  -o edit/face-observations.json
```

View the first source frame with labeled detection numbers, inspect the whole
shot for camera cuts/other faces, and write a selection file. Use its **actual**
first source frame index and detection number from the evidence:

```json
{
  "seed_frame": 30,
  "seed_detection": 0,
  "visually_verified": true,
  "continuous_shot_verified": true,
  "evidence": "Viewed source frame 30 in face-observations.jpg and checked the continuous shot",
  "speaker_mapping": {
    "speaker_id": "speaker_0",
    "method": "explicit_source_review",
    "evidence": "Source speech and visible mouth movement reviewed at the selected shot start"
  }
}
```

`speaker_mapping` is optional. Scribe speaker labels alone do not identify a
visible face. Never choose an active speaker from face size, left/right order,
or the existence of only one detected face. Omit the mapping unless source
review supports it. For two speakers, explicitly select separate tracks/shots
or author a fixed split layout; there is no automatic audiovisual speaker matcher.

```sh
python "$FRAMEWORK/helpers/face_track.py" select edit/face-observations.json \
  --selection edit/face-selection.json -o edit/face-track.json
```

The selected track embeds the measurements, their hash, reviewed seed, and each
frame's selected/lost/ambiguous state. Matching is geometric between adjacent
frames. It deliberately stops after missing/ambiguous evidence or an edge-clipped
face; a later similar face does not silently restart it. Crossing people,
occlusion, profiles and small faces can fail. Split at a genuine shot boundary
and review another seed, or use an explicitly authored fixed/contain layout.
Do not relabel sampled/manual crop keys as automatic face tracking.

## Render through the existing EDL

Each face-follow range needs a `layout` defining the final canvas and optional
picture window. All ranges in the edit must define the same canvas dimensions.
Track paths are relative to the directory containing the EDL, usually `edit/`:

```json
{
  "sources": {"interview": "source.mp4"},
  "ranges": [{
    "source": "interview", "start": 1.2, "end": 8.8,
    "layout": {"width": 1080, "height": 1920},
    "face_follow": {
      "track": "face-track.json",
      "padding": {"horizontal": 0.2, "top": 0.4, "bottom": 0.15},
      "smoothing_seconds": 0.12,
      "deadzone": 0.04,
      "max_pan_speed": 3
    }
  }]
}
```

```sh
python "$FRAMEWORK/helpers/render.py" edit/edl.json --fps 30 \
  --build-subtitles -o edit/final.mp4
```

Use the existing transcript/SRT contract when `--build-subtitles` is requested.
Captions still render last. Position them with an explicit design safe region
and inspect their actual glyph bounds against the face, hands and platform UI;
face following does **not** automatically place captions or guarantee every
platform's safe zones. Existing fixed picture windows can reserve caption space.

The planner chooses the largest exact even-pixel target-aspect rectangle inside
the original source. Padding is a fraction of the measured face width/height;
pan speed is crop widths/heights per second. Smoothing/deadzone reduce jitter,
but never override measured face containment. If the head margin cannot fit or
the necessary pan exceeds the configured speed, rendering fails for review.
This path performs position changes at a fixed crop size, not automatic zoom.

A full-height 9:16 crop can be too narrow for a wide head outline or existing
source titles even when the measured face fits. In that case use a wider picture
window on the portrait canvas, or an explicit contain layout. Do not treat the
detector box as evidence that hair, hands or source graphics remain intact.

No extra `range.reframe`, `layout.crop`, global `treatment.reframe` or global
`treatment.canvas` is allowed to recrop the verified face-follow result. Define
the required output canvas/window in `layout`; grade, graphics and captions
remain available. A fixed layout on another range is an explicit fallback.

The crop executes as numeric FFmpeg `sendcmd` updates inside the ordinary
per-segment decode/grade/encode. It does not create a lossy intermediate,
change source timestamps, or alter audio filters. Commands account for input
seek offsets on the stream time base, including nonzero container starts.
Temporary command files are removed even on failure. Preview changes delivery
size only, not measured source coordinates. Each encoded segment gets a
`.face-follow.json` proof with source hash, actual crop positions, commands hash
and selected track evidence. Normal audio fades, video-copy concatenation,
continuous audio assembly and captions-last composition remain in force.

## Review and replay evidence

Keep source acquisition/probe/hash, observation JSON, reviewed selection, selected
track, per-segment crop proof, EDL, caption word evidence and dependency/model
notices in the editable project. Reacquire excluded raw media from the recorded
permitted source and verify its hash before replay. The model lives in the
recorded public framework; source packages can refer to that pinned checkout
instead of bundling model weights repeatedly.

Inspect encoded start/end frames, motion extrema, each cut and speaker change,
and every ambiguous/lost interval. Compare crop rectangles to actual source
frames, and measure frame count, A/V event alignment and caption timing. Synthetic
colored-frame tests prove crop/clock behavior; they do not prove real-face
detection quality. Run and view a real acquired-source detector/crop smoke before
claiming this capability works for a new campaign's footage.
