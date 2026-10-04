# Original tonal beds and soft pulses

`helpers/ambient_audio.py` synthesizes sustained sine tones and explicitly timed
soft pulses. It is useful for a quiet original bed under a silent montage. It
does not recreate location sound, generate a finished musical composition, or
sample recordings. Choose the frequencies, timing and gains for the actual edit;
the example below is only a short reproducible score.

```json
{
  "version": 1,
  "duration": 8,
  "sample_rate": 48000,
  "seed": 17,
  "headroom_db": 3,
  "fade_in": 0.6,
  "fade_out": 1.0,
  "tones": [
    {"frequency": 146.832, "gain": 0.035, "pan": -0.25},
    {"frequency": 220, "gain": 0.025, "pan": 0.25}
  ],
  "pulses": [
    {"start": 0.4, "duration": 1.2, "frequency": 73.416, "gain": 0.06, "pan": 0},
    {"start": 3.4, "duration": 1.2, "frequency": 73.416, "gain": 0.06, "pan": 0}
  ]
}
```

Save this as `edit/ambient-score.json`, then run:

```bash
python /opt/video-use/helpers/ambient_audio.py edit/ambient-score.json \
  -o edit/ambient.wav > edit/ambient-report.json
```

The output is stereo PCM16 WAV with the exact duration rounded to the nearest
sample. The score's seed selects oscillator phases, and manifest order is stable.
The report includes the score/WAV hashes, actual sample count, peak, headroom and
NumPy version. Preserve the score, report and recorded dependency versions for
replay. Bit-identical floating-point synthesis across different environments is
not promised.

Scores are limited to 120 seconds, 8–96 kHz, 16 sustained tones and 512 pulses,
with a bounded total oscillator sample budget. Frequencies must be 20 Hz through
45% of sample rate, gain 0–1, and equal-power pan −1 through 1. A pulse must fit
entirely within the score and span at least four samples. Raised-cosine global
fades each span at least two samples and together fit the timeline; all final
endpoints are exactly silent. Unknown fields, nonfinite values and oversized
manifests fail before synthesis.

The helper reuses `tactile_audio.py`'s sample-boundary, headroom and PCM writer
checks. It rejects the complete overlapping sum when its peak exceeds the
requested 0–24 dB headroom; it never silently clips or normalizes. Lower the
authored gains when this happens. Output paths must be new and distinct from the
JSON score; existing files and symlinks are preserved, and failed writes clean
up only their own temporary files.

After normal rendering, mux the bed with FFmpeg while copying the reviewed video
packets. If the film already has sound, explicitly mix the bed with that preserved
audio on the output clock instead of replacing it. Keep spoken audio intelligible
and check the final encoded mix. Numeric peak checks do not
certify perceptual quality, music suitability, or a listening review. Label this
as original procedural sound when a viewer might otherwise assume it was
recorded with the footage. Use `tactile_audio.py` for distinct taps and slides.
