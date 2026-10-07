# Video Use in iMessage

## Placement and design

The requested section sits between the featured workflow carousel and the Video Editing preview. It is the seventh homepage content sector once its assets are supplied. Filtered root URLs and the collection/library pages do not show this promotion.

The desktop layout follows the supplied Opal screenshot: phone on the left and context on the right, then context on the left and phone on the right. The phones face directly forward as explicitly requested. Below 768px, each phone precedes its associated context in a single column. Open page background, a subtle warm glow, restrained pill labels, Space Grotesk headings, Inter body copy, and Browser Use orange connect the feature to the existing site.

`ImessageFeature` owns the two rows. Its internal `ConversationPhone` fits each real screenshot inside the transparent frame without cropping or adding invented messages. The frame is the unmodified `phone.png` used above Send at https://family.co/. Its source and hash are recorded in `public/imessage/asset-sources.json`.

The copy describes selected clips shared from Photos. The current messaging implementation can inspect and edit those assets, search public references, and create original videos. It does not have unrestricted private camera-roll access, so the promotion does not claim that capability. No new public onboarding destination or phone number has been invented.

## Pending screenshots

The user will provide two local paths:

1. Camera-roll footage and editing conversation.
2. Video creation and web-reference conversation.

Both values in `data/imessage-conversations.json` are currently `null`. Each final value must contain `src`, the image's natural `width` and `height`, and a descriptive `alt`. Store the supplied images in `public/imessage/` and record their provenance alongside the frame. Inspect each screenshot and its status-bar alignment in the phone at desktop and phone sizes before publishing.

Development builds show neutral labeled screen placeholders while those assets are missing. Production omits the entire feature until both images are configured. The incomplete draft has not been deployed. After supplying the assets, remove the draft fallback, update the homepage sector counts, build, and verify the final screenshots before release.

## Verification

The draft has passed the production build, TypeScript/catalog validation, all 30 importer checks, and lint. Isolated Chromium layout checks at 1440, 1024, 768, 390 and 320px verify its position between the carousel and Editing, the alternating desktop rows, stacked phone layout, successfully loaded frames, and absence of horizontal overflow or page errors. Desktop and phone screenshots were visually inspected. Evidence is stored in `/tmp/video-use-imessage-20261007/qa/`.

The new module does not change `PreviewMedia`, the headless playback provider, the 172-film catalog, or any media URL. Actual scrolling playback is checked separately; screenshots of the chat feature are intentionally static images, while the existing video containers remain muted autoplay loops with no Play/Pause control.

The scrolling regression passed in Chromium and WebKit at 1440 and 390px. It measures real frame advancement in every visible clip at the top of all three collections, confirms the featured video resumes on return, and verifies muted inline autoplay, native looping, and absent playback controls. Both engines report no page errors. See `qa/playback.json` in the evidence directory.
