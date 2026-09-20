e# Video editing tools research and roadmap

Status: research and implementation plan only  
Date: 2026-09-04  
Scope: video-editing intelligence, helpers, references, timeline semantics, and context routing

No editing feature is implemented by this document. It defines the integration baseline, the repository extraction queue, and the gates that should be satisfied before new editing tools ship.

## Executive decision

Video Use should not absorb a desktop NLE or replace FFmpeg with a large editing engine. Its advantage is that an agent can reason about an edit, produce a small declarative handoff, and invoke purpose-built tools. The next architecture should preserve that advantage while making four changes:

1. Keep FFmpeg as the default executor, but stop making `helpers/render.py` carry every timeline concept itself.
2. Normalize the agent-authored EDL into an OpenTimelineIO-compatible internal timeline before rendering.
3. Store expensive media observations as content-aeddressed, queryable analysis sidecars instead of prompt prose.
4. Route a small invariant context core plus only the capability cards required by the task, media, and installed runtime.

The first implemented external primitives should be PySceneDetect plus runtime discovery of the FFmpeg capabilities already installed. OpenTimelineIO should enter with the normalized timeline phase, after the integration and context/analysis foundations exist. MLT should be prototyped as an optional renderer only after that internal timeline is stable. OpenColorIO and a Revideo-versus-HyperFrames evaluation are valuable later routed backends. Kdenlive, Shotcut, Flowblade, Blender, OpenShot, and LosslessCut are primarily design and algorithm references because their full application code or dependency graph is not a clean fit for the current MIT-oriented Python core.

The immediate prerequisite is an integration branch. There is currently no single branch containing the five submitted feature PRs, the latest local GUI agent drivers, Modal rendering, the uncommitted R2 work, and the two competing Manim additions.

## Evidence baseline

This plan assumes the following submitted PRs will land:

