# Motion library

Use the library when a brief needs stronger visual premises, a particular asset role, or reusable authored geometry. Start with the premise. Search by an action such as assembly, interaction, layer-reveal or deformation, then inspect a few relevant entries. Read the actual reference media when possible; written observations do not replace it.

## Discover and acquire

Run from the video-use repository root with Python 3.10 or newer:

```bash
python3 helpers/motion_library.py search assembly
python3 helpers/motion_library.py list --kind reference --tag asset-family
python3 helpers/motion_library.py show lilium-flower-family
python3 helpers/motion_library.py show optical-assembly
python3 helpers/motion_library.py check
python3 helpers/motion_library.py fetch polyhaven-studio-small-09-1k --out edit/animations/slot_hero/assets
python3 helpers/motion_library.py fetch polyhaven-metal-plate-02-1k --out edit/animations/slot_hero/assets
```

`list` and `search` match words across ID, title, summary and tags; every query word must match, and repeated `--tag` filters are combined. Start with one behavior term when a broad combined query returns nothing. `--json` on list/search returns a compact selection; `show ID --json` returns the complete entry. A custom catalog uses `--catalog PATH` before the command. The default catalog resolves relative to the helper file, so an isolated copy of the framework keeps working.

Fetching is explicit and only available for approved `asset` entries. It verifies HTTPS downloads against exact byte counts and SHA-256 hashes, stages all missing files before publishing them without overwriting existing files, and writes `motion-library-<id>.receipt.json`. A valid local cache is reused. A mismatched existing file or receipt stops the fetch so a project edit cannot be silently replaced. Files and combined entry downloads are limited to 64 MiB. There is no archive extraction, provider login or automatic crawling. Fetch does not determine whether an asset improves the design—inspect it after loading.

Keep the receipt and any required license files with editable project deliveries. If an upstream file changes, verify its new contents and terms before updating the catalog pin. Do not solve a hash failure by removing verification.

## One catalog, four kinds

The canonical index is [catalog.json](../library/catalog.json). It contains metadata and original observations; third-party binaries live in the project's asset directory.

| Kind | What it supplies | What to do with it |
|---|---|---|
| `reference` | Creator/source, observed beats, evidence scope, action, asset roles and preserved property | Study the relationship and author an original interpretation; `reuse` is `reference-only` |
| `resource` | A provider, its useful roles and applicable license conditions | Select an individual asset and verify its exact terms; the provider entry cannot be fetched |
| `asset` | Specific files, creator/license, exact URLs, hashes and sizes | Fetch into the project, await decoding, inspect the render and retain provenance |
| `recipe` | Original implementation, contract, controls and proof instructions | Copy the selected source into a project and supply its camera, timeline and materials |

Common fields are `id`, `kind`, `title`, `tags`, `summary` and `source_url`. A recipe with `authorship: "original"` and a valid `implementation` can omit `source_url`; this avoids inventing an upstream author. `detail` and `implementation` paths are relative to the catalog directory and must remain inside it. `related` contains existing entry IDs. References require an `evidence` record and `reuse: "reference-only"`. Assets require `license.name`, `license.url`, an explicit boolean `license.redistribution`, an attribution string, and nonempty `downloads` with `url`, plain `filename`, `sha256` and `bytes`. Only assets may declare downloads; fetching requires redistribution to be true. Provider-level permission never automatically turns a resource into an approved asset.

## Original recipes and prompt examples

The [tracked prompt examples](../library/prompt-examples.json) preserve each exact request, the expanded direction, selected catalog IDs, source links and asset provenance. They are authored trials with documented repair, not an autonomous benchmark or a general quality claim. Use the prompt as the content contract and the recipe as a component; author the new composition around the requested behavior.

