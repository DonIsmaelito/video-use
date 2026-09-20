# video-use website

The open-source library's inspiration gallery, kept separate from the Python editing harness and `gui/` product.

## Run locally

Requires Node 22.13 or newer.

```sh
cd website
npm ci
npm run dev
```

Open the Local URL printed by the server. It tries port 3000 first and picks the next available port if needed.

```sh
npm run build
npm run check
```

## Where things live

- `app/page.tsx` composes the opening, gallery, and footer.
- `app/globals.css` owns the lavender palette, typography, layout, responsive behavior, and animation.
- `components/hero.tsx` rolls whole words upward with the reference’s 500ms cube transition and 1200ms hold, respects reduced motion, and reads GitHub's public stars count. If GitHub is unavailable the link remains available without inventing a count.
- `components/getting-started.tsx` supplies one copyable git clone command below the headline, aligned to its left edge and centered vertically alongside the rotating word on desktop. The box has balanced padding and a text-only copy action. A manual-copy dialog handles unavailable clipboard access.
- `components/gallery.tsx` owns filters, category sections, scroll-driven previews, the accessible detail dialog, and clipboard feedback. Videos load metadata near the viewport and play silently together while visible. They pause offscreen, in a hidden tab, when reduced motion is enabled, or when a gallery dialog opens; they resume when those conditions clear. Hover or keyboard focus reveals the scrollable prompt and copy action inside each card. Motion Design stays muted and loops in the full player. Video Creation uses audible playback for its footage-based montages and reviews. Touch users tap to open it.
- `components/wordmark.tsx` closes the page with a dim lavender VIDEO USE wordmark, cropped at the bottom to reveal about 70% of the letterforms.
- `lib/gallery.ts` provides filtering, duration formatting, and the fixed section order: Video Edits, Video Creation, Motion Design, Explainers. All examples is the combined view.
- `data/examples.json` supplies the gallery cards and category counts. Media is hosted in Cloudflare R2. The gallery contains original motion studies and eight original cloud-generated films; the explainer collection now contains six reviewed Fable/Astra examples.
- `public/media/` retains earlier bundled assets for history; the active gallery uses R2 media.
- `data/media-sources.json` records provenance, saved prompt status, model authorship, source/website hashes, and review links. The canonical motion recipe and exact prompt ledger remain in `../skills/motion-design/library/`.

`promptKind` distinguishes saved original prompts from self-contained starter prompts adapted from the source run. Starter prompts are examples, not a claim that these exact words produced the displayed result. Posters and scroll-driven playback use the same centered crop to fill each 16:9 card, with no hover zoom or format change. The video fades over its poster once playback starts. The popup preserves the video's complete original frame and shows a reusable prompt with its copy action.

The previous five motion requests are tracked under batch `five-for-website-20260914`: rotary telephone, glass staircase, beach umbrella, ink octopus, and color zipper. Their short prompts are preserved separately from expanded art direction and repair notes. The silent website copies preserve the original video stream; earlier scored exports remain in their original delivery folders. The older adapted starter prompts were updated to request silent output.

## Cloud motion batch

Batch `motion-cloud-20260915` adds eight original films, 12–18 seconds each: Make Room, Night Shift, Paper Current, Little Weather, Woven Signal, Ink Relay, One Good Day, and Shape Jazz. Each ran independently in Modal with `gpt-6-astra` at medium reasoning, using the unchanged `fix-review-recovery` framework at `2c25bb58cabdfb02203ff2a637b48d60143b7dc4`. Agents received creative briefs and generic tools, with instructions excluding earlier scene implementations and template explainers.

Generation, rendering, encoded-frame extraction, full-decode verification, R2 uploads, and the website build ran in Modal. The gallery shows the exact creative request; `data/media-sources.json` links the full request, editable source archive, contact sheet, review, and verification record for each film. All eight are silent 1920×1080 H.264 videos at 30 fps. Review used encoded frames and technical checks; real-time human playback was not performed.

## Cloud source-edit batch

Batch `edit-cloud-20260915` adds eight edits: Messi goals scored to Joy Crookes, a stacked podcast exchange, Nacho Libre, a food-review cutdown, comedy, a recipe, a restoration, and a rainy Kyoto travel story. Every editing agent used `gpt-6-astra` at medium reasoning in a separate Modal container. The unchanged framework came from `integration/latest-video-use-20260908` at `a501db6f98692aabd2c7a1b9a772cbbf5d17e742`, before the later optimization work. Agents received concise creative prompts and separate technical delivery instructions, with no supplied scene implementations or fixed review-pass limit.

Source acquisition, transcription, editing, rendering, encoded-frame review, audio measurements, full-decode checks, and R2 uploads ran in Modal. The exact creative prompts appear in the gallery. Provenance links include editable code and EDL archives, source ledgers, reviews, and verification records. Original downloaded media and audio stems remain in each durable Modal project; the downloadable source archives omit those large media files. Review used encoded images and measured timing/loudness rather than real-time human audition.

