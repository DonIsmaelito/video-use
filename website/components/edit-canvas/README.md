# Scenic edit canvas

## Current request and preserved design

“Okay i liked the design, could you make it into another video? possibly a more scenic? find a reference on youtube with the same zooming and flying, find one that is more scenic/possibly even fiction”

The user approved the wordless editing composition. Preserve its existing geometry, orange crop guides, sixteen-second decorative animation, agent cards and viewport/dialog behavior. This revision only replaces the film and its dependent stills/waveform, with a footer credit link. The earlier bowling film is retained in git history at `2b8c0b2`.

## Source and selection

The selected YouTube reference is **Iceland I Cinematic FPV flying 4k 2024** by **LHuFPV**: https://www.youtube.com/watch?v=lxk6XLZsdA0. Source time 03:04–03:28 is one continuous flight toward a moss-covered waterfall, around the drop and down the river. The original forward motion, full frame and color are preserved; no artificial zoom, hero copy, captions or extra controls are added. Its green cliffs, blue sky and moving water provide the scenic emphasis. The inspected Rocky Mountains reference was visually grayer; Blender’s Spring had fantasy scenery but less continuous first-person flight.

YouTube’s source metadata marks the 2024 upload Creative Commons Attribution with reuse allowed (CC BY 3.0). `footage.json` records the original URL, author, license, range and source/output hashes. `public/edit-canvas/credits.txt` contains attribution, a source link, license link and changes; the existing site footer links it as Footage credits. This does not imply authorship of the drone footage. Original source audio is excluded from playback.

## Assets and behavior

The 24-second delivery is 768×432 H.264 at the source’s 25fps, yuv420p, CRF 26, with fast-start metadata and no audio stream. Its four 640×360 stills come from delivery seconds 2, 5, 13 and 19. The waveform uses 120 RMS measurements of the corresponding source audio at 8kHz. All five visual assets and the manifest were regenerated together, so no bowling imagery or waveform remains. Native looping returns directly to the waterfall approach; it is not described as a seamless spatial continuation.

`EditCanvas` renders the approved composition and pauses CSS clocks while offscreen, hidden or behind a connection dialog. `PreviewMedia` retains muted inline autoplay, looping, poster fallback and autoplay retries. Reduced motion stops the decorative layers while keeping the existing user-requested video playback. Neither component’s runtime logic nor the composition’s CSS changed for this footage swap. The original gallery films and all catalog records stay separate.

## Replay and verification

The source receipt, frozen EDL, downloaded source, reproducible `render.py` and encoded proof frames live in `/Users/ismaelito/Movies/Video Use Scenic Showcase 20261007/edit/`. Run that `render.py` to regenerate `delivery/`. It validates the source SHA-256, extracts the exact range, encodes once and measures the matching waveform. Website-ready assets are copied into `public/edit-canvas/`; its `footage.json` is copied into this directory.

Run the website and scroll to `#agents` to review the composition. Check advancing silent video and end-to-start looping, the matching filmstrips, responsive panel geometry, six agent actions, poster failure, reduced motion and the footer credit. A dense encoded sequence is inspected separately from real-time browser transport; do not describe still-frame review as perceptual watching.
