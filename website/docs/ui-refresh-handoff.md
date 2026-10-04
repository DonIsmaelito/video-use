# Gallery UI refresh — 2026-10-03

Active implementation checkout: `/Users/ismaelito/Developer/video-use`.
Website baseline imported from `feature/useful-video-library` at `f51ed4c` so today's reviewed videos, MCP page, connection guides, source links, square playback, filters and shareable URLs survive the redesign.

The requested design uses three featured films directly below the header, with the reviewed MCP launch first; tall gallery containers; Copy Prompt, expand and persistent likes; black/white/gray surfaces with occasional purple accents; and less supporting copy.

Cleanup coordination: the refresh owns `website/components/gallery.tsx`, `preview-media.tsx`, `site-header.tsx`, featured cards, `app/page.tsx`, the shared stylesheet and the new likes API. Keep the newer library data and source provenance. Before another deployment from the library checkout, carry over this UI work so an older source tree does not replace it.

Playback must stay muted inline, pause offscreen/when a dialog opens, respect reduced motion, and preserve complete video frames. Prompts keep the existing chat context and source links. Likes are real, begin at zero, and are limited to one per example per browser identity.

The implementation includes content updates through `0a8ed68`: 85 examples plus the revised 28-second MCP connection film. This is the deployment content checkpoint.

Implemented:
- Three wide, autoplaying hero films directly below a compact header.
- One continuous tall-card gallery with original-frame video over a blurred poster; responsive grids and a swipeable mobile featured row.
- Purple Copy Prompt actions that turn white on hover, heart counts, and separate expand buttons. Touch controls stay visible.
- Neutral black/white/gray surfaces, white icons, occasional purple accents. Removed the large text hero, redundant banner, repeated category headings, helper strip, and unused Hero/GettingStarted/Hint components.
- Existing search, categories, optional audience/use-case/type filters, deep links, full chat prompt handoff, source disclosures, MCP page and connection guides remain.
- Server-only likes API uses a signed anonymous browser cookie and a hashed database identity. Explicit desired state plus a unique key makes retries idempotent. Table/RPC access is denied to anon/authenticated clients. No synthetic likes were added.

Validation:
- TypeScript, existing gallery checks, lint and production build pass.
- Desktop/mobile browser flows passed copy-content checks, like/reload/unlike, dialog deep links, category/search/facet/reset, MCP setup, and reduced motion. Thirteen visible videos played concurrently; opening dialogs paused background previews.
- Backend tests passed separate-browser counts, concurrent duplicate writes, unlike, invalid payloads and foreign-origin rejection. Test likes were removed.
- Read/write/RPC denial for public clients was checked on both the isolated test branch and parent. The temporary backend branch was deleted after successful merge.
- Browser-facing Host is used for origin validation because Next may normalize request.url on local/proxied requests. Keep this behavior.
- Browser bundles were checked for server credentials; none were present.

Deployment `553b826f-e9ce-4e1c-966c-6338be5f61ff` is READY on the existing Video-use site InsForge project. Production URL: https://video-use.insforge.site (provider URL: https://c6t3b5eb.insforge.site). Live verification passed on both desktop and mobile: 85 cards, three featured films, revised MCP media, correct clipboard prompt, like/reload/unlike persistence, MCP page, zero page/console errors and no horizontal overflow. The production test vote was removed.


## Integration into the library branch

The verified refresh was selectively integrated into `feature/useful-video-library`, preserving that branch’s newer example and media manifests. The source migration is retained for reproducibility; integration does not reapply backend changes. The library copy restores the visible Original prompt / Starter prompt label and exposes the example description inside Details & sources.

Independent live checks of deployment `553b826f-e9ce-4e1c-966c-6338be5f61ff` passed for 85 examples and the 28-second MCP film: fully painted desktop/mobile previews, complete video frames, clipboard content, like/reload/unlike with the test vote removed, keyboard focus restoration, background pause, reduced motion, source/review links, Video type filtering and no page errors or horizontal overflow. Evidence: `/private/tmp/video-use-library-ui-integration-live-qa/result.json`.