| Recipe / discovery term | Reusable behavior | Assets used by its demonstration |
|---|---|---|
| [Optical assembly](../library/recipes/optical-assembly.md) · `assembly` | `setState({aperture,separation,rotation})` opens one optic and exposes its layers. | Studio Small 09 HDRI and Metal Plate 02 PBR maps. |
| [Paper koi](../library/recipes/paper-koi.md) · `fold` | `draw(ctx,state)` develops a square into a fish and moves attached fins/tail through `unfold`, `swim`, `phase` and `bend`. | Original Canvas geometry and grain; no external hero asset. |
| [Jelly chair](../library/recipes/jelly-chair.md) · `contact` | `setState({squash,lift,bend,yaw})` compresses and recovers a continuous chair around grounded supports. | Studio Small 09 HDRI; original geometry and authored materials. |
| [Chrome beetle](../library/recipes/chrome-beetle.md) · `wing` | Case hinges, membrane unfolding, wingbeat and leg tuck have separate absolute controls. | Studio Small 09 HDRI; original insect geometry and veins. |
| [Liquid word](../library/recipes/liquid-word.md) · `liquid` | Editable font-derived glyphs become a connected pool through `liquefaction` and `phase`. | Locally loaded Sora variable font with its OFL. |
| [Botanical editorial](../library/recipes/botanical-editorial.md) · `botanical` | `render(ctx,state)` connects a supplied image's full hero, macros, strips and radial shutters. | A supplied/generated passionflower image; the component accepts another decoded image. |
| [Satin bow](../library/recipes/satin-bow.md) · `tie` | `setState({tie,cinch,flutter,phase,loopSpread,tailDrop})` gathers one continuous ribbon into loops and attached tails. | Studio Small 09 HDRI; original ribbon, grain and satin materials. |
| [Citrus slices](../library/recipes/citrus-slices.md) · `spiral` | `setState({separation,spiral,rotation})` opens matching rind sections into a helix and restacks one fruit. | Studio Small 09 HDRI and an original generated cut-face image; a procedural fallback is available. |
| [Toy planet](../library/recipes/toy-planet.md) · `train` | `setState({travel,trackProgress,landscapeProgress,pull})` links the train route to rising track and scenery; `trackFrame(turns)` supports attached staging. | Studio Small 09 HDRI; original ceramic world, railway and train geometry. |
| [Luminous jellyfish](../library/recipes/luminous-jellyfish.md) · `pulse` | `setState({pulse,phase,current})` contracts the bell while attached oral arms and threads lag behind. | Studio Small 09 HDRI; original anatomy, membrane shader and caller-owned glow. |
| [Checker zebra](../library/recipes/checker-zebra.md) · `gallop` | `draw(ctx,state)` develops a checkerboard into stripes and persistent limbs through `peel`, `phase` and `gallop`. | Original Canvas geometry and pattern; no external hero asset. |
| [Rotary telephone](../library/recipes/rotary-telephone.md) · `cord` | Body/receiver assembly, dial motion and `cordLoop` retain both cable endpoints. | Studio Small 09 HDRI; original molded telephone and helical cord. |
| [Glass staircase](../library/recipes/glass-staircase.md) · `cascade` | `setState({cascade,spread,settle,phase})` releases ordered tiles into radially oriented spiral treads. | Studio Small 09 HDRI; original beveled tiles and layered glass materials. |
| [Beach umbrella](../library/recipes/beach-umbrella.md) · `bloom` | `setState({bloom,pole,spin,ripple,phase})` connects a striped disc to its canopy, runner and braces. | Studio Small 09 HDRI; original geometry and caller-supplied woven grain. |
| [Ink octopus](../library/recipes/ink-octopus.md) · `ink` | `draw(ctx,state)` develops one drop into a mantle and eight attached arms through `form`, `phase`, `jet` and `curl`. | Original Canvas geometry and seeded ink texture; no external hero asset. |
| [Color zipper](../library/recipes/color-zipper.md) · `unzip` | `setState({open,flow,spread,pullTilt})` separates attached zipper edges while a continuous river flows underneath. | Studio Small 09 HDRI; original fabric weave, hardware and colored surfaces. |

Retrieve a complete recipe entry with `show ID --json` to read its interface, controls, `asset_requirements`, exact `example_prompt` and `example_source`. Component requirements and demonstration assets are separate: the chair does not contain an HDRI, and image-driven recipes do not contain or automatically generate their hero images. The [passionflower image prompt](../library/recipes/botanical-editorial-image-prompt.txt) and [citrus cut-face image prompt](../library/recipes/citrus-slices-image-prompt.txt) are available for creating new assets; their binaries belong in the project. Inspect each generated replacement before mapping or cropping it. The citrus procedural fallback establishes anatomy but did not supply the final film's photographic macro detail.

The `implementation`, `detail` and `example_source` paths resolve from the library directory. Copy the chosen module and demo HTML into an isolated project together, preserving their relative imports. Prepare that project's `assets/` and real local browser dependencies at the paths expected by the HTML. Do not serve a demo directly from the catalog root or put fetched binaries in the recipe directory. The renderer's `--deps` locates Puppeteer separately; it does not make an outside Three.js bundle available to browser imports. Follow [browser rendering](browser-rendering.md) for readiness, exact capture commands and packaging.

A demo owns its scene, camera, material choices and timeline; its source is an editable example, not a required visual style. The calling project decides whether to attach a soundtrack; the prompt ledger records sound provenance per batch, including intentional silence. A shared visual format does not imply a shared audio requirement. Before promoting a variation, inspect a real semantic edit such as weaker squash, partial case opening, another word or a different shutter count. Preserve source and asset hashes with the proof, and do not carry a previous render's QA claim across a source change.

## Grow by demonstrated need

Add a reference when an inspected sequence teaches a specific mechanism missing from the index. Record creator, date, media scope/timecodes, observation versus inference, asset roles, continuity and an original transfer. A URL without a motion observation is only a research lead. Keep low-confidence or inaccessible leads in project research notes until inspected.

Promote an asset only after decoding it, verifying item-level reuse terms, measuring files and proving its intended role. Promote an original recipe after a representative render, a meaningful control variation and deterministic backward/repeated seeks. Document known limits and ownership of geometry/material disposal. A recipe owns its behavior; the composition owns staging and time.

Extend this catalog and its nearby recipe files before creating another registry. Keep formal teaching assets under Manim's existing domain system. Keep discovery independent of the render and EDL helpers: the renderer receives a prepared project and does not search the library or download assets. Retrieve selected entries instead of loading the entire catalog into every prompt.

Research rationale and source comparisons: [motion-design-reference-library.md](../../../docs/motion-design-reference-library.md).