## Reviewed explainers

The four earlier explainer cards have been replaced with six existing R2 outputs: soap-bubble color, jet engines, GPU data flow, diffusion models, binary search, and hash-map collisions. Fable authored the jet-engine and hash-map examples; Astra authored the other four. Selection checked encoded frames throughout each timeline and full decoding at 1080p. Refreshed posters show representative content instead of early fades. The videos themselves are unchanged. Model evidence, source object keys, hashes, and review sheets are recorded in `data/media-sources.json`.

## Design and assets

### Video Edits

Video Edits contains twelve technique demonstrations: four edits of the same camera unboxing, four Tears of Steel studies, plus Split Screen, Auto Captions, Reaction Cuts, and Step Selection. Video Creation contains sports, film, restoration and travel montages plus a food review. Motion Design includes Paper Collage and Character Animation alongside typography, graphic loops, UI animations and object studies. Explainers contains teaching videos. Every card label is one to three words describing its technique, design or format. All four sections share the category heading, count, grid, viewport autoplay and prompt dialog. Inline cards autoplay muted; the full player preserves source audio for Video Edits, Video Creation and Explainers. Motion Design stays muted and loops.

The earlier Apollo effects collection was replaced by four practical edits of an unedited camera unboxing: Cut the pauses, Show the details, Skip the setup, and Make it vertical. Four independent Modal workers used GPT-5.6-Luna with high reasoning and the unchanged video-use framework. The examples keep the source voice and handling sounds. Review checked source ranges, encoded frames, full decoding, audio levels, and an independent transcription of the finished speech. Website review also corrected setup speech boundaries and moved portrait captions above the product. Source provenance, editable EDLs and review links remain internal in `data/media-sources.json`.

The opening takes its large serif composition and lavender rule from https://studiohuncho.com/work. The gallery follows https://melies.co/cinematic-techniques with five desktop columns, 6px gaps, 16:9 media windows, 10px corners, wrapped category filters, and every category in one continuous scroll. It adapts to three, two, and one column on narrower screens. The header uses the Browser Use logo at 56px on desktop and 46px on mobile, alongside a text-only GitHub link. The hero has no icons or supporting paragraph. Instrument Serif is reserved for the headline and footer. Inter is used for filters, counts, copy actions, and prompts; the clone command uses a system monospace. Each category has a heading and count; each card has its title inside the media window. Fonts are bundled locally with their OFL licenses.

All gallery clips come from prior video-use runs; `data/media-sources.json` records the run IDs and source types. The share image is an original generated asset.

This preview has no account system, uploads, or editing backend. Its header links to the open-source repository. Before deployment, set `SITE_URL` to the chosen public origin so social previews use the production URL. Keep `.openai/hosting.json` and `sites()` in the Vite configuration for Sites compatibility.

## Tears of Steel edit demonstrations

Four 10–12 second edits use the same licensed film acquired with yt-dlp: a speed ramp, a freeze-frame poster, an animated split screen and a cinematic grade comparison. Each initial author ran video-use with GPT-5.6 Luna at high reasoning in a separate Modal container. The speed-ramp and grade-comparison edits received targeted Luna-high repairs after independent review found timing, wipe-direction and framing defects. A failed speed-repair worker was recovered from saved files; the finishing pass used persistent project storage. The displayed creative prompts remain the exact initial requests; full requests, repair instructions, model/container evidence, editable projects, output hashes and review evidence are linked from `data/media-sources.json`.

Source: (CC) Blender Foundation | mango.blender.org, [Tears of Steel](https://www.youtube.com/watch?v=R6MlUcmOul8), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). These clips are modified excerpts. Review covered encoded transition frames, full decoding, media dimensions and duration, HTTP range responses and MP4 faststart. Browser interaction and subjective audio listening were unavailable. The [32 researched edit briefs](docs/video-edit-prompts.md) are saved for future examples; the gallery displays the rendered examples and their exact prompts.

## Local motion collection

Batch `motion-local-20260916` adds 24 original ten-second studies at the beginning of Motion Design, bringing that section to 50 examples. Eight graphic studies, eight sculptural 3D pieces, and eight illustrated animations use distinct compositions and movement mechanisms. The existing card layout, viewport autoplay, full player and prompt-copy controls apply to all new entries.

All 24 are silent 1920×1080 H.264 MP4s at 30 fps. Artwork and animation were authored and rendered locally using Canvas and Three.js; the videos are served from the existing R2 media bucket. The displayed prompts are reusable authored production briefs, labeled internally as starter prompts rather than exact user messages. `data/media-sources.json` records each file hash, rendering provenance, family, prompt URL and verification summary. Editable projects remain in the local collection delivery.

Review covered deterministic seeks, proof and encoded frames, all 7,200 decoded frames, and public media byte-range responses. The published files preserve the reviewed local video bytes. No gallery components, layout, or playback mechanics changed for this batch.
