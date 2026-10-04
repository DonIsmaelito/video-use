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


## Sidebar and header follow-up — 2026-10-04

The user explicitly requested the left category/facet sidebar back, integrated with the refreshed gallery, without a Filters button. They also requested removal of the Library and MCP links from the top navigation. This pass owns `components/gallery.tsx`, `components/site-header.tsx`, its MCP page call site, and `app/globals.css` in the main checkout. Preserve the library branch’s prompt labels, source descriptions, and newest media manifests when deploying. The completion receipt is recorded below in both checkouts.


### Implementation ready — deployment running

The sidebar/header follow-up is implemented in the main checkout. `gallery.tsx` removes `showFilters` and the global Filters button, with the Video type / Audience / Use case sidebar always present. `globals.css` restores a slim sticky left column on desktop and visible stacked controls on phones, retaining the existing white/gray/purple design. The responsive grid now accounts for the sidebar width. `site-header.tsx` removes the Library and MCP navigation links and unused props; `app/mcp/page.tsx` uses the simplified header. `README.md` documents this behavior. The original/starter prompt labels and source descriptions from the library integration are retained.

Production build, TypeScript, gallery checks (93 examples), lint, and browser checks at 320 / 390 / 768 / 1024 / 1440 pixels passed. Browser checks cover the visible sidebar, absence of a Filters button, header removal, filters, search, reset, URL reload, MCP connection, and zero overflow or page errors. Evidence: `/tmp/video-use-ui-qa/sidebar-local-result.json`. The deployed catalog is the committed `f59f7db` checkpoint; newer uncommitted data in the library checkout remains untouched. Before another library-branch deployment, integrate this follow-up’s five changed source/documentation files from the main checkout. Do not overwrite either checkout’s newer catalog.


### Deployment verified

Deployment `7ba26090-203a-49b6-b6e8-bfbc205bc617` is READY on the existing Video-use site project. Live at https://video-use.insforge.site with the committed 93-example catalog. Live browser checks passed at 320, 390, 768, 1024, and 1440 pixels: sidebar placement, no Filters button, no Library/MCP header links, filter/reset/search/deep-link behavior, MCP connection, mobile touch selection and scrolling, zero horizontal overflow, and zero page errors. Evidence: `/tmp/video-use-ui-qa/sidebar-live-result.json`. No backend/schema changes were needed in this follow-up.


### Library branch sidebar integration

The verified sidebar/header follow-up is now copied into `feature/useful-video-library`: `components/gallery.tsx`, `components/site-header.tsx`, `app/mcp/page.tsx`, `app/globals.css`, and `README.md`. The newer catalog at `002c41c` (98 examples) and all media/provenance manifests remain authoritative and were not copied from the original checkout. Original/Starter prompt labels, source descriptions, and the visible Video type label are preserved. This integration changes no backend schema or environment configuration. Production build and release verification are recorded separately in the campaign deployment receipt.


### Use case always visible — completed

The user requested that Use case always be shown. This pass in the main checkout makes it a static expanded sidebar section rather than a collapsible disclosure. Audience keeps its current disclosure behavior. The current 108-example catalog and opening-card/loop changes from `8e2c41c` have been brought into the main checkout before deployment. The change owns `components/gallery.tsx`, small shared-stylesheet additions, and the README. The final source changes will also be applied to the library checkout if those files remain unchanged.


Use case is now a permanent `<section>` in `gallery.tsx`, with no collapse button. The existing selection counts, URL state, and reset behavior are unchanged. `globals.css` styles the section consistently with Audience, including the existing scrollable option list on phones. The three edited files (`gallery.tsx`, `globals.css`, and README) were copied into the library checkout only after verifying each still matched the committed `8e2c41c` version. Its catalog and unrelated work were untouched. Build, typecheck, lint, and local desktop/mobile verification passed for all 108 examples. Evidence: `/tmp/video-use-ui-qa/use-case-local-result.json`. Deployment is in progress.


Use case deployment `84d20679-d3f7-4122-8d29-30aa8d6c6ade` is READY and verified at https://video-use.insforge.site. Desktop and mobile checks confirm the expanded section, absence of a collapse button, all 64 use-case options in the rendered list, selection/reload/reset behavior, independence from the Audience disclosure, and no page errors or horizontal overflow. The complete 108-example catalog is preserved. Evidence: `/tmp/video-use-ui-qa/use-case-live-result.json`.


### GitHub star badge — in progress

The user requested a compact dark rounded GitHub badge matching their reference, showing this repository’s real star count. This pass owns `components/site-header.tsx`, the header styles in `app/globals.css`, a new server-only GitHub metadata helper, and README notes. Preserve the expanded Use case section and current 108-example catalog. The helper will use GitHub’s public metadata endpoint with hourly Next.js caching; no credentials or backend schema changes are required.


### Library branch Use case integration

The completed three-file change is now reviewed in `feature/useful-video-library`. Use case remains a static labeled section on desktop and mobile; Audience still has its own disclosure. The existing prompt labels, context handoff, loop metadata, opening cards, and authoritative media manifests are unchanged. TypeScript, gallery validation (108 examples), and lint pass. The live deployment and desktop/mobile filter, reload, reset, and layout evidence are the `84d20679-d3f7-4122-8d29-30aa8d6c6ade` receipt above. This integration requires no backend or environment changes and does not trigger a competing deployment; the next library release will include the newer reviewed catalog after its data freeze.
