# Product demos through OpenScreen

Use this route to polish a real screen recording with a background, rounded
window, shadow and camera moves. OpenScreen implements the effects. The agent
chooses what deserves attention and writes the small cue specification. Do not
build a replacement compositor, transcribe silent footage, invent cursor clicks,
or use montage cuts for this full-length route.

Read [setup and commands](../integrations/openscreen/README.md). The current
adapter is a tested Apple Silicon macOS import path. OpenScreen itself also
supports recording and other platforms; those are distinct integration paths.

## Editorial choices

- Establish the product and complete application before focusing on a control.
- Highlight meaningful input, interaction, actual progress and the result.
  Keep the main application visible for most of the recording. A video playing
  inside the product is one feature, not the entire product demonstration.
- Use sparse, modest zooms. Start with depth 1 (1.25x). Brief holds return to an
  overview so viewers understand where the action happened. Choose cue times
  from source frames or real action timestamps, not guessed milestones.
- Keep the entire recording at 1x. The adapter has no cut, speed or cropping
  fields. If the user wants a montage, choose a different editing route.
- Existing visible cursors stay in the source. Replacing or smoothing a cursor
  requires a recording made with editable cursor telemetry; do not draw a
  second cursor over an imported one.

The cue contract uses `settle_s` (fully zoomed) and `hold_end_s` (start returning).
OpenScreen v1.11.0's native transition starts about 1.523 seconds before settling
and ends about 1.015 seconds after the hold. Those timings are upstream behavior,
not the old custom camera's 0.33-second ramps. The validator preserves overview
gaps around the complete movement. It rejects unsupported easing/custom-scale
fields because the upstream legacy loader silently discards them.

## Review and delivery

Inspect encoded frames at overview, entrance, settled focus, exit and the final
screen. Check text readability, source proportions, smooth movement, source
edges, background, cursor count and the important app controls. Listen when
there is audio. The helper checks decoding and technical metadata; its status
`technically_verified` deliberately leaves visual review `pending`.

Keep the original source, cue specification, `.openscreen` project, manifest,
native logs, verification result and delivered MP4. A changed source/project
invalidates its preparation manifest. Prepare a new bundle for revisions.
The project can be opened in OpenScreen for manual editing; edits made there
need a new validation path rather than reusing the original manifest.
