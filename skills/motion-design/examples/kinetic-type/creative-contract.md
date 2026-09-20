# One clear thought

## Exact user-facing prompt

Make a short typographic film about the feeling of having too many tabs open in your head, then finding one clear thought. Let the words behave like the feeling. Use only type and simple graphic shapes.

## Authored decisions, separate from the prompt

This original sixteen-second typographic film makes mental interruptions physically occupy the same finite space. Opening words insist on room, oversized thought strips overwrite them, and the entire field compresses into one horizontal mark. That mark clears space for a soft serif thought. The changing behavior carries the emotional turn.

- Format: 1920 × 1080, 30 fps, 16 seconds.
- Typography: Inter Semibold for crowded, assertive thought; Instrument Serif for the release. Neither is supplied by the reusable runtime.
- Palette: warm paper, near-black ink, and vermilion used to signal interruption.
- Strongest frame: cream and vermilion thought ribbons collide across a near-black field, with an oversized central thought establishing hierarchy.
- Signature transformation: competing horizontal strips compress to a single baseline; that same line becomes the calm final phrase's underline.
- Rhythm: 0–3.2 s one thought becomes three; 3.2–7.4 s increasing interruptions; 7.4–9.8 s pressure and collapse; 9.8–11.9 s a breath; 11.9–16 s one clear thought settles.
- Assets: original code and wording, two locally bundled OFL fonts. No stock imagery, downloaded studio animation, or generated bitmap assets.
- Sound: the authored visual project does not require audio; any delivered score is a separately recorded decision, not part of the short prompt.
- Failure conditions: accumulation becomes uniformly illegible; static poster treatment replaces meaningful motion; final words lack enough reading time; sample wording leaks into shared runtime code.

`content.json` exposes every phrase, the palette, and construction seed. Different phrase lengths are measured and fitted at font-ready time. Film timing and shot design are intentionally authored in `scene.mjs`; this is a reproducible example, not a natural-language template dispatcher. Other prompts should receive a new composition that can reuse the small time/measurement/transform primitives.

## Provenance

- Inter Semibold, Rasmus Andersson and contributors, SIL Open Font License 1.1, https://github.com/rsms/inter . Local font was reused from `website/public/fonts/inter-semibold.ttf`; the accompanying `Inter-OFL.txt` is included.
- Instrument Serif, Instrument and contributors, SIL Open Font License 1.1, https://github.com/Instrument/instrument-serif . Local font was reused from `website/public/fonts/instrument-serif.ttf`; the accompanying `InstrumentSerif-OFL.txt` is included.
- Runtime: original video-use `skills/motion-design/runtime/motion.mjs`, copied into `lib/` for a self-contained scene. No npm runtime dependencies.

Review notes and render evidence are stored with the external rendered output. The short prompt records intention; exact reproduction depends on the delivered source, fonts, content, and renderer versions.