- [#145 agent guidance and contract guards](https://github.com/browser-use/video-use/pull/145)
- [#146 Manim teaching assets and chapter previews](https://github.com/browser-use/video-use/pull/146)
- [#147 EDL v2, deliverables, overlay layouts, and caption provenance](https://github.com/browser-use/video-use/pull/147)
- [#148 sourced footage, illustration engines, and layout QC](https://github.com/browser-use/video-use/pull/148)
- [#151 local Whisper transcription](https://github.com/browser-use/video-use/pull/151)

`preview/merged-main` at `92b5138` is the best local approximation of that future baseline. It contains the final tips of all five feature branches. It does not contain the latest local GUI/Claude work, Modal/R2 integration, or the current dirty-only Manim narration additions.

The submitted PRs are stacked, not flat: `#145 -> (#146, #147, #151)` and `#147 -> #148`. Descendant branches must be rebased after upstream merges, especially if GitHub squash-merges a parent, or an integration can duplicate the parent’s commits.

### Branch and infrastructure facts

| Layer | Best available source | Important fact |
|---|---|---|
| Upstream base | `origin/main` at `9575612` | Includes rotation-aware portrait detection and silent-audio rejection during transcription. |
| Submitted feature stack | `preview/merged-main` at `92b5138` | Integrates all five submitted PR tips and is the planning baseline. |
| Agent GUI | `feature/gui-lane-server` at `9971737` | Adds local Codex and Claude sessions, approvals, model selection, and four lanes; it is based on older feature snapshots and its Claude server integration is broken. |
| Modal renderer | `feature/gui-modal-runs` at `71dc67f` | Validates and renders staged EDLs in Modal. It does not run the editing agent. |
| Object storage | current uncommitted GUI/R2 files | Publishes unauthenticated video/poster copies through `R2_PUBLIC_BASE_URL`; the Modal run tree remains until deletion, and `render.log` is also downloaded into local durable history. |
| Manim additions | `feature/manim-teaching-assets` plus dirty worktree | The branch has layout/protected-region semantics; the dirty worktree has a separate `TimedScene`, narration-alignment, and narration-preflight implementation. |
| Native editor | upstream [#138](https://github.com/browser-use/video-use/pull/138) | Useful AVFoundation preview and edit-log work, but it moves the Python package and conflicts with the submitted helper branches. |

Codex and Claude currently run on the local host, not inside Modal. The local agent produces `edit/edl.json` and its assets; only then is the project uploaded for remote validation and FFmpeg rendering. A single generic key is not needed for this planning work. Live R2 verification requires five R2 settings locally and in the Modal secret `video-use-r2`. Claude needs its own local authentication path. Before rollout, the product must explicitly choose public artifacts versus signed/private delivery.

There is also a known GUI-tip integration defect: the lane runner passes `network_access` to both agent drivers, while `FreshClaudeSession.run()` does not accept that argument. That must be fixed before treating the Claude lane as usable.

## Intended post-integration product model

No committed ref currently implements this entire pipeline, but the combined local work intends:

```text
task plus media
    -> isolated local Codex or Claude edit session
    -> transcript and on-demand visual evidence
    -> agent-authored EDL and generated assets
    -> local EDL validation
    -> Modal Volume staging
    -> remote FFmpeg render and verification
    -> R2 video and poster plus durable local evidence
```

This separation is good. The missing layer is between “task plus media” and “agent-authored EDL”: there is no router that decides which editing knowledge, evidence providers, or backend cards the agent needs.

### Capabilities to preserve

| Area | Existing implementation | What it already does well |
|---|---|---|
| Transcript-led editing | `helpers/transcribe.py`, `helpers/transcribe_batch.py`, `helpers/pack_transcripts.py` | Word timestamps, diarization/audio events with Scribe, an optional explicitly selected local Whisper engine in PR #151, and a compact phrase reading view. |
| Focused visual inspection | `helpers/timeline_view.py` | Filmstrip, waveform, word labels, and silence candidates for a selected source window. |
| Deterministic rendering | `helpers/render.py` | Per-segment extraction, audio fades, stream-copy concat, overlays, captions-last composition, HDR-to-SDR handling, and loudness normalization. |
| EDL contracts | `helpers/edl.py` from PR #147 | Validates sources/ranges, v2 deliverables, loudness, reframe declarations, and caption provenance. |
| Delivery and overlay contracts | `helpers/render.py` from PR #147 | Builds output-timeline subtitles, validates overlay layouts/protected regions, and renders named outputs. |
| Captions | integrated and dirty `helpers/captions.py` variants | PR #147 converts timed words or ElevenLabs alignment to ASS; the dirty implementation separately provides configurable output-timeline SRT and deterministic PIL rendering. Both capabilities need one API. |
| Explainer visuals | `helpers/web_source.py`, `helpers/render_illustration.py`, `helpers/layout_qc.py` from PR #148 | Provenance-aware public footage acquisition, Penrose/CeTZ rendering, and declared layout collision checks. |
| Original Manim explainers | `skills/manim-video/` from PR #146 | Semantic teaching objects, domain components, chapter planning, selective previews, and measurable legibility checks. |
| Reproducible evaluation | `benchmarks/` | Codex-first tasks, trace/cost collection, media validation, and comparison reports. |

## Limitations that constrain edit quality

### 1. No coherent integration target

The active checkout mixes an older committed base with modified and untracked versions of EDL, renderer, captions, visuals, GUI, benchmarks, R2, and Manim code. `preview/merged-main` is coherent for the submitted PRs but lacks the GUI and storage work. `preview/harness` is an obsolete merge of earlier snapshots.

This is more than branch hygiene: different layers currently assume incompatible renderer options and caption contracts. For example, the GUI invokes multi-deliverable renderer flags that the active checked-out renderer does not expose.

### 2. Isolation is being mistaken for context routing

`AgentWorkspaceFactory.prepare()` gives each run a clean project and framework copy. Codex explicitly disables project instruction loading, apps, plugins, memories, hooks, multi-agent, skill discovery, host skills, and configured MCPs. Claude clears settings and MCP sources, but does not provide an equivalent OS-level sandbox or explicit multi-agent disable. Neither driver proves it cannot read host credentials. The harness provides useful context isolation, not a complete security boundary.

It is not routing:

- Every run receives the entire root `SKILL.md`.
- The full framework tree is available.
- The model must notice prose such as “read this reference when doing X.”
- `gui/task_context.py` labels the result after EDL creation; it does not select initial context.
- Clean-room rules are duplicated across generated `AGENTS.md`, Codex developer instructions, the Claude system prompt, and task prompts. Codex sets `project_doc_max_bytes=0`, so its generated project `AGENTS.md` is not itself an active input; the duplication still creates source-of-truth drift.
- Multi-agent is disabled by the GUI while the skill still instructs the editor to spawn parallel animation agents.
- The root skill requires interactive strategy confirmation, while the GUI clean-room prompt requires one-turn completion without follow-up questions.

On the integrated feature preview, the root skill is about 31 KB. The nested Manim skill and references add thousands of lines. Adding more tool documentation to this shape will increase both missed instructions and irrelevant reading.

### 3. The timeline is still a hard-cut list

EDL v2 improves validation and delivery, but its core edit remains ordered source ranges with global overlays. It does not natively model:

- separate linked or unlinked audio/video edits for J-cuts and L-cuts;
- video and audio tracks, gaps, nested sequences, or multicam synchronization;
- transitions with source handles;
- time remapping, speed ramps, freezes, reverse, or optical-flow requirements;
- effect keyframes and reusable automation curves;
- music, ambience, sound effects, buses, ducking, fades, and mix automation;
- masks, tracked objects, stabilization data, or effect scopes.

These should not be added as unrelated top-level EDL fields. They need a normalized timeline and named data model.

### 4. Media evidence is narrow and not reusable

The agent can read speech and request a timeline PNG. It cannot query a durable index of scenes, motion, faces, framing, beats, black frames, freezes, focus failures, duplicate shots, or technical defects. Tracked reframing can consume keyframes in PR #147, but nothing in the repository generates those keyframes.

The current principle that only the packed transcript deserves to persist is too strict for the next phase. The better boundary is: persist only content-addressed evidence that is expensive to recompute, queryable without loading it all, and records provider/configuration provenance.

The existing transcript path also has three correctness gaps:

- Cache reuse is based on the transcript filename existing, not a source fingerprint; replaced media with the same stem can silently reuse stale words.
- `takes_packed.md` exposes phrase endpoints rather than every word timestamp, so it cannot alone support arbitrary filler-word cuts while satisfying the word-boundary rule.
- EDL validation does not mechanically verify cut edges against transcript word boundaries/padding, source duration, or declared `total_duration_s`.

### 5. Render work is repeated and coarse

- Segments are re-extracted sequentially on each render.
- There is no operation hash, segment cache, dirty-range invalidation, or proxy state machine.
- A small overlay or caption change can trigger another broad encode.
- “Lossless concat” still follows full per-segment re-encodes; there is no GOP-aware smart-copy planner.
- Multiple outputs repeat expensive work that could be shared.
- In the integrated renderer, long-edge scaling can still give mixed-orientation segments incompatible dimensions before stream-copy concat, and `extract_segment()` always applies an audio filter, so a video-only source fails. VFR, rotations, data streams, and alpha codecs also rely on scattered special cases rather than a source manifest and compile plan.
- One global subtitle artifact/configuration is reused across deliverables, so 16:9 and 9:16 outputs cannot independently optimize wrapping, safe regions, typography, or placement.

Upstream [#150](https://github.com/browser-use/video-use/pull/150) demonstrates the immediate value of source-level probing: caching two facts per source reduced 81 probes to 5 on its fixture. Upstream [#153](https://github.com/browser-use/video-use/pull/153) covers mixed-orientation montage inputs, silent/still sources, and basic music beds. Both should be reviewed against the integrated renderer rather than independently reimplemented.

### 6. Creative audio is largely absent

Current audio is source audio plus boundary fades and final loudness normalization. `build_final_composite()` maps only base audio, so overlay/B-roll audio, natural sound, and reaction audio are discarded. There is no first-class music/SFX/ambience model, beat grid, sidechain ducking, dialogue cleanup, mix buses, or track-level automation. Upstream [#39](https://github.com/browser-use/video-use/pull/39) is an older proof of concept for sidechain ducking and librosa beat timestamps; #153 is a better-tested base for music beds but does not replace a complete audio timeline.

### 7. Color handling is corrective rather than managed

Current HDR detection recognizes only PQ/HLG transfer metadata and hardcodes a Hable-to-Rec.709 path. It does not model primaries, matrix, range, camera log, working space, creative/display/output transforms, or verify final color metadata. The source manifest needs a minimal color contract before OCIO becomes an execution backend.

### 8. Quality checks validate files more than edits

The benchmark validator covers decoding, geometry, duration, codec, audio presence, approximate level, and subtitle artifacts. Layout helpers validate declared rectangles. The rest of self-evaluation is prose. There is no executable batch for cut-boundary continuity, caption visibility, overlay critical frames, black/freeze detection, A/V drift, pacing, shot repetition, or achieved loudness per deliverable.

## Repository landscape and extraction decisions

“Extract” has four meanings in this plan:

- **Adopt**: use a permissively licensed library as a dependency.
- **Adapter**: invoke a separately installed executable or runtime through a narrow contract.
- **Port**: copy or translate a small permissively licensed primitive with attribution and tests.
- **Reimplement**: reproduce documented behavior or architecture without copying incompatible source.

| Repository or engine | License and fit | Valuable primitive | Decision |
|---|---|---|---|
| [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) | Apache-2.0; Python; does not render | Rational time, clips, gaps, tracks/stacks, transitions, markers, media references, nested compositions, adapters, and bundles | **Adopt with Timeline IR.** Keep video-use effect schemas; pin separately packaged [OpenTimelineIO-Plugins adapters](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/main/docs/tutorials/adapters.md) independently and report lossy mappings. |
| [FFmpeg](https://ffmpeg.org/ffmpeg-filters.html) | LGPL/GPL depends on build | Installed filter/encoder/format/hardware discovery, analysis filters, timeline commands, stream mapping, and render execution | **Keep as default engine.** Generate a live capability catalog and compile typed operations to it. |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | BSD-3-Clause; Python; API still evolving | Content/adaptive/threshold/histogram/hash scene detectors and reusable per-frame stats | **Adopt first and pin `<0.8`.** Persist metrics so thresholds can change without decoding again. |
| [auto-editor](https://github.com/WyattBlue/auto-editor) | Unlicense core; current runtime boundaries need version review | Audio/motion/black/subtitle detectors, interval boolean algebra, margins/minimum-duration morphology, action labels, and timeline export | **Reimplement the small interval layer and adapt detectors.** Do not couple Video Use to its complete runtime. |
| [MLT](https://github.com/mltframework/mlt) | LGPL core; GPL executables/components require distribution care | Producers, playlists, multitrack tractors, filters, transitions, consumers, XML, and runtime service queries | **Prototype after Timeline IR.** Compile a limited conformance corpus to MLT XML and invoke `melt` as an optional backend. |
| [Kdenlive](https://github.com/KDE/kdenlive) | GPL-3.0 desktop app over MLT | Dirty preview chunks, proxy benchmarking, effect zones, stabilization, and motion-track-to-keyframe workflows | **Reference only.** Reimplement cache and named-analysis behavior; use MLT services for execution. |
| [Shotcut](https://github.com/mltframework/shotcut) | GPL-3.0 desktop app over MLT | Content-derived proxy IDs, pending-job sentinels, original/proxy mapping, capability metadata, and analysis jobs | **Reference only.** The proxy state machine is the main extraction target. |
| [Flowblade](https://github.com/jliljebl/flowblade) | GPL-3.0 Python app over MLT | Named tracking artifacts, tracked masks, stabilization, rendered speed media, and persistent render queues | **Reference only.** Standardize named analysis sidecars and queue semantics independently. |
| [GStreamer Editing Services](https://gstreamer.freedesktop.org/documentation/gst-editing-services/) | LGPL-2.1-or-later; native/GI stack | Layers versus output tracks, ripple/roll/trim constraints, transactions, automatic overlap transitions, preview/render pipelines | **Defer runtime adoption.** Independently reimplement its useful edit-operation constraints or add a later adapter; do not copy it into the core. |
| [Pitivi](https://github.com/pitivi/pitivi) | LGPL-2.1-or-later frontend to GES | Proxy lifecycle, persisted waveforms/thumbnails, and audio alignment | **Reference only.** Use GES directly if that backend is ever selected. |
| [libopenshot](https://github.com/OpenShot/libopenshot) / [OpenShot](https://github.com/OpenShot/openshot-qt) | LGPL-3.0 library and GPL-3.0 UI; normal `libopenshot-audio` dependency is GPL-3.0/commercial-dual | JSON Timeline/Clip/Effect/Keyframe objects, incremental JSON diffs, tracked objects, and cache epochs | **Reference only unless a GPL/commercial choice is explicit.** Independently implement patch/provenance and cache-epoch concepts. |
| [Blender VSE](https://developer.blender.org/docs/features/sequencer/) | GPL-3.0 application | Multi-stage caches, dependency invalidation, proxies, retiming curves, integrated 3D, compositor, and camera animation | **Optional adapter.** Invoke Blender headlessly only for routed 3D/compositor work. Reimplement cache/retime concepts. |
| [LosslessCut](https://github.com/mifi/lossless-cut) | GPL-2.0 | Stream mapping, metadata/chapters, scene/silence/black analysis, and GOP-boundary smart cuts | **Reimplement behavior with FFmpeg.** Use its smart-cut edge cases to define the codec/container test matrix. |
| [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) | BSD-3-Clause | Explicit source/working/display/output spaces, ACES configs, LUT baking, optimized processors, and transform cache IDs | **Adopt as a routed color layer.** Record a color contract and execute baked transforms through FFmpeg where possible. |
| [libplacebo](https://github.com/haasn/libplacebo) | LGPL-2.1-or-later | High-quality GPU scaling, HDR tone/gamut mapping, debanding, dithering, and shader hooks | **Capability-gated adapter.** Prefer an installed FFmpeg `libplacebo` filter before adding native bindings. |
| [VapourSynth](https://github.com/vapoursynth/vapoursynth) | LGPL-2.1-or-later | Lazy Python frame graphs and mature restoration/deinterlace/denoise plugins | **Optional restoration adapter.** Pipe `vspipe` into FFmpeg for archival or damaged sources. |
| [GPAC](https://github.com/gpac/gpac) | LGPL-2.1-or-later | Container surgery, ISOBMFF metadata, chapters, fragmented MP4, DASH/HLS, and packaging | **Optional packaging adapter.** It is not a general editor. |
| [PyAV](https://github.com/PyAV-Org/PyAV) | BSD-3-Clause source; current wheels can bundle a GPL-enabled FFmpeg build | Exact packet/frame PTS/DTS, rational time, side data, decoded arrays, and filter graphs | **Optional precision adapter.** Build against the controlled system FFmpeg or record the resulting binary’s GPL status; do not assume wheel licensing from PyAV’s source license. |
| [HyperFrames](https://github.com/heygen-com/hyperframes) | Apache-2.0; HTML/CSS/GSAP; already advertised by Video Use | Deterministic browser-frame capture, validation/linting, UI motion, typography, alpha WebM, and agent-oriented authoring | **Keep as the incumbent web-motion backend.** Establish measured baseline behavior before choosing another engine. |
| [Revideo](https://github.com/midrender/revideo) | MIT; TypeScript/headless | Generator scenes, dynamic inputs, partial-range rendering, worker parallelism, audio/video scheduling, and progress events | **A/B prototype against HyperFrames.** Compare alpha, partial renders, validation, cold start, context burden, and output quality before assigning preference. |
| [Motion Canvas](https://github.com/motion-canvas/motion-canvas) | MIT | Generator-coroutine animation, reactive signals, scene graph, vector/code/LaTeX nodes | **Reference or adapter only.** Revideo currently offers the clearer headless rendering path. |
| [Remotion](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) | Source-available with commercial conditions; not OSI open source | Mature React composition, templates, audio/video scheduling, and render sharding | **Do not extract.** Keep optional use only when license eligibility is explicit. Prefer Revideo for an OSS backend. |
| [Editly](https://github.com/mifi/editly) | MIT; lower current activity | Compact edit schema, sequential clips plus layers, GL transitions, Ken Burns, resize modes, and general layer scheduling | **Fixture and schema reference.** Video Use overlaps on cuts, overlays, and some resize behavior, but not its transitions, Ken Burns motion, or broader scheduling model. |
| [OpenCut](https://github.com/OpenCut-app/OpenCut) | MIT; active ground-up rewrite | Promising Rust core, Editor API, plugins, MCP, and headless roadmap | **Monitor.** Re-evaluate after a versioned headless API and conformance tests exist. Do not build on roadmap-only contracts. |
| [Omniclip](https://github.com/omni-media/omniclip) / [Omnitool](https://github.com/omni-media/omnitool) | MIT; browser/WebCodecs; reusable engine is still WIP | Millisecond JSON timeline, typed filter/transition registries, sequence/stack builders, interpolation, browser captions, background removal, and progress streams | **Study and selectively port permissive utilities after tests.** Do not make the server renderer depend on the unstable browser runtime. |
| [Mediabunny](https://github.com/Vanilagy/mediabunny) / [WebAV](https://github.com/WebAV-Tech/WebAV) | MPL-2.0 and MIT browser media libraries | Streaming mux/demux, microsecond time, WebCodecs probing, clip/sprite/combinator abstractions | **Future browser-preview references.** They should not displace server FFmpeg now. |
| [BMF](https://github.com/BabitMF/bmf) | Apache-2.0; native graph framework | Packet/module graphs and efficient decode-inference-encode pipelines | **Architecture reference.** Benchmark only when several GPU analysis stages make repeated decode a measured bottleneck. |

### Tracking provider spike

Tracked reframing needs a producer, not just an EDL field. Before choosing one stack, benchmark a permissively licensed shortlist:

- [OpenCV](https://github.com/opencv/opencv) (Apache-2.0) for optical flow, classical trackers, motion metrics, and geometry;
- [MediaPipe](https://github.com/google-ai-edge/mediapipe) (Apache-2.0) for face/person detection and landmarks;
- [Norfair](https://github.com/tryolabs/norfair) (BSD-3-Clause) for lightweight temporal association over detector outputs;
- [SAM 2](https://github.com/facebookresearch/sam2) (Apache-2.0 repository; verify each checkpoint) only when mask propagation materially beats box tracking.

The spike must compare face/person coverage, temporal jitter, occlusion recovery, CPU/GPU cost, model licensing, and conversion to normalized reframe/mask keyframes. Avoid an AGPL/commercial detector dependency unless that product decision is explicit.

## Proposed architecture

### A. One canonical source of runtime instructions

Split runtime knowledge into four routed layers:

1. **Invariant core**: project boundaries, strategy/approval policy, EDL handoff, correctness rules, and verification obligations.
2. **Intent cards**: small workflow packs such as talking-head cleanup, montage, interview, product demo, sourced explainer, original technical explainer, or restoration.
3. **Capability cards**: one concise card per verified operation, including inputs, outputs, restrictions, cost, backend, and reference pointer.
4. **Failure cards**: codec-, platform-, and backend-specific recovery context loaded only after a matching validation failure.

One resolved instruction bundle should be the source of truth. Each driver must inject it through a channel that driver actually consumes: the attached skill/developer input for Codex, the system prompt for Claude, and project `AGENTS.md` only for clients configured to load project instructions. Their current hand-written duplication should disappear.

Planned repository artifacts:

| Planned artifact | Responsibility |
|---|---|
| `context/core.md` | Small non-negotiable editing and safety contract. |
| `context/routes.yaml` | Task/media/output predicates mapped to intent and capability cards. |
| `context/cards/*.md` | Concise agent-facing procedures and judgment guidance. |
| `context/failures/*.md` | Narrow recovery knowledge keyed by validator error codes. |
| `helpers/context_router.py` | Resolve an initial task/media route and a later timeline/backend/failure route. |
| `helpers/capabilities.py` | Probe FFmpeg, MLT, Manim, Node backends, color tools, hardware, and models. |
| `edit/context_receipt.json` | Persist exactly which cards, versions, fallbacks, and budgets were supplied to a run. |

Routing should have two stages:

1. **Initial route** from the submitted task, an inexpensive source manifest, user-requested targets, and available capabilities. This cannot depend on agent-authored deliverables that do not exist yet.
2. **Post-EDL route** from the normalized timeline, actual deliverables, chosen operations, and validator error codes. This selects backend and failure cards.

The router should output card IDs and paths, never concatenate an unbounded tool catalog. A route receipt makes missed context debuggable and gives the benchmark harness a measurable independent variable.

#### Example routes

| Task | Load | Do not load by default |
|---|---|---|
| Talking-head cleanup | core, transcript cutting, captions if requested, delivery, FFmpeg renderer | Manim, web sourcing, Penrose/CeTZ, beat editing, restoration |
| Music montage | core, scene/motion analysis, beat grid, audio mix, transitions, delivery | full transcript craft and Manim unless speech or diagrams are present |
| Original technical explainer | core, narration, Manim teaching, illustration, layout QC, sourcing, delivery | interview/multicam and restoration packs |
| Archival restoration | core, source diagnostics, VapourSynth/FFmpeg restoration, color, delivery | animation and social-caption design packs |

### B. Agent-facing EDL plus normalized Timeline IR

Do not discard EDL v2. Keep it as the concise agent handoff and backwards-compatible public format. Add a normalization stage that converts v1/v2 into a stricter internal timeline aligned with OpenTimelineIO semantics.

The internal model should include:

- rational time and half-open source/output ranges;
- explicit media references and stream selection;
- video and audio tracks, clips, gaps, stacks, and nested compositions;
- linked and unlinked A/V source ranges for J/L cuts;
- transitions with verified source handles;
- rate, reverse, freeze, and keyframed time transforms;
- typed effects and animation curves;
- named references to analysis artifacts such as tracks, masks, beats, scenes, and stabilization transforms;
- deliverable-specific layout, captions, color, loudness, and codec policies.

OpenTimelineIO should own time/composition semantics and interchange, not backend effect meaning. Video Use effects should remain namespaced and compile through an adapter selected by capabilities.

Planned artifacts:

| Planned artifact | Responsibility |
|---|---|
| `helpers/timeline.py` | Normalize EDL v1/v2 and validate timeline invariants. |
| `helpers/otio_adapter.py` | Import/export supported OTIO constructs and report lossy mappings. |
| `helpers/edit_ops.py` | Ripple, roll, slip, slide, split, link/unlink, and transition-handle operations. |
| `tests/fixtures/timelines/` | Golden timing, transition, nesting, and round-trip cases. |

### C. Queryable analysis sidecars

Every analyzer should implement the same lifecycle:

```text
probe -> analyze -> persist -> summarize -> query -> invalidate
```

Each sidecar records:

- media fingerprint and exact stream identity;
- analyzer name, version, model hash, and configuration;
- time base;
- scalar metrics or labeled intervals;
- confidence and evidence pointers;
- creation time and parent artifact hashes.

Dense frame metrics should stay out of the model context. The agent should call a query helper for questions such as “show high-motion landscape shots between 2 and 6 seconds,” “find a clean reaction after this sentence,” or “return beat-aligned scene boundaries.” Results should be short, timestamped, and traceable.

Initial providers:

1. Source manifest from one `ffprobe` pass, including stream identity and a minimal source color contract.
2. PySceneDetect metrics and scene intervals.
3. FFmpeg silence, black, freeze, crop, interlace, and loudness observations.
4. A low-cost OpenCV/auto-editor-style motion metric provider.
5. auto-editor-inspired interval algebra for union, intersection, inversion, margins, minimum-duration fill, and label precedence.
6. Beat grid and musical sections.
7. Face/subject boxes and track keyframes after the tracking spike.
8. Optional quality observations such as blur, exposure clipping, and duplicate frames.

Planned artifacts:

| Planned artifact | Responsibility |
|---|---|
| `helpers/media_manifest.py` | One normalized technical/color probe and source fingerprint. |
| `helpers/analyze.py` | Provider registry, content-addressed cache, and query CLI. |
| `helpers/intervals.py` | Small tested interval and label algebra. |
| `edit/analysis/index.json` | Compact artifact registry and summaries. |
| `edit/analysis/<source-id>/` | Versioned provider sidecars and dense metric files. |

### D. Tool adapter contract

Each optional editing backend should expose the same six operations:

1. `probe`: version, license mode, build flags, installed services, hardware, and known restrictions.
2. `describe`: concise typed capabilities for routing.
3. `validate`: reject unsupported timeline constructs before paid or long-running work.
4. `compile`: create a deterministic execution plan without executing it.
5. `execute`: run with structured progress and artifact hashes.
6. `inspect`: verify output properties and backend-specific failure conditions.

The agent should select semantic capabilities such as `scene.detect`, `audio.duck`, `subject.track`, or `color.ocio_transform`, not application names such as Kdenlive or Blender. Backend selection happens after the capability is chosen.

### E. Incremental render planner

Build a render plan that classifies every timeline interval as one of:

- direct stream copy;
- remux only;
- boundary-GOP re-encode plus stream copy;
- video-only re-encode while copying unaffected audio/data streams;
- cached segment reuse;
- full composition.

Cache keys should include source fingerprint, exact rational range, stream mapping, normalized operation graph, tool versions, and output codec settings. A timeline diff should invalidate only affected ranges and downstream compositions.

The LosslessCut smart-cut design, Kdenlive preview chunks, Shotcut proxy lifecycle, Blender cache stages, and libopenshot cache epochs are the reference set. No GPL application source needs to be copied.

## Prioritized extraction queue

### Phase 0 — integration and contract lock

Goal: produce one trustworthy baseline before adding tools.

Before integration, preserve each dirty-only slice separately: R2/storage, Manim timing/narration, caption/visual/renderer changes, and benchmarks. Preserve the local GUI branches too. Work in a new worktree; do not build the integration by mutating this dirty checkout.

Default decision for upstream #138: defer its `src/video_use` packaging migration. The PR is currently conflicting/non-rebaseable and would otherwise need to become the first path-migration step.

1. Establish the eventual upstream baseline containing PRs #145, #146, #147, #148, and #151 in their dependency order. Until then, use `preview/merged-main` only as a disposable reference. Resolve or explicitly accept outstanding PR review findings before locking the contract; #147 currently has actionable feedback.
2. Review #102 and #150 as focused candidates. Review #153 as a broad renderer/schema patch: port only required silent/still-source correctness in Phase 0, leave music/canvas semantics for Phase 4, and avoid duplicating #102 behavior already present in #138-derived code.
3. Write an explicit compatibility table and lock precedence, migration, and legacy behavior for PR #147 ASS/provenance versus dirty SRT/PIL captions; EDL-v2 deliverable geometry versus `treatment.canvas`; tracked versus static reframe; #138 `subtitle_style`; and #153 `canvas`, `music`, and `mute`. The caption implementations are complementary, not interchangeable, and must survive behind one caption API.
4. Make interactive and autonomous modes explicit: strategy approval versus the GUI’s one-turn policy, and parallel animation agents versus GUI-disabled multi-agent. These cannot both be global invariants.
5. Reconcile the branch Manim layout/protected-region work with dirty timing, alignment, and narration preflight without choosing either tree wholesale.
6. Replay only the GUI/Modal lineage after the obsolete EDL base (`fbb0e28..9971737`) onto the integrated baseline. Rebasing the whole branch would replay obsolete agent-guidance and EDL commits.
7. Decide whether Claude implements `network_access` semantics or the lane runner sends that option only to Codex. Test manual approval, auto-approval, and denied network access through the real server-driver boundary.
8. Apply the R2 patch semantically after schemas and GUI settle. Decide public versus signed/private artifacts, and add idempotent retry/partial-failure tests because deletion spans non-atomic Modal, R2, and local operations.
9. Regenerate `uv.lock` from the final dependency set. Build/deploy Modal only from a clean integration tree and record the source commit and image revision in every run trace.
10. Keep two test tiers: a deterministic hermetic suite with fake Codex, Claude, Modal, and R2 adapters; and opt-in credentialed smoke tests requiring local agent auth, a Modal profile, and all five R2 settings.

Exit gate: one clean branch; one renderer and caption contract; v1/v2 fixture equivalence; no GUI/Modal CLI mismatch; green hermetic Codex and Claude server paths; Modal dependencies matched to the locked contract; storage privacy decided; credentialed smokes documented; and no uncommitted code in deployment.

### Phase 1 — source manifest, context router, and capability inventory

Goal: make additional tools reduce context rather than enlarge the root prompt.

1. Add the inexpensive source manifest first: source fingerprint, streams, exact time bases, dimensions/rotation, audio presence, duration, and minimal color interpretation.
2. Probe FFmpeg and optional backend capabilities before routing.
3. Extract the mode-aware root skill core and move workflow-specific instructions into cards without deleting contract tests.
4. Implement the initial route from the task, manifest, user-requested targets, and capabilities; implement the post-EDL route from normalized operations, actual deliverables, and validator errors.
5. Inject one resolved bundle through each driver’s real context channel.
6. Persist the context receipt and expose it in benchmark/run summaries.
7. Add route tests asserting required and forbidden cards plus a maximum context-byte budget.

Exit gate: representative talking-head, montage, explainer, and restoration prompts each receive the expected minimal pack and produce the same or better benchmark results than the monolithic skill.

### Phase 2 — scenes, motion, and interval algebra

Goal: give the agent new editorial evidence without flooding its prompt.

1. Integrate pinned PySceneDetect behind the analyzer contract.
2. Add FFmpeg technical/signal detectors.
3. Add a low-cost OpenCV/auto-editor-style motion provider.
4. Implement interval algebra with property-based tests.
5. Expose compact timestamp queries and timeline-view batch rendering.
6. Persist provider provenance and cache invalidation facts.

Exit gate: the agent can find and compare scenes, silence, motion, black/freeze defects, and candidate cut boundaries without opening full sidecars or re-decoding unchanged media.

### Phase 3 — Timeline IR and OpenTimelineIO

Goal: unlock real edit semantics without growing unrelated EDL fields.

1. Normalize existing EDL v1/v2 into the internal timeline.
2. Add separate audio/video tracks, linking, gaps, and edit operations.
3. Implement one verified crossfade with explicit source handles.
4. Add OTIO import/export with explicit lossy-mapping reports and independently pinned adapter plugins.
5. Compile the supported subset back to the current FFmpeg renderer.
6. Keep old EDL fixtures byte- or frame-equivalent.

Exit gate: hard cuts remain backward compatible; J/L cuts, crossfades with handles, gaps, and nested overlays have golden timing and A/V-sync tests.

### Phase 4 — first creative tool pack

Goal: materially improve common edits before adding exotic engines.

1. Reconcile #153’s music bed, silent/still source, and fixed-canvas handling with EDL v2.
2. Promote music, dialogue, ambience, and SFX to audio tracks/buses.
3. Add sidechain ducking, clip/track fades, gain automation, and loudness reports.
4. Add beat and musical-section analysis as routed evidence.
5. Add richer transitions, speed/freeze operations, and per-effect keyframes to the FFmpeg compiler.
6. Run the OpenCV/MediaPipe/Norfair/SAM 2 tracking spike, select a licensed stack, then generate normalized reframe/mask keyframes. Do not leave reframe tracks as consumer-only schema.

Exit gate: a mixed-orientation music montage, a dialogue-plus-B-roll edit, and a social reframe render correctly from one timeline with deterministic mix and layout reports.

### Phase 5 — incremental rendering and proxies

Goal: shorten the agent’s inspect-adjust-render loop.

1. Add operation-hashed segment and analysis caches.
2. Render changed chunks only and assemble evaluable previews.
3. Add a crash-safe proxy state machine and hardware-specific proxy benchmark.
4. Prototype GOP-aware smart rendering behind a conservative codec/container allowlist.
5. Shard independent chunks in Modal only after local equivalence tests pass.

Exit gate: caption-only, overlay-only, and one-cut revisions reuse unaffected media; cache hits are visible in the run summary; smart rendering never activates outside its tested matrix.

### Phase 6 — specialized routed backends

Goal: add differentiated capability without burdening ordinary edits.

1. MLT XML backend for timelines that are materially simpler there.
2. OpenColorIO and optional libplacebo path for explicit color-managed/HDR work.
3. Revideo backend for web-motion explainers and cards.
4. Blender adapter for 3D/compositor scenes.
5. VapourSynth adapter for restoration.
6. GPAC adapter for streaming/package delivery.

Exit gate: each adapter has a capability probe, license record, compile-only plan, golden fixture, failure card, and a clean fallback to FFmpeg or a clear unsupported result.

## Benchmark plan

Extend the existing benchmark harness before judging any imported tool.

### Required workloads

| Workload | What it measures |
|---|---|
| Existing Jensen social edit | Transcript selection, captions, vertical delivery, and regression compatibility. |
| Same captioned edit in 16:9 and 9:16 | Deliverable-specific wrapping, typography, placement, safe regions, and shared editorial timing. |
| Existing GPU explainer | Routed Manim/illustration/sourcing context and critical-frame QC. |
| Mixed-orientation music montage | Scene selection, beat alignment, silent/still sources, music mix, transitions, and canvas behavior. |
| Interview with B-roll | J/L cuts, dialogue continuity, ducking, scene search, and source provenance. |
| Multicam conversation | Sync, linked/unlinked A/V, reaction selection, and nested timeline behavior. |
| HDR/log mixed-camera edit | Source interpretation, color transforms, shot matching, scopes, and delivery metadata. |
| Lossless trim/remux corpus | GOP boundaries, B-frames, VFR, rotations, chapters, subtitles, and multiple audio/data streams. |
| Restoration clip | Deinterlace, denoise, cadence, scaling, and restoration-backend routing. |

### Metrics

- task completion and validator pass rate;
- human preference on story, pacing, audio, composition, and technical finish;
- context bytes and card count supplied to the agent;
- required-card recall and irrelevant-card load rate;
- total tool calls, failed calls, and fallback count;
- analysis cache hit rate and decoded frames avoided;
- render wall time, compute cost, and percent of frames re-encoded;
- A/V sync, cut-boundary audio discontinuity, achieved LUFS/true peak, and output color metadata;
- source/operation/tool-version provenance completeness.

Every new tool should run as an A/B against the same task and baseline. A feature should not ship merely because it exposes more operations; it must improve output, reliability, iteration time, or agent context efficiency.

## Idea notebook

These are product directions surfaced by the repository comparison. They are not committed roadmap items.

### Near-term ideas

- **Editing lenses**: transcript, scenes, beats, faces, motion, audio events, and technical defects become query modes over the same timeline instead of separate giant reports.
- **Context receipt viewer**: each run shows why a card/backend was selected, what was omitted, and which fallback fired.
- **Named evidence tracks**: one subject track, mask, beat grid, or stabilization transform can drive several effects and deliverables.
- **Edit patches**: OpenShot-style small operations with author, reason, and undo provenance instead of replacing the whole EDL after each instruction.
- **Boundary review reel**: automatically render all cut boundaries into one contact-sheet/video artifact with waveform and caption/overlay states.
- **Pacing curve**: show shot duration, speech density, motion, and musical energy across the output so the agent can reason about rhythm without watching every frame.
- **Continuity warnings**: surface repeated frames, flash cuts, gaze jumps, background jumps, and implausible audio handoffs as evidence, not automatic edits.

### Medium-term ideas

- **Capability lockfile**: attach exact binaries, build flags, filters, encoders, model hashes, licenses, and fallbacks to every render.
- **Dirty-range preview**: compile timeline diffs to only the affected chunks and retain frame-accurate handles around them.
- **Proxy advisor**: benchmark the current machine/container once and select proxy codecs/resolutions from measured decode and seek performance.
- **Color contract**: record source interpretation, working space, creative transform, display transform, and delivery encoding rather than relying on metadata guesses.
- **Editorial macros**: reusable semantic operations such as “radio edit,” “reaction hold,” “cut on action,” “match dialogue,” or “beat montage” compile to timeline edits but remain inspectable and reversible.
- **Cross-deliverable composition solver**: use subject tracks and protected regions to produce independent 16:9, 1:1, and 9:16 compositions from shared editorial intent.
- **Evidence-aware B-roll suggestions**: rank local or sourced clips by narrative function, visual novelty, motion, aspect, and license/provenance rather than keyword similarity alone.

### Longer-term ideas

- **Renderer portfolio**: the same timeline compiles to FFmpeg, MLT, Revideo, Blender, or a browser preview, with an explicit unsupported/lossy report for each backend.
- **Edit critic loop**: a separate bounded evaluator queries the same evidence and challenges pacing, continuity, clarity, and audio choices without receiving all authoring context.
- **Successful-edit memory**: persist abstract decisions and measurable outcomes, not raw private media or task prose, so future routes learn which capabilities helped each workflow.
- **Live semantic preview**: a lightweight browser/native client plays the timeline and emits human edit patches that the conversational agent can explain, preserve, or revise.
- **GPU analysis graph**: if repeated decode becomes a measured bottleneck, use a BMF-like packet graph to share decoded frames across tracking, scene, OCR, and quality analyzers.

## Licensing and extraction rules

1. Maintain a ledger for every imported or adapted primitive: source repository, commit/tag, license, extraction mode, modifications, and attribution.
2. Do not copy GPL application source into the core. Use documented behavior, underlying LGPL engines, or external executable boundaries with distribution review.
3. Review LGPL dynamic-linking/distribution obligations and MPL file-level copyleft for each adapter. Record the licenses of individual MLT services, VapourSynth plugins, codecs, models, and browser packages; the engine’s core license does not cover its plugin ecosystem.
4. Treat FFmpeg licensing as a property of the exact build, not the project name. Record configure flags and enabled nonfree/GPL components.
5. Treat PyAV wheels as binary distributions whose bundled FFmpeg license may differ from PyAV’s BSD source license.
6. Do not extract Remotion code. Its optional use requires an explicit license decision.
7. Pin model and tool versions for reproducibility, but keep capability probes authoritative for the current local or Modal environment.
8. Require golden tests before translating an algorithm from another implementation, especially timestamp, GOP, color, and audio code.

## Decisions needed before Phase 0 implementation

- Whether PR #138’s `src/video_use` packaging is desired now or should stay independent from the editing-tool integration.
- Whether distributed builds may bundle GPL executables or must rely on user-installed external tools.
- Whether the public EDL should expose tracks directly in a future v3 or keep the richer Timeline IR internal at first.
- Which three workflows should define the first quality bar. Recommended: talking-head/social, music montage, and original technical explainer.
- Whether local agent execution is intentional long term or whether moving Codex/Claude into Modal is a separate future infrastructure project. The current code does not do that.

## Recommended next implementation slice

The next coding task should be Phase 0 only: preserve the dirty slices, build the canonical integration branch in a new worktree, reconcile renderer/caption/Manim contracts, transplant the GUI-only commits, fix the Claude lane behavior, apply R2 cleanly, and make hermetic tests green before opt-in live smokes. Do not add an external editing engine in the same change.

After that, implement Phase 1. Its source manifest, capability inventory, two-stage router, and context receipt create the boundary every later repository extraction can plug into, while immediately reducing repeated probes and making agent behavior measurable.
