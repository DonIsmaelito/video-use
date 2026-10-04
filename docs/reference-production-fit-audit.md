# Reference production fit audit

Audited October 3 2026 against `feature/curated-video-references`, following the
reference-cloning implementation in commit `446ce22`. Fixes are isolated on
`fix/reference-production-fit` because another agent was editing the release
files during verification.

## What was inspected

The repository indexes 73 gallery entries and 85 provenance records. Seven owned
R2 videos were downloaded through authenticated storage access. Their SHA-256
hashes matched the saved provenance. FFprobe checked actual streams/durations;
six evenly spaced decoded frames per video were visually inspected. Saved review
reports and prompts were read where present. This was not normal-speed audiovisual
playback, a fresh production render, or a latency benchmark.

| Example | Observed mechanism | Boundary |
| --- | --- | --- |
| MAKE ROOM, 14s | Letterform deformation and negative-space composition | Historical Modal SVG/browser render; silent, with revisions |
| Paper Current, 18s | Connected river path through paper/photo collage | Historical Modal render; needs prepared image assets |
| Porcelain Bloom, 10s | Small sculptural object with radial petals | Historical local browser output; no proof of complex environments |
| Night Tram, 10s | Illustrated city layers, tram and graphic reflections | Canvas illustration, not photoreal 3D |
| Toy Planet, 8s | Stylized original meshes and connected train/track | Authored Three.js recipe, not a city simulation |
| Binary Search, 20s | Readable array comparisons and labels | Audio exists; original renderer/prompt not established by this audit |
| Vertical Reframe, 13.61s | Footage crop, cutdown and phrase captions | Historical Modal edit of supplied footage, not synthetic actors |

The machine-readable ledger in
`video_use_mcp/pilot/references/production-evidence.json` retains exact output
URLs, hashes, prompt provenance and limits. Local audit media/frame sheets are in
`/tmp/video-use-production-audit`; they are not required by production.

## Current production boundary

The worker image declares FFmpeg, Chromium, Puppeteer, Canvas/SVG, Manim 0.19.x,
TeX and Three.js. It is CPU-only and production networking is blocked. Blender,
CAD conversion, native generative-video providers, signed-in app capture and
runtime CDN/package fetching are not available. Narration has separate provider
and allowance dependencies. Installation is not a current-worker readiness probe.

Reference selection now receives this evidence before searching. Every newly
recommended work needs inspected image/video evidence and a production plan:
renderer, defining treatment, supporting evidence IDs, needed assets, adaptations
and confidence. Runtime-only support is explicitly `requires_sample`. A historical
example supports its particular mechanism, not exact similarity or rendering time.
The host still judges artistic fit; the validator checks evidence identities and
method compatibility, not a fabricated similarity score.

Search remains fresh and brief-specific. The ledger is internal evidence, not a
bank of references to repeatedly offer. A Blender credit alone does not disqualify
a simple object that can be recreated in Three.js. A realistic city cannot be
promised from the evidence of a toy planet. Material adaptations must be disclosed
before selection and demonstrated in the short snippet.

## Cloning review and repair

The new clone workflow downloads the selected source, stores it, and asks the host
to measure timing, composition and motion before adapting the user's subject.
That is useful source analysis; it does not supply a new renderer.

Fixed a failed handoff manifest write marking production ready, and cached retries
that could not repair it. Readiness now includes successful handoff persistence;
retry restores and verifies saved assets before rebuilding it. Downloads can use
the existing browser-verified media URL while retaining the source page attribution.

Remaining boundary: acquisition accepts a complete video up to ten minutes and
200 MB, not a remote slice of a longer film. Guidance now discloses this before
offering such a source. A checksum verifies byte transfer, not that an uploaded
or extracted video is the intended work; the host must inspect identity/content.
No end-to-end new Claude generation or fresh paid reference download was performed
as part of this audit.

Validation: the isolated pilot suite passed 1001 tests with 9 environment-gated
skips. No deployment was performed from this branch while the other agent was
changing the shared release. Existing Claude sessions were not modified.
