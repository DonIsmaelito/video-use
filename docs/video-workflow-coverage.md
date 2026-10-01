# Browser video workflow coverage

This is an engineering coverage map for the Claude/ChatGPT MCP branch. The host
assistant chooses and authors the piece; categories provide optional context,
not fixed templates or a deterministic query router. Support here describes an
implemented production path, not an assertion that every example has passed an
end-to-end creative or account-level test.

- **Supported**: an achievable version can use the installed primitives and
  ordinary supplied inputs. Artistic quality still requires agent judgment and
  inspection of the real output.
- **Conditional**: substantial assets, specialist validation, a compatible
  format, scale limits, or external capabilities change feasibility. The
  dependency is stated in the row.
- **Unavailable**: the requested operation itself has no configured adapter or
  provider. A different achievable version must be identified as an alternative.

Inputs belong to the authenticated project. A user may upload files or supply a
downloadable public HTTPS file; signed cloud storage links work only when they
are actual accessible files. A video watch page is not media. Claude/ChatGPT
account connectors and browser sessions are not inherited by this server.
Where the host supports a file picker it can transfer a selected file explicitly;
otherwise use the project's upload flow. Neither path grants general account
access.

## Shared implemented building blocks

| Building block | Implementation and practical boundary |
| --- | --- |
| Project state and creative context | `start_video`, optional `plan_video`, project files and checkpoint storage. Original category names remain valid; supplementary categories are optional. |
| Creative references | Six cached example clips: diagrams, editorial motion, two caption treatments, interface focus and procedural product assembly (`product_3d`). The optional picker accepts two or three catalog references independently of category; these are examples, not a complete style catalog or mandatory templates. |
| Source inspection | `inspect_source.py` summarizes supported document/data inputs; page, slide and row provenance matter. Bounded CSV/TSV/JSON/XLSX inspection and document extraction default to 25 MiB. XLSX exposes stored cell values, formula text/unverified caches, formats and sheet/cell locators; it does not recalculate formulas. `pdftoppm` renders PDF pages; text extraction is not OCR or a native Office renderer. |
| Clip editing | `edl.py`, `render.py`, `visuals.py`, `grade.py`: timed cuts, crop/reframe, overlays, color, format and audio treatment. |
| Speech and captions | Coordinator `transcribe_video` and `narrate_video`; cached word timing and `captions.py`. Worker scripts do not receive speech keys. Language/voice suitability must be verified for each request. |
| Stills and audio-first sequences | `media_sequence.py` creates editable manifests and FFmpeg sequences from local assets. Useful for photos, cover art and paced document images. |
| Audio-responsive motion | `motion_audio.py` measures amplitude/spectral features; deterministic browser composition uses those measurements. No music-generation provider. |
| Programmatic explanation | Manim and domain helpers for geometry, graphs, systems, biology, computing, finance and mathematics. These are drawing primitives, not authoritative domain facts. |
| Browser motion and 3D | `motion_render.mjs`, local CSS/canvas and Three.js; procedural meshes and compatible local glTF/GLB. CPU/software-WebGL bounds apply. |
| Tracking | OpenCV source tracking and local overlay alignment. This is not guaranteed semantic object understanding or generative inpainting. |
| Bounded independent scenes | `run_video_step` component commands render with capped concurrency and assemble only after success. No hidden provider-paid LLM agents. |
| Review and delivery | Encoded-frame review, full decode validation, private source/archive storage, in-chat preview and MP4 download where supported by the host. |

## Educational and explainer content

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| How does X work | Supported | Compose causal diagrams, local assets and timed narration; verify specialized claims from supplied or host-researched sources. |
| School subject lessons | Supported | Manim worked examples, supplied illustrations and narrated explanation; adapt difficulty rather than require one lesson structure. |
| Company explainer | Supported | Browser motion, product assets and narration. Authentic product facts/assets are inputs; original character illustration is authored code or supplied art. |
| Employee training and onboarding | Conditional | Documents or recordings can become narrated scenes. Actual policies, procedures and reviewer authority must be supplied; output is not automatically compliance-approved. |
| X explained in five minutes | Supported | Flexible chapter scenes and narration, subject to render and speech allowances. No fixed chapter count. |
| Concept comparisons | Supported | Shared comparison criteria and aligned diagrams/charts; avoid changing scales or definitions to make a visual point. |
| Historical timelines | Conditional | Timeline motion is supported; source-backed chronology, archival media and compatible local map assets are needed. No archival search/licensing adapter. |

