# Video Use in iMessage

## Placement and design

The requested section sits between the featured workflow carousel and the Video Editing preview. It brings the homepage to seven content sectors. Filtered root URLs and the collection/library pages do not show this promotion.

The desktop layout is one symmetrical composition. The phones lean inward into a shallow V, with the title and two descriptions centered between them. Each description aligns with its respective phone: camera-roll editing on the left, reference-guided creation on the right. This replaces the initial two-row layout following the user's request to reduce its height. Below 1024px, the phones remain side by side, with the title above and the two context columns beneath. Open page background, a subtle warm glow, restrained pill labels, Space Grotesk headings, Inter body copy, and Browser Use orange connect the feature to the existing site.

`ImessageFeature` owns the shared grid. Its internal `ConversationPhone` accepts a left/right position; the CSS module applies mirrored rotation and perspective while keeping each screenshot and its frame together. The desktop tilt is 10 degrees, with gentler 8-degree tilt on smaller screens. Screenshots preserve their full aspect ratio. The frame is the unmodified `phone.png` used above Send at https://family.co/. Its source and hash are recorded in `public/imessage/asset-sources.json`.

The phone stages have a warm Browser Use orange halo and a blurred mist layer behind the devices. `mistDrift` gently translates, rotates and fades the mist over a 16-second alternating cycle; the two sides have offset timing. Both layers are decorative CSS pseudo-elements with no pointer interaction or effect on layout height. Reduced motion keeps the orange glow but stops the decorative animation. Video preview playback remains independent.

The copy describes selected clips shared from Photos. The current messaging implementation can inspect and edit those assets, search public references, and create original videos. It does not have unrestricted private camera-roll access, so the promotion does not claim that capability. No new public onboarding destination or phone number has been invented.

## Conversation screenshots

The user supplied both original PNGs on 2026-10-07. They are copied byte for byte to `public/imessage/`, with dimensions, hashes and provenance in `asset-sources.json`.

| Phone | Screenshot | Natural size | Conversation |
| --- | --- | --- | --- |
| Left | `video-use_1.png` | 1179 × 2327 | Adjusting a punch to the word “Sway” and receiving the revised video |
| Right | `video-use_2.png` | 1179 × 2347 | Reviewing a Linear reference and requesting a Browser Use video |

`data/imessage-conversations.json` provides each image's source, dimensions and descriptive alt text. `ConversationPhone` uses Next Image for responsive, lazy-loaded display, with `object-fit: contain` and a black screen background so the full supplied screenshot remains visible. The screen links to the original PNG in a new tab for full-size reading, with a keyboard focus indicator and an accessible link name. No raster edits or invented messages are used.

The temporary placeholders and production guard have been removed. The complete section now renders in production; filtered root views and collection pages continue to omit it.

## Verification

The initial draft passed the production build, TypeScript/catalog validation, all 30 importer checks, lint, and responsive layout/playback checks. Evidence for that superseded two-row layout is stored in `/tmp/video-use-imessage-20261007/qa/`.

The new module does not change `PreviewMedia`, the headless playback provider, the 172-film catalog, or any media URL. Actual scrolling playback is checked separately; screenshots of the chat feature are intentionally static images, while the existing video containers remain muted autoplay loops with no Play/Pause control.

The compact revision measures about 684px tall at 1440px, compared with roughly 1830px for the original. Its layout checks cover symmetric phone geometry, separation of text and phones, uncropped device frames, balanced heading wraps, unchanged placement above Editing, and absence of horizontal overflow. Fresh screenshots and the final browser checks are stored in `/tmp/video-use-imessage-compact-20261007/qa/`.

The production build, TypeScript/catalog checks, 30 importer checks, lint and diff checks pass. Chromium layout checks pass at 1440, 1280, 1024, 1023, 768, 540, 390 and 320px; desktop and phone screenshots were reviewed in Chromium and WebKit. Both engines confirm real playback in every visible Editing preview after scrolling through the promotion, and the featured video resumes on return. One clip stalled at time zero in the first combined WebKit run; a clean focused run passed all ten desktop clips and all six phone clips without changing playback code. These compact-layout checks preceded the final screenshots.

The orange mist pass is verified in Chromium at 1440, 390 and 320px and WebKit at 1440 and 390px. Animation timelines and successive rendered screenshots confirm actual motion; reduced-motion mode removes the mist animations while retaining the halo. Device placement and section height stay intact, with no horizontal overflow. WebKit reports empty computed animated pseudo-element transforms, so motion verification uses the animation timeline and rendered pixel differences. Its phone height is compared with the existing WebKit baseline rather than Chromium's font metrics. Evidence is in `/tmp/video-use-imessage-mist-20261007/qa/`.

## Final screenshot verification

The supplied assets pass the production build, lint, TypeScript/catalog validation, all 30 importer checks and diff checks. Production browser checks pass in Chromium at 1440, 1024, 390 and 320px, and WebKit at 1440 and 390px. Both screenshots decode, preserve their aspect ratio, and match the original PNG hashes. Desktop keyboard activation and phone taps open each original in a new tab. The section follows the featured carousel and precedes Editing, bringing the content-sector count to seven. There is no horizontal overflow or browser page error. Reduced motion retains the halo and disables the decorative mist.

Actual video time advances for every visible preview at the top of all three collections in both engines at desktop and phone widths: Editing 10/6, Creation 8/6, and 3D 15/9. Featured playback resumes after scrolling back. No preview Play/Pause control is present. Evidence, reviewed screenshots and the focused browser checker are in `/tmp/video-use-imessage-release-20261007/`.

## Live release

Published at https://video-use.insforge.site/#imessage from source `96e6dde1dc679b927ef780f94f526c85cd5c4631`. InsForge deployment `c4e11648-39e2-4a73-89a6-955d1ac64219` reached READY at 2026-10-07 07:13:20 UTC; provider deployment `dpl_cy24haYmzJWsKZD12iDcGKvHhS8v`. The release branch is `feature/useful-video-library` on the user's fork.

Live Chromium and WebKit checks pass at 1440 and 390px for uncropped screenshots, original image hashes, keyboard/tap full-size links, seven sectors, placement, no overflow, actual mist animation and reduced motion. All visible videos advance through the three collection stops and resume at the featured row, without preview controls or page errors. All six public routes return HTTP 200. The deployment receipt and live evidence are in `/tmp/video-use-imessage-release-20261007/`.

## Orange launch badge

Added a centered NEW! badge above the iMessage heading at the user’s request. `ImessageFeature` renders a decorative sparkle beside the text; its CSS uses Browser Use orange, a warm gradient, bold italic Space Grotesk, a slight tilt, a soft glow and a periodic shimmer. Reduced motion disables the shimmer. The Messages icon and both original conversation screenshots remain in place.

Production build and lint pass. The local production build temporarily disabled the webpack disk cache after the machine ran out of space, then restored the original Next configuration byte for byte. Chromium at 1440/1024/390/320px verifies centered placement above the heading, no overflow, the two phones, and reduced-motion behavior. Evidence: `/tmp/video-use-imessage-new-20261007/`.
