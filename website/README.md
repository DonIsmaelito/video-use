# video-use website

The open-source library's inspiration gallery, kept separate from the Python editing harness and `gui/` product.

## Run locally

Requires Node 22.13 or newer.

```sh
cd website
npm ci
npm run dev
```

Open the Local URL printed by the server. It tries port 3000 first and picks the next available port if needed. The current preview runs at http://localhost:3001.

```sh
npm run build
npm run check
```

## Where things live

- `app/page.tsx` composes the opening, gallery, and footer.
- `app/globals.css` owns the lavender palette, typography, layout, responsive behavior, and animation.
- `components/hero.tsx` rotates the headline, respects reduced motion, and reads GitHub's public stars count. If GitHub is unavailable the link remains available without inventing a count.
- `components/gallery.tsx` owns filters, hover previews, the accessible detail dialog, and clipboard feedback. Videos load metadata near the viewport, play silently on hover or focus, and pause on exit or when a dialog opens. Touch users tap to open the full player.
- `components/pixel-wordmark.tsx` draws the cropped VIDEO USE footer with square-pixel letterforms and a gentle light wave. Animation pauses offscreen and respects reduced motion.
- `lib/gallery.ts` provides filtering and duration formatting.
- `data/examples.json` is the gallery content. Add a record here to add a video. Category counts update automatically.
- `public/media/` contains four original motion pieces and their posters. Twelve other examples stream from the existing public video-use R2 library.

`promptKind` distinguishes saved original prompts from self-contained starter prompts adapted from the source run. Starter prompts are examples, not a claim that these exact words produced the displayed result. Portrait footage remains fully visible during playback; the cards use cropped posters for the fixed 4:3 gallery layout. The popup shows only the full video, a reusable prompt, and its copy action.

## Design and assets

The opening takes its large serif composition and lavender rule from https://studiohuncho.com/work. The gallery follows https://motionimo.xyz/resources with four columns, 24px horizontal gaps, 4:3 media windows, pill filters, and Inter metadata. Instrument Serif is the open-font alternative for the headline. Fonts are bundled locally with their OFL licenses.

The Browser Use mark comes from https://browser-use.com/logo-primary.svg. The GitHub icon comes from Simple Icons. All gallery clips come from prior video-use runs; `data/media-sources.json` records the run IDs and source types. The share image is an original generated asset.

This preview has no account system, uploads, or editing backend. Its header links to the open-source repository. Before deployment, set `SITE_URL` to the chosen public origin so social previews use the production URL. Keep `.openai/hosting.json` and `sites()` in the Vite configuration for Sites compatibility.
