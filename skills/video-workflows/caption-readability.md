# Caption density and capacity review

Use `helpers/caption_readability.py` to find cues that deserve a closer timing or
layout review. It reads SRT or ASS and emits JSON without editing either file.
Warnings are advisory: the command exits successfully when it produces a valid
report, even if cues are flagged. It is not an additional render approval gate.

```bash
python /opt/video-use/helpers/caption_readability.py edit/master.srt \
  --font edit/assets/inter-semibold.ttf --font-size 68 \
  --max-width 864 --max-lines 2 > edit/caption-readability.json
```

Use the actual delivery font and pixel dimensions. Omit all four layout arguments
for a timing-only report. The same command accepts `edit/captions.ass`. The input
file hash, cue source lines, exact text and times, character/word counts, overlap
pairs and optional font hash remain in the report.

The default heuristics flag more than 24 characters per second and cues shorter
than 0.8 seconds containing at least five whitespace-separated words or 30
characters. They caught the real eight-word 0.62s and 0.58s conversation cues
that fit spatially but flashed too quickly. These are working review thresholds,
not universal language or accessibility standards. Adjust `--max-cps`,
`--short-seconds` and `--long-words` for the actual material. A single token up to
12 characters, such as a brief “STOP!”, is not automatically a density warning.
Characters include spaces; punctuation remains, and word counts use whitespace.

Overlap is temporal, with half-open intervals: a cue ending exactly when the
next starts does not overlap. ASS layers are preserved so intentional speaker
lanes can be reviewed. All pairs are counted; only the first 1,000 pair details
are retained. Inputs are bounded to 1 MiB and 4,000 cues. Malformed timings or
unsupported event formats are reported as input errors rather than silently
discarding cues. ASS centiseconds, commas in dialogue and `\N` line breaks are
handled explicitly. Vector drawing events are identified, not counted as speech.

Capacity uses the existing caption helper's word wrapping and the supplied font
metrics at one fixed size, preserving explicit line breaks. It reports the lines
and measured widths. It does **not** simulate libass shaping, auto-shrinking,
font substitution, safe zones, inline transforms or collisions with faces and
other graphics. ASS style metadata is retained; inline overrides request visual
review. Compare the estimate with the real caption renderer and inspect the
encoded frames, including transitions and the longest cue.

Read flags alongside the source audio, reviewed words and actual edit map. Do
not solve a density warning by silently dropping speech, lengthening a caption
into unrelated dialogue, or attributing overlapping words to the wrong speaker.
An intentional short emphasis or split-speaker overlap may be correct. Record
any approved phrasing/timing change separately from the raw transcript, then
review the encoded result. A report with no automatic flags is not semantic,
speech-alignment or perceptual approval.
