# Homepage sectors and collection pages

Reference inspected on 2026-10-06: https://higgsfield.ai/ and https://higgsfield.ai/higgsfield-genjutsu-presets.

A sector is a complete vertical module separated from the next by exposed page background. Cards in one horizontal row count together. A header and its associated gallery count together. Desktop/mobile variants of the same module count once.

## Reference count

The public desktop HTML and CSS describe **10 content sectors**, or **12 including the global header and footer**:

1. Featured product carousel.
2. Discount promotion and product shortcut tiles, sharing one desktop row.
3. AI Influencer promotion.
4. Global Film Festival hero, submissions and action.
5. ChatGPT / MCP promotion.
6. Visual Effects preview, cropped with a gradient and View all presets.
7. Genjutsu feature and preset preview, with its own View all action.
8. Seedance preview with its own View all action.
9. Community project breakdown previews and Explore community.
10. Supercomputer promotion.

Mobile hides some promotions and swaps the Genjutsu presentation, so this is a desktop structural count, not a claim that every viewport shows twelve modules. The connected browser was unavailable during the reference study; the count is grounded in the public markup, visibility classes, and stylesheet rather than measured screenshot boundaries.

The Genjutsu destination consists of an introductory hero, collection tabs, and an uncropped masonry gallery. This is the reference for our dedicated collection pages.

## Video Use implementation

The homepage has **eight content sectors**: featured workflows, agent shortcuts with a blank showcase panel, Video Use in iMessage, Video Editing, the MCP connections promotion, Video Creation, the Dots-style MCP promotion, and 3D Animations & Visuals. Including the announcement strip, navigation, and footer gives **eleven vertical modules** while the announcement is visible.

The three clip sectors each show up to sixteen curated examples, preserve their natural aspect ratios, and end at a finite height. A fade returns the grid to the page background with a centered white View More action. Any card whose controls fall below the usable preview edge is inert and hidden from assistive technology. The entire catalog remains available on the destination pages.

| Collection | Classification | Initial count | Route |
| --- | --- | --- | --- |
| Video Editing | Existing footage edited into clips, stories, demos or highlights | 82 | `/video-editing` |
| Video Creation | Original motion design and explainers | 56 | `/video-creation` |
| 3D Animations & Visuals | 3D objects, materials, product animation and miniature worlds | 29 | `/3d-visuals` |
| Complete library | All three collections | 167 | `/library` |

Counts derive from `examples.json` through the existing enrichment helpers. The production technique determines membership, because five older footage edits carry a legacy Video Creation category. Source records, executed prompts, media URLs, and stable IDs are not rewritten to change the browsing hierarchy.

`lib/sectors.ts` defines copy, membership and preview selection. The third collection uses the existing `3d` technique, leaving each clip in exactly one collection. `McpDots` adds original SVG characters, a pearl glow, and a fading dot texture between Video Creation and 3D; its CTA opens the existing connection dialog. The earlier connector showcase remains between Editing and Creation. `GallerySector` implements the bounded preview, `CollectionPage` supplies the destination hero and navigation, and `Gallery` reuses filtering, copying, URL state, and `DemoDetail`. `facetOptions` accepts a source collection so filter choices and counts stay relevant. Root example links and old root filter URLs remain supported.

Space Grotesk is hosted locally for headings, hero labels and card titles; Inter remains the interface font. Section titles use Browser Use orange `#fe750e`; primary actions are white. Featured card widths remain 512/400/312px with 20px gaps. The masonry grid uses 8px gaps and 16px corners.

`npm run check` includes exhaustive/disjoint collection coverage, preview membership, scoped search and facets, and the five legacy classifications alongside existing catalog, prompt and importer validation.

## Initial two-collection verification

The production build, TypeScript/catalog checks, 30 importer tests, lint, formatting and diff checks pass. An isolated local Chromium run checked homepage and all three collection/library routes at 1440, 1024, 768, 390 and 320px: correct clip counts, no horizontal overflow, no overlapping cards, and inert clipped preview cards. Desktop interactions passed for View all navigation, scoped search, reload, filters, empty states, reset, exact prompt copying, dialog Back navigation, and legacy root links. Final phone runs at 390 and 320px passed View all, opening a player by tapping exposed media, exact prompt copying and closing.

Visual review covered desktop and phone homepage sectors, both destination heroes, and a 320px player dialog. The final refinement reduced the desktop hero title to 56px and phone titles to 28–36px, shortened contextual copy, and kept the two phone hero actions beside one another when space allows. The reference count comes from Higgsfield's markup; the browser checks described here cover the local Video Use implementation.

## Three-collection extension

The user requested a third 3D collection and a Dots-style MCP interlude before deployment. The third collection has its own hero, search, contextual facets, metadata and navigation. The new promotion follows the reference banner composition using original CSS characters and Browser Use colors. It advertises the existing Video Use MCP connection, without claiming a separate Dots integration. The desktop reference banner was inspected in isolated Chromium with JavaScript disabled because hydration removed that server-rendered promotion; the structural sector count remains grounded in public markup.


The final three-collection build passes TypeScript/catalog and disjoint-collection checks,30 importer tests, full lint, formatting, and diff checks. Browser verification covers all five browsing routes at1440/1024/768/390/320px, plus production-build checks at1440/390/320px. All167 clips are accounted for, with no horizontal overflow, overlapping cards, or page errors. View all, scoped search and filters, legacy links, exact prompt copying, player opening/closing, and the Dots promo connection dialog pass. The promo was also inspected at820px; touch navigation to3D and exact prompt copy pass at390/320px. Evidence is in /tmp/video-use-higgsfield-study-20261006/qa-three/ and qa-production/.

