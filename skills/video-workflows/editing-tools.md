# Reusable editing tools

Read only the reference needed for the current source and edit. These helpers
are available under `/opt/video-use/helpers/` through `run_video_step`; reference
files are readable with `video_use_guidance` using their `skills/` paths.

- [Caption readability](caption-readability.md): advisory
  SRT/ASS density, overlap and measured line-capacity report; no automatic edits.
- [Measured face following](face-follow.md): reviewed
  physical targets and actual per-frame observations through the normal renderer.
- [Transcript clocks](transcription-clock.md): source-bound
  cached word timing and explicit audio-offset validation.
- [Per-shot layouts](shot-layouts.md) and
  [continuous reframing](continuous-reframing.md): explicit
  picture windows and authored crop motion, distinct from measured face tracking.
- [Silent replays](silent-replays.md): bounded speed changes
  for sources with no audio, retaining a separate derivative hash and time map.
- [Original ambient audio](original-ambient-audio.md):
  explicit tone beds and pulses; original synthesis, never recorded location sound.

Source inspection, speech boundaries, caption meaning and actual encoded-frame
review remain part of the edit. A numeric report does not certify final quality.