## Data-driven videos

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Bar chart races | Supported | Parse comparable time series; author stable ranking, labels and transitions in Manim/browser motion. |
| Stock and market recaps | Conditional | Supplied dated data or host-obtained snapshots can be charted. No live market feed or financial verification service. |
| Sports statistics | Supported | Supplied results/stat tables to charts and motion. Automatic live standings acquisition is unavailable. |
| Company metrics and investor updates | Supported | Data plus report/deck extraction, consistent chart units and branded narration. Figures must match the source. |
| Personalized year-in-review | Conditional | User-exported activity data and an authored reusable composition. No Spotify/Strava/Duolingo account integration or bulk annual job scheduler. |
| Weather and election results | Conditional | Supplied snapshots and map geometry are renderable; no live feeds, polling updater or official-results validation adapter. |
| Infographic videos | Supported | Source-linked quantities rendered as geometry, charts, comparisons and narration. Distinguish illustrative from measured values. |

## Marketing and commercial videos

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Product showcases | Supported | Supplied photographs/footage and feature callouts; accurate 3D views require a compatible model or achievable authored geometry. |
| Social media ads | Supported | Asset sequences, hook/copy/CTA and bounded visual variants; no automated ad buying or campaign performance evaluation. |
| Real estate listings | Supported | Supplied listing photos/footage and verified listing details; 3D reconstruction from those photos is unavailable. |
| Restaurant and menu videos | Supported | Supplied dish images/footage, prices and details; do not invent dish appearance or offers. |
| Sale and promotion announcements | Supported | Typography and product assets with a real supplied offer, dates and CTA. |
| Testimonials | Supported | Supplied genuine quotes or clips with captions, identity and logos; no fabricated endorsement or ratings. |
| Brand intros and logo animation | Supported | Supplied logo or authored typography animated in browser motion; 3D variants can use supported geometry. |
| Event promotions | Supported | Supplied event details, speaker assets and motion; schedule facts are inputs and ticket distribution is outside scope. |

## Software demos and tutorials

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Product demos | Conditional | Edit actual screen recordings/screenshots. This service does not operate a logged-in product browser to capture them. |
| Feature release videos | Conditional | Real recordings/assets and release facts are needed; render callouts, comparisons, narration and captions. |
| How-to tutorials | Conditional | A source recording or screenshots of the correct product/version are needed; verify each demonstrated action. |
| Customer support videos | Conditional | Supplied validated steps and real UI capture; do not invent controls or account states. |
| Onboarding walkthroughs | Conditional | Actual UI states/recording plus intended path; capture through another host tool must be explicitly transferred. |
| Coding tutorials | Supported | Author or use supplied code, locally demonstrate runnable supported examples, narrate and compose code visuals. Arbitrary package installation or external-service setup may require another environment. |

## Personal footage and photo montages

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Travel videos | Supported | User-selected source clips/photos, coherent selects, title/caption treatment and supplied music. |
| Wedding highlights | Supported | Supplied ceremony/reception media; speech-aware vows, meaningful chronology and audio transitions. |
| Birthday and anniversary slideshows | Supported | Photo sequence with supplied names/dates/order and optional sound; preserve important subjects in crops. |
| Memorials and tributes | Supported | Respectful sequencing of supplied assets; clarify meaningful omissions or naming only when uncertain. |
| Baby and childhood milestones | Supported | Selected photos/videos, verified dates and optional voiceover; no automatic photo-account search. |
| Graduation and end-of-year recaps | Supported | Supplied images/clips and names; consistent typography and bounded group/individual variants. |
| Event recaps | Supported | Footage selects, source audio, overlays and format-specific exports. |
| Fitness and transformation stories | Supported | Supplied chronological material with truthful labels, comparable framing and no invented outcome claims. |

## Documents to video

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Blog post to video | Supported | Supplied text, Markdown or document export to narrated visual interpretation. Stock footage must be supplied; no stock-search adapter. |
| Slide deck to video | Conditional | PPTX extraction supports content adaptation. Exact slide appearance needs exported images or a PDF export rasterized with `pdftoppm`; animations/embedded objects and native Office rendering are not guaranteed. |
| News summaries | Conditional | Host-obtained or supplied dated articles with provenance; no news-feed adapter or automatic fact verification. |
| Research paper summaries | Conditional | Readable paper extraction plus accurate interpretation and source review. Scanned pages need external OCR; figure extraction and exact figure selection can require page images rendered with `pdftoppm`. |
| Book summaries | Conditional | Supplied accessible material, chapter notes or authorized excerpts; preserve meaning and avoid inventing details from a title. No book acquisition service. |
| Newsletters and reports | Supported | Readable supplied document/text plus source-linked charts, imagery and narration; preserve material qualifications. |

## Audio-first videos

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Podcast clips | Supported | Audio/video excerpt, timed speech transcription, cover art, captions and optional waveform motion. |
| Lyric videos | Conditional | Supplied lyrics, music and checked timing; speech ASR is not a reliable singing aligner. No lyric lookup or forced music-alignment adapter. |
| Music visualizers | Supported | Supplied audio, measured waveform/spectral envelopes and deterministic local motion. |
| Full podcast episodes | Conditional | Cover art plus source audio is simple, but long durations may exceed task/output/daily compute limits. No promise of arbitrary episode length. |
| Audiobooks and meditation videos | Conditional | Supplied or bounded configured narration and appropriate local visuals; long-form speech/render allowances and source rights remain constraints. |