## Live release

Published at https://video-use.insforge.site in InsForge deployment `92b3a5a3-60ca-4f62-aa4d-eb743957cf1b` from source `6f207c3`. Live checks pass for all five browsing routes at1440/390/320px, the MCP connection CTA and copy action, and actual phone navigation/player/prompt-copy controls. All six public routes return200 and the hosted font matches its source hash.


## Preview playback and promotion second pass

The user reported still previews in Arc. Clean Chromium and WebKit sessions could play the existing media, so the exact Arc failure was not reproduced. The prior reduced-motion layout checks intentionally suppressed previews and did not establish frame advancement. `PreviewMedia` now declares native muted inline autoplay, sets default and live mute state before play, resumes on visibility/page restoration, and reports autoplay rejections. `PreviewPlaybackProvider` shares an explicit Play/Pause choice across collection routes and retries inside a trusted user gesture. Reduced motion still starts quietly, with an explicit Play option.

The revised Dots-style promotion uses original SVG mascots with distinct silhouettes and accessories, a pearl character inside the white heading, tighter character placement, pill labels and outlined cursors. Soft pearl lighting, lower dots and an orange beveled CTA bring the composition closer to the inspected reference. Phone layouts place the characters in two columns beneath the copy. No new package or external asset is required.

Production build, TypeScript/catalog validation, 30 importer tests, lint, formatting and diff checks pass. The saved `scripts/check-preview-playback.py` verifies actual video time advancing in Chromium and WebKit at 1440 and 390px, all three sectors, scroll return, shared Play/Pause, modal pause/resume, the pageshow handler, route navigation, reduced motion and simulated autoplay rejection. Nine viewport layouts pass overflow and mascot/copy separation checks; production screenshots and MCP/detail dialogs pass at 1440, 390 and 320px. The phone click harness was corrected to target exposed footage instead of the separate Copy Prompt button. Evidence: `/tmp/video-use-playback-dots-20261007/`.

This UI pass builds on the newer reviewed-media release `417da51` and preserves every catalog/source/media manifest byte for byte from that version.


Published the playback/promo follow-up at https://video-use.insforge.site in deployment `dcf05104-8173-4b30-9785-57e0067e5630` from source `bd19563`. Live Chromium and WebKit pass actual playback and recovery checks at 1440/390px. Header/promo layouts and MCP/detail dialogs pass at 1440/390/320px. All six routes return 200, every current video URL appears in the published client bundle, and the hosted Space Grotesk file matches its source. The user's Arc session was unavailable for direct inspection. Final receipt: `/tmp/video-use-playback-dots-20261007/release-summary.json`.


## Automatic looping previews

The user explicitly requested continuously playing videos inside every visible clip container, with no Play/Pause control. This supersedes the earlier shared-toggle behavior. `PreviewMedia` always enables muted inline autoplay and native looping when a container is visible. Reduced motion no longer turns clip previews into still posters; it continues to govern decorative CSS motion. Hidden tabs, offscreen clips and covered background videos can pause automatically and resume when visible again. `PreviewPlaybackProvider` is now headless and retries a browser rejection during ordinary trusted interactions, without exposing a control or storing a playback preference.

This pass starts from the latest 172-film release `c258c2e`, preserving its catalog, original prompts, source records and all media URLs. The three collections contain 82 editing clips, 61 creations and 29 3D visuals.


The production build, TypeScript/catalog checks, 30 importer tests, lint, formatting and diff checks pass. Chromium and WebKit at 1440/390px verify all eight featured clips, every visible container at both ends of each homepage sector, all collection/library/MCP routes, scroll return, dialog suspension/resumption, page restoration, autoplay with reduced motion and recovery during ordinary interaction. Each engine also observes two uninterrupted native loop boundaries on a visible clip. An initial test forced repeated end seeks and stalled in Chromium; the corrected check watches complete natural loops without altering playback time. Phone/header checks at 1440/390/320px confirm no playback control, no overflow and a working MCP dialog. Evidence: `/tmp/video-use-continuous-previews-20261007/`.


Published automatic looping at https://video-use.insforge.site in deployment `05eb89e9-9804-4a72-8658-85b96c122cd7` from source `ec23407`. Live Chromium and WebKit repeat the complete 1440/390px playback suite, including every visible homepage container, all eight featured clips, all browsing routes, reduced-motion autoplay, normal-interaction recovery and two uninterrupted native loops. Header/MCP checks pass at 1440/390/320px. All six routes return 200 and all 172 current video URLs appear in the published bundle. The Play/Pause preview control is absent. Final receipt: `/tmp/video-use-continuous-previews-20261007/release-summary.json`.


## Agent shortcuts and MCP command box

The agent row follows Higgsfield’s large left panel / six compact right cards, visually inspected in Chromium on 2026-10-07. Its left panel is deliberately blank pending a film. The six cards are ChatGPT, Claude, Cursor, OpenClaw, Nous Research’s Hermes, and the user-selected Your agent. The first three open the appropriate existing connection guide; the last three select and scroll to their setup in the lower MCP promotion. That promotion remains after Video Editing and now includes copyable Claude Code, OpenClaw and Hermes commands plus a generic remote MCP URL. Official syntax sources and scope are in `agent-showcase.md`.

The iMessage heading now pairs its name with a green Messages-style icon; the “A conversation away” eyebrow is removed. The Dots banner grows symmetrically between Creation and 3D, with tighter adjacent margins, larger type, artwork and action. Solid white cursor pointers are anchored directly to each sculpture and mirrored on the right.
