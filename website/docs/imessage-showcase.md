# Video Use in iMessage

## Placement and design

The requested section sits between the featured workflow carousel and the Video Editing preview. It is the seventh homepage content sector once its assets are supplied. Filtered root URLs and the collection/library pages do not show this promotion.

The desktop layout is one symmetrical composition. The phones lean inward into a shallow V, with the title and two descriptions centered between them. Each description aligns with its respective phone: camera-roll editing on the left, reference-guided creation on the right. This replaces the initial two-row layout following the user's request to reduce its height. Below 1024px, the phones remain side by side, with the title above and the two context columns beneath. Open page background, a subtle warm glow, restrained pill labels, Space Grotesk headings, Inter body copy, and Browser Use orange connect the feature to the existing site.

`ImessageFeature` owns the shared grid. Its internal `ConversationPhone` accepts a left/right position; the CSS module applies mirrored rotation and perspective while keeping each screenshot and its frame together. The desktop tilt is 10 degrees, with gentler 8-degree tilt on smaller screens. Screenshots preserve their full aspect ratio. The frame is the unmodified `phone.png` used above Send at https://family.co/. Its source and hash are recorded in `public/imessage/asset-sources.json`.

The phone stages have a warm Browser Use orange halo and a blurred mist layer behind the devices. `mistDrift` gently translates, rotates and fades the mist over a 16-second alternating cycle; the two sides have offset timing. Both layers are decorative CSS pseudo-elements with no pointer interaction or effect on layout height. Reduced motion keeps the orange glow but stops the decorative animation. Video preview playback remains independent.

The copy describes selected clips shared from Photos. The current messaging implementation can inspect and edit those assets, search public references, and create original videos. It does not have unrestricted private camera-roll access, so the promotion does not claim that capability. No new public onboarding destination or phone number has been invented.

## Pending screenshots

The user will provide two local paths:

1. Camera-roll footage and editing conversation.
2. Video creation and web-reference conversation.

Both values in `data/imessage-conversations.json` are currently `null`. Each final value must contain `src`, the image's natural `width` and `height`, and a descriptive `alt`. Store the supplied images in `public/imessage/` and record their provenance alongside the frame. Inspect each screenshot and its status-bar alignment in the phone at desktop and phone sizes before publishing.

Development builds show neutral labeled screen placeholders while those assets are missing. Production omits the entire feature until both images are configured. The incomplete draft has not been deployed. After supplying the assets, remove the draft fallback, update the homepage sector counts, build, and verify the final screenshots before release.

## Verification

The initial draft passed the production build, TypeScript/catalog validation, all 30 importer checks, lint, and responsive layout/playback checks. Evidence for that superseded two-row layout is stored in `/tmp/video-use-imessage-20261007/qa/`.

The new module does not change `PreviewMedia`, the headless playback provider, the 172-film catalog, or any media URL. Actual scrolling playback is checked separately; screenshots of the chat feature are intentionally static images, while the existing video containers remain muted autoplay loops with no Play/Pause control.

The compact revision measures about 684px tall at 1440px, compared with roughly 1830px for the original. Its layout checks cover symmetric phone geometry, separation of text and phones, uncropped device frames, balanced heading wraps, unchanged placement above Editing, and absence of horizontal overflow. Fresh screenshots and the final browser checks are stored in `/tmp/video-use-imessage-compact-20261007/qa/`.

The production build, TypeScript/catalog checks, 30 importer checks, lint and diff checks pass. Chromium layout checks pass at 1440, 1280, 1024, 1023, 768, 540, 390 and 320px; desktop and phone screenshots were reviewed in Chromium and WebKit. Both engines confirm real playback in every visible Editing preview after scrolling through the promotion, and the featured video resumes on return. One clip stalled at time zero in the first combined WebKit run; a clean focused run passed all ten desktop clips and all six phone clips without changing playback code. The feature remains a local draft awaiting the two real screenshots.

The orange mist pass is verified in Chromium at 1440, 390 and 320px and WebKit at 1440 and 390px. Animation timelines and successive rendered screenshots confirm actual motion; reduced-motion mode removes the mist animations while retaining the halo. Device placement and section height stay intact, with no horizontal overflow. WebKit reports empty computed animated pseudo-element transforms, so motion verification uses the animation timeline and rendered pixel differences. Its phone height is compared with the existing WebKit baseline rather than Chromium's font metrics. Evidence is in `/tmp/video-use-imessage-mist-20261007/qa/`.