## Personalization and localization

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Sales outreach | Conditional | Small, explicit recipient records and supplied site images can drive personalized compositions. No CRM, website capture, sending or campaign scheduler. |
| Customer welcome videos | Supported | A small bounded set of user-supplied records mapped to an editable scene; each output must match its record. |
| Thank-you videos | Supported | Supplied recipient details, variable text/assets and optional configured voiceover. No automatic purchase/donation trigger. |
| Birthday and holiday greetings | Supported | Small batches from explicit records, occasion details and assets. No customer database sync or automatic distribution. |
| Localized versions | Conditional | Host-authored translations, available local fonts and suitable supplied/configured audio. No voice cloning, face lip sync or guaranteed multilingual dubbing. |
| Account and billing summaries | Conditional | Correct explicit records and domain-reviewed explanations are essential. No banking/insurance feed, account access or compliance validation. |

## 3D and procedural animation

| Everyday request | Coverage | Production path and dependency |
| --- | --- | --- |
| Product renders | Conditional | Three.js procedural geometry or supplied compatible GLB/glTF; exact fidelity needs real geometry/materials. No photoreal promise or automatic CAD conversion. |
| Architectural flythroughs | Conditional | A modest compatible local scene can be animated. No floor-plan reconstruction, BIM/CAD importer, navigation model or production GPU render farm. |
| 3D logos and titles | Supported | Author suitable geometry/type with local assets; prove font/model loading and legibility at the delivery size. |
| Medical and scientific animation | Conditional | Manim/Three.js can illustrate geometry and mechanisms; validated source material, accurate models and expert review are necessary for factual claims. |
| Assembly and exploded views | Conditional | Supplied component models and correct relationships, or a clearly illustrative authored model; no automatic engineering inference. |
| Stylized animated scenes | Supported | Bounded procedural/local-model scenes with deterministic camera and material animation. Complex character rigging or high-fidelity simulation requires additional tooling. |

## Cross-cutting requests outside the list

| Request | Coverage | Boundary |
| --- | --- | --- |
| Captions, cuts, reframing, color and audio edits | Supported | Use the requested operation directly when the source and intent are clear. |
| Remove a visible object without cropping or masking | Unavailable | Generative inpainting/reconstruction is not configured. Offer crop/mask only if it solves the user's intent. |
| Turn an uploaded long video into several clips | Supported | Transcript selects and bounded independent renders; do not automatically scrape a watch page. |
| Generate photoreal shots from a prompt | Unavailable | No generative-image/video provider is configured in this MCP; edit supplied generated assets instead if appropriate. |
| Edit externally generated clips | Supported | Treat them as ordinary local media and check continuity, sound and delivery properties. |
| Read the user's connected Google Drive/Photos automatically | Unavailable | Host account permissions are not delegated to the MCP. Explicit transfer/upload/export is required. |
| Download a public direct media/document link | Supported | The importer validates destination, redirects, file limits and allowed formats; not a general browser/scraper. |
| Record a signed-in website or desktop | Unavailable | The local rendering browser is not the user's session; capture must come from an explicitly available external tool. |
| Automatically deliver thousands of personalized videos | Unavailable | No bulk delivery, event automation or campaign queue; the pilot provides bounded jobs and explicit downloads. |

## Why these are not per-genre templates

The workflow module adds document, audio, personalization, procedural 3D and
custom contexts alongside the original categories. A primary category and up to
three supporting categories supply relevant inputs, techniques, questions and
limitations. They do not select content, impose a beat count, force an approval
pause or prescribe a font, palette or renderer. Existing project states and
older client category values remain compatible.

The shared browser guidance lives at
[`skills/video-workflows/browser-production.md`](../skills/video-workflows/browser-production.md).
It describes how to combine capabilities, how to ask useful questions and what
evidence needs checking. Each renderer's existing detailed guidance remains the
source for production-specific commands and constraints.

## Verification scope

The new workflow tests exercise mixed document/data/brand requests, preserved
user preferences, stale-choice reset when intent changes, open-ended custom
requests, two- or three-reference overrides, invalid references and rejected
oversized combinations. Source resilience tests cover hard transfer deadlines,
durable receipts after worker copy errors, and healthy source refresh that
preserves rendered caches even across a transient refresh failure. Input/helper,
renderer and live MCP tests should be recorded separately by the deployment run.
A test of a photo sequence or local 3D scene validates that building block; it
does not establish that all rows above produce excellent videos autonomously.

Remaining integration work with external dependencies includes researched asset
acquisition, OCR/native Office rendering when needed, authenticated cloud imports,
logged-in screen capture, specialized model conversion, generative providers,
advanced dubbing and campaign automation. Add those only through explicit
capability adapters and truthful availability reporting. Do not promise them
merely by adding another workflow label or skill paragraph.
