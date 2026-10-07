# Wordless edit canvas

## Exact revision request

“did not really like the design, try again please - the hero is boring and this just looks too AI generated, maybe here it is more about the design than the hero and text”

This replaces the rejected orange sculpture, slogan and prompt box. The earlier version remains in git history at `fb8ee16`.

## Creative contract

The panel is an editorial composition of real film frames: a wide contact strip runs behind a selected moving image, a closer strip and actual audio waveform cross the foreground, and an orange playhead passes through the layers. The shared angle and overlapping crops connect the parts into one editing surface. There is no headline, campaign copy, invented status text, send button, mascot, glow or 3D primitive. The six adjacent agent cards supply the context.

The intended impression is a working film edit, with sharp orange selection marks, muted peripheral images and natural warm color in the selected shot. The key still is the complete layered composition at eight seconds. The motion is a restrained sixteen-second pan and return, with crop guides briefly appearing during the pass. A small projected editor and a stack of oversized logos were considered; the film-contact composition keeps the subject specific to video and makes photographic detail the focus.

## Assets and behavior

`footage.json` references the already published gallery film **A Night at Bryant Lake Bowl**, ID `useful-57-night-out`. Its source receipt in `data/media-sources.json` identifies the original JayByrd Films venue production. The complete twenty-second frame sequence and embedded credits are retained in a silent 768×432 H.264 preview at 24fps. It uses CRF 27, yuv420p and fast-start metadata; the original gallery movie stays unchanged. The original URL and both source/preview hashes are retained in the manifest. The four local JPEGs are 640px frames extracted at 6, 10, 14 and 18 seconds; their hashes and the source hash are in the JSON. The waveform is 120 RMS energy measurements taken from the existing film's mono audio at 8kHz. No synthesized photography or new stock is involved. The delivery-only preview encode is about 90% smaller than the original 1920px film.

`EditCanvas` renders the composition and pauses CSS clocks while offscreen, hidden or behind a connection dialog. `PreviewMedia` provides the existing muted inline looping playback, poster fallback, viewport handling and autoplay retries. Reduced motion stops the decorative layers; the existing video playback behavior stays consistent with the user's request for continuously playing clips. No controls or extra focus stops are added. Only one extra video element is used, with its small preview served alongside the local posters.

## Replay and verification

Run the site with its existing package lock and scroll to `#agents`. For a deterministic CSS frame, select `[data-edit-canvas]`, pause its `getAnimations({subtree:true})` and set each `currentTime` to the same milliseconds. Pause and seek its video separately to a stated source time, waiting for `seeked`. Reload before normal playback or pause/resume checks so manual animation-clock overrides cannot affect them. Source and choreography live in this directory; local stills are in `public/edit-canvas/`. QA evidence lives in `/tmp/video-use-edit-canvas-20261007/`.

Check the full sixteen-second CSS sequence, film playback, viewport/dialog suspension, narrow and wide layouts, and media failure. Reject any pose where peripheral strips obscure most of the selected footage, or where decorative labels and typography creep back into the design.
