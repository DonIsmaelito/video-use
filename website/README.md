# Video Use website

The public example library and MCP landing page for the open-source [Video Use toolkit](https://github.com/browser-use/video-use).

Live site: https://video-use.insforge.site

## Run locally

Requires Node 22.13 or newer. The app uses Next.js 16, React 19, TypeScript, and Tailwind CSS 4.

```sh
cd website
npm ci
npm run dev
```

The server prints its local URL. For verification:

```sh
npm run check
npm run lint
npm run build
```

Set `SITE_URL` to the public origin when building a different deployment. The site is hosted by the **Video-use site** InsForge project, separate from the MCP backend project. Follow that project's existing hosting configuration; this is not a Vite app and does not use a Sites build plugin.

The production build explicitly uses Next.js's webpack builder, matching the locally verified CSS pipeline. After publishing, check the rendered homepage and `/mcp`; a successful build alone does not verify the hosted styles or media.

For playback changes, `python3 scripts/check-preview-playback.py http://localhost:3000` measures actual video time advancing in every visible container in Chromium and WebKit at desktop and phone widths. It checks all featured clips, both ends of each homepage sector, two native loop boundaries, scroll resumption, dialogs, page restoration, collection/library/MCP routes, autoplay with reduced motion and recovery from a simulated autoplay rejection during normal interaction. It also verifies the absence of preview playback controls. This optional browser check requires Python Playwright and its Chromium/WebKit browsers; use `--browser chromium` or `--chromium-executable /path/to/chromium` when needed, and `--output report.json` to save evidence.

## Routes and components

- `app/page.tsx` assembles a homepage with seven content modules: featured films, Video Use in iMessage, a Video Editing preview, MCP connections, a Video Creation preview, the Dots-style MCP promotion, and a 3D Animations & Visuals preview. Each gallery fades into the page background with a View all link at its lower edge.
- `app/video-editing/page.tsx`, `app/video-creation/page.tsx`, `app/3d-visuals/page.tsx`, and `app/library/page.tsx` use `CollectionPage` for introductory copy, collection navigation, and the complete searchable gallery. The 82 footage edits, 61 motion/explainer examples, and 29 3D visuals form three disjoint collections. Counts derive from the current catalog.
- `lib/sectors.ts` owns the three collections, their copy, and curated previews. It classifies by production technique; the five legacy records named Video Creation are edits of existing footage, so they belong to Video Editing. The original records, prompts, and media stay intact.
- `components/gallery-sector.tsx` bounds each homepage preview. Cards clipped by the fade are inert and absent from the accessibility tree; keyboard users reach the View all link without tabbing through invisible controls.
- `components/collection-page.module.css` and `gallery-library.module.css` provide centered desktop / left-aligned mobile heroes and a full-width library, with search and optional filters above the videos.
- `app/mcp/page.tsx` and its CSS module provide the centered MCP landing page, launch film, three-step flow, client setup cards, copyable starter prompts, and FAQs.
- `components/site-header.tsx` and `wordmark.tsx` provide the shared navigation and open-source links. The header's small “by Browser Use” credit glows slowly and stays still for reduced motion.
- `components/gallery.tsx` handles homepage previews and collection-scoped browsing, audience/use-case/video-type/category filters, search, clipboard feedback, deep links, and the detail dialog. Video type keeps the internal `technique` data key and URL parameter. Legacy root filter links still open the full filtered library, and root example links still open their dialog.
- `components/demo-detail.tsx` renders the minimal demo dialog: a player sized for the video shape, category and title, a borderless scrollable full prompt, an orange Copy Prompt action and the compact Connect your chat control. Its CSS module keeps the actions visible while long prompts scroll, with a stacked phone layout. Source/project links and required media credits live in a small Sources disclosure; prompt bytes, native playback and clipboard fallbacks are preserved.
- `components/masonry-gallery.tsx` packs cards into Higgsfield-style columns with 8px gaps and 16px corners, using two columns on phones, three from 1024px and four from 1280px. Each new card sits in the shortest column; `ResizeObserver` recalculates positions when widths or content change, while DOM order and video elements stay stable. `gallery-cards.module.css` preserves natural 16:9, 9:16 and square previews without a separate footer. Hover or keyboard focus reveals a large centered title and compact orange-tinted Copy Prompt button over a soft dark scrim; the controls remain visible on touch. Clicking the video outside the copy button opens its player and prompt without a separate expand button. A regular responsive grid is the no-JavaScript fallback.
- `components/preview-media.tsx` loads media near the viewport and automatically loops every visible, muted preview without a Play/Pause control. It declares native inline autoplay and sets both default and live mute state before playback. Visible video playback is always enabled, including when reduced motion is set, as explicitly requested for the clip containers. Previews pause in hidden tabs and under dialogs, then resume on visibility/page restoration. The headless `preview-playback.tsx` retries browser autoplay rejections during normal trusted clicks or keypresses. Gallery cards preserve the full video in its matching shape, without a blurred backdrop; featured films remain wide, with optional ambient fill behind a portrait film so its foreground remains uncropped.
- `components/connect-mcp.tsx` provides copyable setup URLs and separate ChatGPT, Claude, Cursor, and local-source instructions. Official client artwork lives in `public/clients`, with its provenance in `brand-sources.json`; compatible clients are not presented as end-to-end tested.
- `components/ui/disclosure.tsx` uses Base UI for optional filters and source details. `technique-icon.tsx` gives each video type a consistent icon.
- `components/mcp-feature.tsx` leads the fixed hero order: Video Use MCP, Product Launches, then Movie Edit. Each title has a short promotional description beneath it, without a caption arrow. `data/featured-workflows.json` maps the six library-backed feature cards to reviewed examples, use-case titles, concise descriptions and fit modes. Movie Edit previews the existing Whiplash film with a cover crop that fills its tile; the full player preserves the entire frame. Its gallery title, prompt and source records stay separate from the hero caption. `featured-film.tsx` shares an accessible full-film dialog for the product and MCP films; opening it pauses background previews. `mcp-launch.tsx` places the 11.6-second MCP loop on the MCP page. The media manifest opts its full player into looping; Product Launches retains normal playback.
- `components/featured-carousel.tsx` places eight films in a horizontal rail: Video Use MCP, Product Launches, Movie Edit, Sports Highlights, Venue Reels, Podcast Clips, Demo Highlights and Mini Docs. The five footage-led edits also open in the regular player/prompt dialog and remain discoverable in the gallery. They replace the rejected original studies; historical source records and immutable releases remain available. Catalog validation prevents a feature from pointing at an unpublished example. Its CSS module follows Higgsfield's fixed 512px desktop / 400px tablet / 312px mobile cards, 20px gaps, 8px corners and edge-mounted arrows. Small phones narrow the card to preserve a peek. Native scroll snapping settles touch/trackpad swipes on card edges; mouse drags, arrow controls and keyboard navigation use the same stops, honor reduced motion and never auto-advance.
- `components/imessage-feature.tsx` stages a compact homepage section immediately after the featured carousel and before Video Editing. Two phones tilt inward into a shallow V around a centered title and two context columns about shared camera-roll footage and web references. On smaller screens the phones stay side by side, with the title above and their respective context beneath. The section uses Family's unmodified phone frame, the site's fonts, and Browser Use orange. `data/imessage-conversations.json` maps the user's editing screenshot to the left phone and the reference conversation to the right. Both screenshots fit without cropping and link to their original full-size PNGs. A soft orange halo and animated mist sit behind each device; reduced motion keeps the glow still. See `docs/imessage-showcase.md` for provenance and verification.
- `components/mcp-connections.tsx` sits between the Video Editing and Video Creation homepage previews. Its CSS module recreates the Krea MCP reference's fading 56px grid, overlapping dark tiles and glowing white Browser Use tile. OpenAI and Claude sit nearest the center; Cursor, Hermes, Pi and OpenClaw recede with tiered blur and opacity. The center links to `/mcp`, all six client marks stay visible on phones, and official asset provenance lives in `public/clients/brand-sources.json`.
- `components/mcp-dots.tsx` adds an open, dotted MCP promotion between the Video Creation and 3D previews. Original SVG characters in `mcp-mascot.tsx` share soft clay shading with distinct silhouettes, glasses, sunglasses and headphones. A pearl character sits in the white headline, with closer floating roles, pill labels, outlined cursors, a soft pearl glow, and a dotted lower edge. The Browser Use orange button opens the existing connection dialog. Small screens place the characters below the copy, and reduced motion disables their drift.
- `components/mcp-announcement.tsx` adds a full-width, flat announcement strip directly above the header, following the Higgsfield reference with a softer orange blend. Centered 20px dark text leads with “Make videos in your AI chat” and a bold “Try Video Use MCP” link to `/mcp#setup`, without an arrow or separate CTA button. Phones use two centered lines with 16px/18px type. The background blend drifts slowly; reduced motion keeps it static. The close X remembers dismissal for the browser tab's session and returns keyboard focus to the home link.
- `lib/gallery.ts` contains the real filtering and URL parsing logic. Legacy classifications use stable IDs rather than display titles, so renaming a clip preserves its filters. `buildChatPrompt` appends a visible handoff to the example's original brief.
- `app/globals.css` owns the neutral black/white/gray palette, responsive containers, and media treatment. All brand accents share `--accent: #fe750e`, matching Browser Use's `--pumpkin-500` color; MCP page tints derive from the same token.

## Gallery interactions

The homepage shows up to sixteen curated examples per collection. View all opens a separate route containing every matching clip, a hero explaining the collection, and search. Filters open an optional panel above the grid; its options and counts are scoped to that collection. `/library` provides a complete cross-collection search. The header exposes Explore, Video Editing, Video Creation, 3D Visuals, and MCP, with a separate horizontal navigation row on smaller screens.

Headings and card titles use locally hosted Space Grotesk (400–700), with Inter for interface text. Font provenance and the SIL OFL license are in `public/fonts/space-grotesk-source.json` and `SpaceGrotesk-OFL.txt`. The Browser Use accent remains `#fe750e`. Featured cards retain their existing geometry; gallery corners use 16px radii.

The compact card action copies the same full prompt as the detail dialog. Card previews have no duration badges, and neither cards nor expanded players have like controls or counts. The frontend does not load or submit likes. Cards reveal a centered title and Copy Prompt on hover and keyboard focus; touch devices show them continuously. The overlay scales for narrow landscape cards while preserving every video aspect ratio. Search and video types stay above the full collection grids, with audience/use-case options in the Filters panel. Existing category/search/facet/deep-link behavior is retained. The opening gallery order mixes film formats without changing the source catalog.

The opening gallery keeps Screen Studio first. `openingIds` controls the curated order, and `wideOpeningIds` can mark landscape films that need more room. Wide cards span two columns on phones and large desktops, and one at the three-column breakpoint. The five rejected launch films (IDs51–55) are removed from the visible catalog; their historical source records and immutable release assets remain for provenance. The next batch focuses on edits of actual creator, sports and product footage, with exact prompts containing direct source links.

The legacy server-only likes route (`app/api/likes/route.ts`), signing helper (`lib/likes-server.ts`), and database votes are retained. The site UI does not call them. The endpoint still requires `INSFORGE_URL`, `INSFORGE_API_KEY`, and `LIKES_COOKIE_SECRET` if used directly; the schema remains recorded in `../migrations/20261004054241_gallery-likes.sql`.

Coordination and verification notes are in `docs/ui-refresh-handoff.md`.

## Example data

`data/examples.json` is the public gallery source. Every entry must point to a real, reviewed video and poster. Do not publish queued jobs or placeholder media as examples.

Clip titles name the visible subject in a few words (for example, Red Telephone or Messi Goals). Cards allow two compact lines. Rename the title without changing the stable ID, source prompt, or media URLs so saved links and likes keep working.

Required fields:

```json
{
  "id": "stable-example-id",
  "title": "A useful workflow",
  "category": "Motion Design",
  "description": "What this workflow helps the viewer do.",
  "prompt": "The original creative request or an explicitly labeled reusable starter.",
  "video": "https://public-media-host/final.mp4",
  "poster": "https://public-media-host/poster.jpg",
  "duration": 18,
  "promptKind": "Original prompt",
  "orientation": "landscape"
}
```

The four categories are Video Edits, Video Creation, Motion Design, and Explainers. `promptKind` is either `Original prompt` or `Starter prompt`; a starter is not a claim that those exact words generated the video.

Optional fields for practical workflows:

- `audiences: string[]`, such as Content creators, Founders, Marketers, Designers, Educators, or Product teams.
- `useCases: string[]`, such as Product launches, Product demos, Social content, or Tutorials.
- `technique: "motion-design" | "3d" | "diagrams" | "video-editing"`.
- `sourceRepo: string` and `promptSource: string` for a public source URL and short adaptation credit.
- `sourceArchive: string` and `reviewUrl: string` for the editable project and production notes.

Legacy examples retain their original content. Conservative fallback tags classify art-only pieces as Motion studies. Explicit tags on new examples override those fallbacks. Each collection uses a continuous grid with scoped filters; `/library` searches all collections together.

`data/media-sources.json` preserves provenance, source rights, exact prompts, run/container/framework evidence, reviews, and output hashes. Do not replace the stored original prompt with the chat handoff. The UI shows exactly what Copy Prompt copies, including the example link and instructions to preserve the user's involvement and approval mode.

The earlier library includes unboxing and Tears of Steel edits, footage-based montages, original motion studies, and technical explainers. Film excerpts retain attribution in the detail view. Existing batch history and review artifacts are recorded in the provenance ledger.

The three `screen-demo-*` examples are archived educational browser/app edits from x-demo-maker with saved Video Use creation evidence. Their public films are silent, retain contextual credits, and use reconstructed Starter prompts. They include production notes, but no editable project ZIP or claim of a new MCP generation. The bounded publisher is `../experiments/publish_archived_screen_demo.py`; private historical records remain outside the public site.

### Importing reviewed receipts

Run `node scripts/import-reviewed-examples.mjs /path/to/receipt.json [...]` only after publication verifies the reviewed media bytes. All input receipts are validated before any manifest is written. The established `useful-*` and MCP receipt formats remain supported.

New `social-XX-slug` receipts contain the public `approval` subset (`id`, `approved`, `sha256`, `sourceReviewed`, `sourceSha256`, and a review of at least 80 characters). Movie and source hashes must agree with the published `hashes`, `publicCheck`, and source ledger. The exact executed text stays an **Original prompt**. The displayed prompt plus one newline must match the SHA256 of `creative-prompt.txt`, and its public URL must match `source.promptUrl`.

Initial `screen-demo-slug` archive receipts require explicit movie approval and use a **Starter prompt** reconstructed from historical creation evidence. They omit source ZIPs and editable-source hashes; an archived film is not relabeled as a new generation. `source.kind` is `archived screen demo created with Video Use`, and `source.sourceArchiveScope` is `Published film and reconstructed starter prompt; editable project not included`. Record the actual `sourceRun`, describe creation evidence in `production`, and match the example/source `promptSource` credits. The displayed starter plus one newline must match the published `prompt.txt` hash and URL. No-source archives cannot claim editable-source review.

Both new receipt kinds require `assets` and `hashes`, matching movie/poster/review URLs, a public movie SHA256 and successful byte-range playback. Campaign imports group social edits and screen demos ahead of earlier examples; the existing six opening cards remain curated separately. Use explicit audience/use-case metadata, reusing Product demos, Tutorials, Podcast clips, Interview clips, Social content and Social reframing where appropriate. The current player already preserves full frames and source audio for Video Edits.

`npm run check:imports` exercises the real importer in temporary directories, including approved imports, legacy compatibility, loop preservation, and rejection of changed hashes/prompts or unreviewed records without partial catalog writes. It never imports fixture data into this website.

## Links from a conversation

- `/?technique=motion-design#examples`
- `/?technique=3d#examples`
- `/?technique=diagrams#examples`
- `/?technique=video-editing#examples`
- `/?example=stable-example-id`

Category, text search (`q`), audience, and use-case filters also persist in the URL. Multiple values are OR within an audience/use-case group and AND between different groups. Invalid technique names, unknown IDs, and unsupported facet values are ignored safely. Opening an example adds browser history; Back closes it.

The copied prompt asks the agent to adapt the workflow to existing chat context, skip unrelated reference searches, preserve involvement mode, and request snippet approval in hands-on mode. Copying a prompt never starts a render or grants approval.

## MCP launch media

`data/mcp-launch.json` selects the published 720p autoplay film, 1080p full film, poster, measured duration, and `loop: true` for the full player. Both the homepage feature and MCP page consume the same manifest. The 11.6-second silent loop opens with kinetic INTRODUCING lettering and a brief orange underline. The original white Browser Use mark leads into Video Use MCP, with MCP in Browser Use orange #FE750E, then connects to the official Cursor/Claude/ChatGPT marks below it with three arrows. The existing ChatGPT-style composer adds a gentle push-in and moving edge light while preserving all text and controls; the Create me a/an prefix stays visible while only the request suffix changes. A cursor presses Send, then the unchanged white words “Create and edit videos at the speed of thought” play in 1.8 seconds before the opening returns. The protocol badge remains absent. It is an authored promotional illustration, separate from the prompt gallery, with no generated-result footage or claim of a captured live MCP call.

The editable source archive contains the authored HTML/CSS/SVG timeline, local assets and fonts, exact request, creative contract, pinned dependencies and render instructions. Its public URL, key and checksum are retained with the media receipts. The preceding 13-second cut, 1.75x version, original 22-second cut and earlier 12-second film remain in the featured provenance history.

`data/product-launch.json` uses the same media fields for the user-provided 31.648-second Product Launches film. The source MP4, audio, and embedded captions are preserved. Both promotional films stay separate from the gallery example count. `data/featured-media-sources.json` records their current provenance; each media manifest retains the InsForge storage bucket, returned URL, object key, and file hash. Public media is served from the site project’s `site-media` bucket with versioned keys. Historical MCP provenance remains in `media-sources.json`.

`components/mcp-copy.tsx` provides copy feedback and selectable fallbacks for the landing page’s URL, Cursor configuration, and starter prompts. `ConnectMcp` accepts an `initialClient` so each setup card opens the correct guide.

## Playback and accessibility

The header’s GitHub badge shows the repository’s real star count in compact notation, with the exact count in its accessible label and hover title. `lib/github.ts` reads GitHub’s public repository endpoint on the server and caches it for one hour, allowing the pages to revalidate without a redeploy. If GitHub is unavailable, the badge remains a working GitHub link without inventing a count.

Cards use proportional preview windows that match their video format; featured films use wide windows in a snapping carousel. Full players also preserve the entire frame, including portrait edits. Motion Design defaults to muted, repeating playback in detail. Optional booleans `muted` and `loop` on an example override those defaults; the five launch gallery films open with their original sound and play once. Gallery previews remain muted. Video Edits, Video Creation, and Explainers preserve the source audio in the full player. The MCP launch preview is muted; the full film has native controls.

Dialogs support keyboard focus, dismissal, and focus restoration. Every copy action has visible feedback and a manual-selection fallback. The full collection pages keep search and video types above the gallery. Filters toggles a panel with type, audience and use-case options; Reset clears active filters within the current collection. Audience, installation, and provenance sections use keyboard-accessible disclosures; the complete copied prompt stays visible. Cropped homepage cards are inert so keyboard focus cannot disappear below a preview. Reduced motion disables decorative transitions; video previews continue to autoplay and loop per the requested browsing behavior. Fonts are local, with OFL licenses in `public/fonts`.

The quieter component hierarchy follows [Base UI disclosure guidance](https://base-ui.com/react/components/collapsible), [shadcn item patterns](https://ui.shadcn.com/docs/components/base/item), and [Motion accessibility guidance](https://motion.dev/docs/react-accessibility), using the dependencies already installed.

The library does not provide accounts, uploads, payments, or a rendering backend. The hosted MCP is a private pilot with its own sign-in and access requirements. The website makes no promise that every MCP client or every account tier supports every feature.

## Cloud media storage

The featured retry (useful-56 through60) renders in Modal and streams finished videos from Cloudflare R2. Each release includes the original executed prompt, an editable source archive, source attribution and a review tied to the exact published hashes. Source footage is backed up with authenticated encryption in R2; recovery metadata also lives in R2 and the shared Modal volume. The archive key stays in the Modal secret `video-use-source-archive-v1` and must not be overwritten.

`experiments/source_relay.py` provides a bounded, diskless network fallback when cloud yt-dlp access fails. `experiments/archive_cloud_media.py` verifies encrypted source backups and cloud restores. `experiments/useful_video_library.py fetch --review-only` retrieves bounded images and metadata without downloading video, audio or complete ZIPs to the developer machine. Local cleanup removes only files whose hashes match freshly verified immutable cloud objects. The footage-specific ramp and annotation prototypes remain in the editable project archives; their documented constraints are not exposed as general framework guarantees.
