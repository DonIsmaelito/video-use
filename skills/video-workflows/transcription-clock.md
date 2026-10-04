# Transcripts on the source clock

`helpers/transcribe.py` extracts the first audio stream as mono 16 kHz PCM for
Scribe. Word times must use the same source clock as the EDL: decoded presentation
timestamps minus `format.start_time`. A WAV contains samples but no packet
timestamps, so simply decoding audio can silently move delayed speech earlier
or remove timestamp gaps. The helper uses FFmpeg's timestamp-aware resampler to
fill/trim those gaps before writing WAV. It does not modify the source or the
final soundtrack, stretch speech, or infer word boundaries from silence.

The `_video_use` cache identity records the source SHA256, model, language,
speaker settings and versioned extraction filter. Version 2 uses the explicit
source-clock policy. Unchanged compatible caches are reused without an API call.

Version 1 caches used an untimed extraction. They are reused without rewriting
only if one audio stream's **entire decoded timeline** agrees with a continuous
sample clock starting at zero, within one 16 kHz sample. The check uses decoded
frame PTS and sample counts, so AAC priming and internal gaps are included.
Checking only a stream's start time is insufficient. Multiple audio streams,
missing timing, larger offsets/gaps and uncertain timing fail closed. A rejected
cache remains unchanged; preserve it and transcribe to a separate edit directory
with the new helper, or record an independently measured migration. Do not change
its version field to make it appear compatible.

Retain the exact source and transcript hashes in edited projects. Selecting a
new excerpt maps saved source word times through the EDL; it does not require
another transcription of the same compatible source. Diarization labels still
need explicit audiovisual evidence before association with visible faces. ASR
timing is automatic evidence and does not constitute a human listening review.

Encoded regression tests place two actual AAC tone events at source PTS across
44.1/48 kHz, positive/negative audio offsets and nonzero container origins, then
compare the extracted WAV event times against independently probed/decoded source
samples. A separate discontinuous PCM source exercises a gap after time zero.
See `tests/test_transcribe_clock.py` and the official
[FFmpeg resampler options](https://ffmpeg.org/ffmpeg-resampler.html), especially
`async`, `first_pts` and compensation thresholds.
