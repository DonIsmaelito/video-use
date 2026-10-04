# Useful workflow library

This campaign adds 40 practical examples to the existing Video Use gallery, plus
a separate MCP launch film. The archived Whiplash edit is an additional entry
with a generalized **Starter prompt**; it is not presented as a new generation
or as proof that the starter text produced the original movie.

The live library is at https://video-use.insforge.site and the connection page
is at https://video-use.insforge.site/mcp. The website advertises the Video Use
repository and provides free prompts and reviewed editable sources.

The completed catalog has 114 entries: 73 existing examples, 40 new practical
workflows and the archived Whiplash edit. The separate MCP launch film runs for
28 seconds. The filter previously called **By Technique** is now **Video type**.

## How the parts connect

- `briefs.json` and the pinned source research define the practical use cases.
  Creative prompts remain separate from the production wrapper. Inspiration,
  copied code, licensed footage and original artwork have distinct credits.
- `experiments/useful_video_library.py` freezes the selected framework files,
  starts at most four creative containers, collects output, runs encoded-media
  checks and packages source. Each film keeps its actual producer commit and
  file hashes after later shared-tool improvements.
- `TOOL-GAPS.md` records which production findings became shared helpers and
  which stayed inside an editable example. New containers receive verified
  shared changes; existing films are not relabeled as having used them.
- `experiments/publish_useful_video.py` accepts an explicit review bound to the
  exact movie and source ZIP hashes. Generation containers cannot publish.
  Public asset downloads and byte-range playback are checked before catalog use.
- `website/scripts/import-reviewed-examples.mjs` imports those receipts into
  `website/data/examples.json` and `media-sources.json`. It preserves curated
  per-example playback metadata. `mcp-launch.json` selects the separate hero film.
- `website/lib/gallery.ts` supplies audience, use-case and video-type filtering
  and builds the chat handoff. A copied example retains the existing request's
  subject, brand, audience, format and involvement choices. The MCP workflow
  still asks for snippet acceptance when that interaction mode requires it.

## Review and replay

Review includes actual encoded frames and transitions, technical decoding,
semantic/data checks, original prompt verification, scoped licenses and replay
inputs. Relevant examples also receive geometry, caption timing, audio-level,
every-frame mask/disclosure, or content-substitution checks. A generated contact
sheet or passing technical check alone does not approve publication.

The recorded limits distinguish those checks from normal-speed audiovisual
audition and an independent fresh-machine full rerender. Dependency and native
versions are pinned where applicable; different platforms can rasterize or
encode differently. See each public review and source README for its evidence.

`REPLAY.md` defines the archive-root convention. Project READMEs provide the
exact commands, dependencies and media regeneration or licensed reacquisition.
Source ZIPs exclude private agent traces, credentials, raw media and generated
render caches. Recognized replay inputs and legal notices must be retained.

Large campaign outputs and immutable review/publication receipts live outside
the repository in the campaign's `edit` directory. The public source ledger
keeps the final media identity and links; deployment receipts record the exact
catalog release and hosted browser checks.

The final publication audit reconciles all 40 approvals with the catalog and
exact movie/source identities, rehashes the local source archives, and downloads
all 40 public source ZIPs and 40 public prompt files to verify their bytes.
It also checks the Whiplash starter prompt, MCP film and website-loop metadata.
The shared framework suite passed 1,506 tests and 61 subtests at `1bf8404`
(26 skipped); the subsequent dependency-lock change passed 38 focused archive
and publication tests at `c9aa3d1`. Website validation checks all 114 entries.
