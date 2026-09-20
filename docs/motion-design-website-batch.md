# Five silent films and the website gallery

The `five-for-website-20260914` batch adds five original 8-second, 1920×1080, 30 fps films. Each film contains one transforming hero, no supporting text, and no audio stream. The requests below are preserved exactly; expanded direction and subsequent repairs are separate in each source project's `PROMPT.md` and project review/validation notes.

| Film | Exact prompt | Reusable mechanism |
| --- | --- | --- |
| Rotary telephone | Make a glossy red rotary telephone spring into shape as its coiled cord draws a looping path. | Chassis, receiver, rotary dial and connected helical cord with independent pose controls. |
| Glass staircase | Make a stack of translucent colored glass tiles cascade into a spiral staircase. | Twenty original treads with ordered radial assembly and controllable turns. |
| Beach umbrella | Make a striped beach umbrella bloom from a spinning peppermint disc. | Connected canopy, ribs, braces, runner and pole with a native bloom control. |
| Ink octopus | Make a single blue ink droplet become a swimming octopus. | Original Canvas ink geometry with eight attached arms and an independent curl control. |
| Color zipper | Make a silver zipper unzip a midnight surface and reveal a flowing river of color. | Cloth panels, attached teeth, hollow pull and flowing ribbons with independent spread. |

## Repository structure

The five `.mjs` modules and accompanying recipe notes live in `skills/motion-design/library/recipes/`. Modules own geometry and pose controls; scene callers own timing, camera and lighting. The sibling `*-demo.html` files contain the corresponding portable callers. `library/catalog.json` now indexes 36 entries, including 16 original recipes. `library/prompt-examples.json` tracks 15 exact requests in three batches. Sound provenance belongs to each batch: earlier original scores are preserved, and this batch explicitly has no audio.

`website/data/examples.json` supplies the public video/poster URLs, prompts and categories. The gallery now contains 31 examples, including all fifteen tracked motion requests and four earlier motion studies. `website/data/media-sources.json` records provenance, starter-versus-original prompt status and website asset hashes. `website/components/gallery.tsx` keeps motion previews and full-player playback muted and looping. Other categories retain their existing full-player behavior.

All 19 website motion films and their posters are hosted in the existing Cloudflare R2 bucket under content-hashed keys. Each upload was fetched through its public URL and checked against the complete local file's SHA-256 before the gallery URL was changed. Independent public-URL ffprobe checks confirm the expected 1920×1080 dimensions, exact listed durations and zero audio streams for all 19 films. Source exports from earlier batches remain in their original delivery folders.

## Delivery and validation

The local delivery folder is `~/Movies/video-use-tests/five-for-website-20260914/`. It contains five individual MP4s, posters, `all-five.mp4`, exact prompts and `source.zip`. The silent 40-second reel contains 1,200 frames; every decoded frame was compared with the corresponding ordered source frame. Source archive CRC and all member hashes pass. The archive includes pinned dependencies, original geometry/assets, license receipts, source/control callers, selected proofs, helpers, the complete registry snapshot and reproduction instructions. It excludes node_modules, generated frame sequences and final videos.

Each scene and its native-control variant passes repeated and backward exact seeks. Technical QA checks the encoded films. Visual review covers selected full-resolution poses and decoded contact sheets; the source notes preserve the actual repairs, including handset headroom, glass transparency, octopus mantle continuity and zipper material lighting. The glass treatment is stylized translucent architecture rather than a physically accurate optical simulation. These are agent-authored creative expansions, not a measured autonomous benchmark or evidence about Higgsfield's private implementation.

The localhost gallery passes TypeScript/content checks and a production build. The walkthrough uses a fresh anonymous Chromium session because the connected Browser runtime reported no available browser. It records the real localhost page, actual clicks, copied prompts and video playback. Presentation cursor events and postproduction framing belong only to the capture pipeline; they are not product UI changes. The website remains a local preview and was not deployed.

The finished [74.833-second walkthrough](https://pub-ec8bfc71ab97450e915c455459d2d57d.r2.dev/website/demos/2026-09-14/website-walkthrough-faeb3c977082ee01.mp4) is also stored as `website-walkthrough.mp4` alongside the film delivery. It passes full decode, 2,245-frame, 1080p30, zero-audio and faststart checks; its public R2 download matches the local SHA-256. `recording-source.zip` preserves the capture/compositor source, original events and framing assets, while `review/website/` retains the raw browser capture and validation evidence. Film/source checksums intentionally exclude these later recording artifacts. Safe cleanup removed regenerable caches and duplicate artifacts only after archive or public R2 hash verification; original source deliveries and user browser profiles were preserved.
