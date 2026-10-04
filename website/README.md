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

## Routes and components

- `app/page.tsx` assembles the compact header, featured films, example gallery, and footer.
- `app/mcp/page.tsx` and its CSS module provide the centered MCP landing page, launch film, three-step flow, client setup cards, copyable starter prompts, and FAQs.
- `components/site-header.tsx` and `wordmark.tsx` provide the shared navigation and open-source links. The header's small “by Browser Use” credit glows slowly and stays still for reduced motion.
- `components/gallery.tsx` handles audience/use-case/video-type/category filters, search, clipboard feedback, deep links, and the detail dialog. Video type keeps the internal `technique` data key and URL parameter.
- `components/preview-media.tsx` loads media near the viewport and plays only visible, muted previews. Previews pause in hidden tabs, under dialogs, and for reduced motion. Tall gallery windows preserve the full frame over a blurred poster; featured films remain wide.
- `components/connect-mcp.tsx` provides copyable setup URLs and separate ChatGPT, Claude, Cursor, and local-source instructions. Official client artwork lives in `public/clients`, with its provenance in `brand-sources.json`; compatible clients are not presented as end-to-end tested.
- `components/ui/disclosure.tsx` uses Base UI for optional filters and source details. `technique-icon.tsx` gives each video type a consistent icon.
- `components/mcp-feature.tsx` leads the fixed hero order: MCP, Product Launches, then Whiplash. `featured-film.tsx` shares an accessible full-film dialog for the product and MCP films; opening it pauses background previews. `mcp-launch.tsx` places the new 12-second film on the MCP page.
- `lib/gallery.ts` contains the real filtering and URL parsing logic. `buildChatPrompt` appends a visible handoff to the example's original brief.
- `app/globals.css` owns the neutral black/white/gray palette, responsive containers, and media treatment. All brand accents share `--accent: #fe750e`, matching Browser Use's `--pumpkin-500` color; MCP page tints derive from the same token.
- `components/use-gallery-likes.ts`, `app/api/likes/route.ts`, and `lib/likes-server.ts` provide shared, persistent likes with one vote per example per signed browser identity. Counts start at zero; the database stores a hash rather than the cookie itself.

## Gallery likes

Configure `INSFORGE_URL`, `INSFORGE_API_KEY`, and `LIKES_COOKIE_SECRET` in local and hosted server environments; see `.env.example`. None use a public framework prefix. The schema is recorded in `../migrations/20261004054241_gallery-likes.sql` and was tested in an isolated InsForge backend branch before being applied to the existing site project. Anonymous and authenticated clients have no direct table or RPC access; the server validates example IDs and the request origin. Retrying a like does not add another vote. Clearing browser cookies resets the anonymous identity.

The compact card action copies the same full prompt as the detail dialog. Cards expose controls on hover and keyboard focus; touch devices show them continuously. Filters stay visible in the sidebar, and all existing category/search/facet/deep-link behavior is retained. The opening gallery order mixes film formats without changing the source catalog.

Coordination and verification notes are in `docs/ui-refresh-handoff.md`.

## Example data

`data/examples.json` is the public gallery source. Every entry must point to a real, reviewed video and poster. Do not publish queued jobs or placeholder media as examples.

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

Legacy examples retain their original content. Conservative fallback tags classify art-only pieces as Motion studies. Explicit tags on new examples override those fallbacks. The gallery uses one continuous grid with shared filters.

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

`data/mcp-launch.json` contains:

```json
{
  "src": null,
  "video": null,
  "poster": null,
  "duration": null
}
```

Replace these only after publication with the lighter muted autoplay URL, full MP4 URL, poster URL, and measured duration. Until then the tile shows an original static design with no fake playback control. It is promotional content, separate from the gallery example count.

`data/product-launch.json` uses the same media fields for the user-provided 31.648-second Product Launches film. The source MP4, audio, and embedded captions are preserved. Both promotional films stay separate from the 117 gallery examples. `data/featured-media-sources.json` records their current provenance; each media manifest retains the InsForge storage bucket, returned URL, object key, and file hash. Public media is served from the site project’s `site-media` bucket with versioned keys. Historical MCP provenance remains in `media-sources.json`.

`components/mcp-copy.tsx` provides copy feedback and selectable fallbacks for the landing page’s URL, Cursor configuration, and starter prompts. `ConnectMcp` accepts an `initialClient` so each setup card opens the correct guide.

## Playback and accessibility

The header’s GitHub badge shows the repository’s real star count in compact notation, with the exact count in its accessible label and hover title. `lib/github.ts` reads GitHub’s public repository endpoint on the server and caches it for one hour, allowing the pages to revalidate without a redeploy. If GitHub is unavailable, the badge remains a working GitHub link without inventing a count.

Cards use tall preview windows with a blurred poster behind the complete original frame; featured films use wide windows. Full players also preserve the entire frame, including portrait edits. Motion Design remains silent and loops in detail. An optional boolean `loop` on an example overrides whether its full player repeats, without changing audio behavior. Video Edits, Video Creation, and Explainers preserve the source audio in the full player. The MCP launch preview is muted; the full film has native controls.

Dialogs support keyboard focus, dismissal, and focus restoration. Every copy action has visible feedback and a manual-selection fallback. Browsing controls stay visible in a left sidebar on desktop and stack above the gallery on mobile, without a global Filters button. Use case stays permanently expanded. Audience, installation, and provenance sections use keyboard-accessible disclosures; the complete copied prompt stays visible. Reduced motion disables automatic previews and decorative transitions. Fonts are local, with OFL licenses in `public/fonts`.

The quieter component hierarchy follows [Base UI disclosure guidance](https://base-ui.com/react/components/collapsible), [shadcn item patterns](https://ui.shadcn.com/docs/components/base/item), and [Motion accessibility guidance](https://motion.dev/docs/react-accessibility), using the dependencies already installed.

The library does not provide accounts, uploads, payments, or a rendering backend. The hosted MCP is a private pilot with its own sign-in and access requirements. The website makes no promise that every MCP client or every account tier supports every feature.
