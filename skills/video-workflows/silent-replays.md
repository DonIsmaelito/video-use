# Silent replay derivatives

Use `helpers/silent_retime.py` for an explicitly labeled slow or fast replay of
footage that has **no audio stream**. It makes one new H.264 source with its own
hash and clock. It repeats or drops existing frames; it does not generate
intermediate motion, preserve speech, or claim automatic subject tracking.

```bash
python /opt/video-use/helpers/silent_retime.py edit/source.mp4 edit/replay.mp4 \
  --start 5.5 --end 8.5 --speed 0.75 --fps 30 \
  --source-sha256 RECORDED_SOURCE_SHA256 > edit/replay-provenance.json
```

This example produces four seconds. Select a positive source interval of at most
120 seconds, speed from 0.25 through 2, and integer output FPS from 1 through 60.
The result must contain a whole number of frames and last at most 300 seconds.
The helper verifies actual display timestamps, including variable frame rate and
nonzero container origins. Source time zero follows the container's start;
the requested interval must lie within actual decoded video coverage.

The input must contain one ordinary, unrotated, square-pixel SDR video with even
dimensions, no side larger than 4096 pixels, and at most 8,388,608 pixels. Audio
is rejected even if its samples happen to be silent. Existing output paths,
symlinks, source-hash mismatches and sources changed during rendering fail
without replacing the source or a previous output. Inspect the encoded replay
at its first/last frames and action peak; a slow original may visibly repeat
frames. Numerical frame/clock checks do not replace that visual review.

Add the derivative to the EDL's sources as a separate file, then select it on its
new zero-based clock with the normal renderer. Preserve the JSON mapping to the
original clip. Original-source face tracks, crop measurements and transcript
timestamps cannot be reused against the derivative hash. Perform any required
measurements on the new file. Music or original procedural sound can be mixed
separately on the final output clock; do not fabricate recorded location audio.

For boundary QA, `timeline_view.py` accepts the exact video endpoint. If a normal
seek emits no image there, it resolves the actual last decoded frame rather than
guessing from average FPS. Requests beyond the measured endpoint still fail.
