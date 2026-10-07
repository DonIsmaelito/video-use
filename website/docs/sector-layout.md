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

The homepage has **six content sectors**: featured workflows, Video Editing, the MCP connections promotion, Video Creation, the Dots-style MCP promotion, and 3D Animations & Visuals. Including the announcement strip, navigation, and footer gives **nine vertical modules** while the announcement is visible.

The three clip sectors each show up to sixteen curated examples, preserve their natural aspect ratios, and end at a finite height. A fade returns the grid to the page background with a centered orange View all action. Any card whose controls fall below the usable preview edge is inert and hidden from assistive technology. The entire catalog remains available on the destination pages.

| Collection | Classification | Initial count | Route |
| --- | --- | --- | --- |
| Video Editing | Existing footage edited into clips, stories, demos or highlights | 82 | `/video-editing` |
| Video Creation | Original motion design and explainers | 56 | `/video-creation` |
| 3D Animations & Visuals | 3D objects, materials, product animation and miniature worlds | 29 | `/3d-visuals` |
| Complete library | Both collections | 167 | `/library` |

Counts derive from `examples.json` through the existing enrichment helpers. The production technique determines membership, because five older footage edits carry a legacy Video Creation category. Source records, executed prompts, media URLs, and stable IDs are not rewritten to change the browsing hierarchy.

`lib/sectors.ts` defines copy, membership and preview selection. The third collection uses the existing `3d` technique, leaving each clip in exactly one collection. `McpDots` adds original CSS characters, a warm glow, and a fading dot texture between Video Creation and 3D; its CTA opens the existing connection dialog. The earlier connector showcase remains between Editing and Creation. `GallerySector` implements the bounded preview, `CollectionPage` supplies the destination hero and navigation, and `Gallery` reuses filtering, copying, URL state, and `DemoDetail`. `facetOptions` accepts a source collection so filter choices and counts stay relevant. Root example links and old root filter URLs remain supported.

Space Grotesk is hosted locally for headings, hero labels and card titles; Inter remains the interface font. Section titles and actions use Browser Use orange `#fe750e`. Featured card widths remain 512/400/312px with 20px gaps. The masonry grid uses 8px gaps and 16px corners.

`npm run check` includes exhaustive/disjoint collection coverage, preview membership, scoped search and facets, and the five legacy classifications alongside existing catalog, prompt and importer validation.

## Initial two-collection verification

The production build, TypeScript/catalog checks, 30 importer tests, lint, formatting and diff checks pass. An isolated local Chromium run checked homepage and all three collection/library routes at 1440, 1024, 768, 390 and 320px: correct clip counts, no horizontal overflow, no overlapping cards, and inert clipped preview cards. Desktop interactions passed for View all navigation, scoped search, reload, filters, empty states, reset, exact prompt copying, dialog Back navigation, and legacy root links. Final phone runs at 390 and 320px passed View all, opening a player by tapping exposed media, exact prompt copying and closing.

Visual review covered desktop and phone homepage sectors, both destination heroes, and a 320px player dialog. The final refinement reduced the desktop hero title to 56px and phone titles to 28–36px, shortened contextual copy, and kept the two phone hero actions beside one another when space allows. The reference count comes from Higgsfield's markup; the browser checks described here cover the local Video Use implementation.

## Three-collection extension

The user requested a third 3D collection and a Dots-style MCP interlude before deployment. The third collection has its own hero, search, contextual facets, metadata and navigation. The new promotion follows the reference banner composition using original CSS characters and Browser Use colors. It advertises the existing Video Use MCP connection, without claiming a separate Dots integration. The desktop reference banner was inspected in isolated Chromium with JavaScript disabled because hydration removed that server-rendered promotion; the structural sector count remains grounded in public markup.


The final three-collection build passes TypeScript/catalog and disjoint-collection checks,30 importer tests, full lint, formatting, and diff checks. Browser verification covers all five browsing routes at1440/1024/768/390/320px, plus production-build checks at1440/390/320px. All167 clips are accounted for, with no horizontal overflow, overlapping cards, or page errors. View all, scoped search and filters, legacy links, exact prompt copying, player opening/closing, and the Dots promo connection dialog pass. The promo was also inspected at820px; touch navigation to3D and exact prompt copy pass at390/320px. Evidence is in /tmp/video-use-higgsfield-study-20261006/qa-three/ and qa-production/.
