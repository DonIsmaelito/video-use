# Sound as a motion input

Use sound analysis when a visual behavior should follow actual audio. A score can also be authored alongside motion with deliberate phrase-level decisions. Choose the relationship for the brief; do not turn every film into a reactive visualizer.

`helpers/motion_audio.py` decodes the first audio stream with FFmpeg and uses NumPy to create versioned, time-indexed controls. It makes no assumptions about BPM, genre, instruments, scene type, or design style. It does not interpret a prompt or choose a visual composition.

```bash
python3 helpers/motion_audio.py soundtrack.wav -o analysis.json
python3 helpers/motion_audio.py interview.mp4 -o voice.json \
  --start 12 --duration 8 --offset 4 \
  --bands voice:250:2000,air:4000:10000
```

The second command analyzes input seconds 12–20 and positions the resulting samples at timeline seconds 4–12. `--start` trims source audio; `--offset` changes analysis timestamps. They are independent. `--bands none` omits frequency features. The default decoding rate is 24 kHz with 2048-sample Hann windows and 60 analysis frames per second. This analyzes frequencies up to 12 kHz; increase `--sample-rate` and adjust bands when higher frequencies matter. Band boundaries must lie below Nyquist, and the FFT window must resolve at least one frequency bin per band.

## Data contract

Schema version 1 records duration, sample rate, analysis rate, window size, timestamp convention, smoothing settings, bands, normalization scales and source file hash. Each frame includes:

- `time`: absolute timeline seconds at the center of an analysis window. Windows that extend beyond the audio are zero padded. The final timestamp is less than `offset + duration`.
- `rms` and `peak`: loudness-related energy and peak amplitude, normalized against this entire analysis.
- `envelope`: RMS smoothed using configurable attack and release times, then normalized.
- `onset`: positive spectral change between adjacent windows. This is an accent-strength signal, not a detected beat, BPM estimate or guarantee of a distinct musical event.
- `bands`: normalized spectral RMS in each requested frequency range.
- `raw`: unnormalized RMS, peak and band RMS. These preserve physical amplitude relationships that independently normalized bands would hide.

Normalized values lie in 0–1 using the chosen global percentile (95 by default), with a small amplitude floor and clipping. Onset normalization uses positive values so a sparse signal does not acquire a zero scale. Silence remains zero; quiet passages are not stretched independently to full strength. Different bands normalize independently, so compare **raw** band values when judging which frequency region dominates. The stored scales allow recovering unclipped relative amplitude only below the clipping threshold; use raw values when exact energy matters.

FFmpeg downmixes to mono. Opposite-phase stereo content can cancel; this is an analysis choice, not a measurement of perceived stereo loudness. The helper decodes the selected segment into memory; trim very long sources with `--start` and `--duration`. RMS and onset windows can anticipate an event by half the window length because timestamps describe window centers. For hard lip-sync or percussion cuts, inspect the actual soundtrack and choose an appropriate window or offset.

## Author the relationship

Choose distinct behaviors for distinct features: bass could bend a broad surface, bright energy could open narrow petals, and low overall energy could reduce motion and restore negative space. Those are design decisions for one film, not defaults in the helper. Use the shared runtime's `keyframes` to interpolate flattened numeric controls, or an equivalent absolute-time sampler. Precompute smoothing and cumulative measures once. Never accumulate particle state or sample random numbers inside `seek`.

Validate the mapping with a different soundtrack, silence, and isolated frequency signals. Changing the input should change the motion in the expected way without changing code or assuming the demonstration's tempo. Interpret mechanical tests separately from a visual and listening review: data extraction does not establish that the composition is interesting or the sync feels right.

The [Signal Garden example](../examples/signal-garden/README.md) preserves the short prompt separately from its creative expansion. Its garden artwork and original score are an editable example, while the analyzer is reusable infrastructure.
