# Original tap and slide accents

Use `helpers/tactile_audio.py` when a product motion needs restrained, original mechanical accents. It synthesizes filtered noise and decaying tones; these are **procedural sounds, not recorded Foley or a simulation of a named material**. No outside recordings, models or services are used. It does not generate music or speech. Choose whether these sounds suit the film and review the resulting mix; silent films do not need an empty audio track.

Save an explicit event timeline, then render a stereo PCM16 WAV:

```json
{
  "version": 1,
  "duration": 20,
  "sample_rate": 48000,
  "seed": 207,
  "headroom_db": 3,
  "events": [
    {"kind": "slide", "start": 4.3, "duration": 1.9, "pan": -0.4, "gain": 1},
    {"kind": "tap", "start": 6.5, "duration": 0.4, "pan": -0.4, "gain": 1}
  ]
}
```

```bash
python /opt/video-use/helpers/tactile_audio.py edit/sound-events.json \
  -o edit/assets/tactile.wav > edit/audio-report.json
ffmpeg -i edit/silent.mp4 -i edit/assets/tactile.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k \
  -movflags +faststart edit/final.mp4
```

`start` and `duration` are seconds; every event must fit entirely inside the timeline. Absolute timestamps round to the nearest sample, with half samples rounded up. The WAV has exactly `floor(duration * sample_rate + 0.5)` frames. Events require at least four samples and have zero-valued endpoints. `pan` uses equal-power gains from −1 (left) through 0 (center) to 1 (right). `gain` is a linear multiplier from 0–16; 1 retains the intentionally quiet original levels. Overlapping events sum without automatic normalization. If their sum exceeds the requested peak headroom (3 dB by default), generation fails before writing output. Lower event gains or reduce overlap, then regenerate. PCM16 quantization can change the measured peak by half a quantization step.

All numeric values must be finite. Rates are integer 8–96 kHz, durations up to 600 seconds and at most 28.8 million stereo frames; timelines allow at most 2,048 events with a bounded total synthesis budget. The seed is an integer from 0 through 2⁶⁴−1. An empty event list produces exact silence. Unknown fields are rejected so spelling mistakes do not silently alter a mix.

The same ordered timeline, seed and NumPy version produce identical PCM. Keep the JSON, helper version, NumPy version and reproduction command with editable source; generated audio can be recreated instead of included in a source archive. The JSON report records levels and length, not listening quality. Inspect the encoded final audio/video and do not claim an audio audition when only levels were checked. To make motion follow an existing soundtrack, use the separate [sound analysis helper](audio-motion.md).

Adapted from the original deterministic sound proposal produced for the Video Use modular desk showcase; the shared helper adds a validated event contract, sample boundaries, bounded allocation, explicit headroom rejection and safe PCM output.
