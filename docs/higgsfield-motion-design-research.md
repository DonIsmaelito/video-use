# Higgsfield motion design and a stronger video use harness

Higgsfield's September 2026 motion-design examples are best explained by a capable agent working with strong visual references, specialized design knowledge, native editable scene construction, and repeated rendered inspection. GPT-6 Astra is explicitly part of the current workflow. More significantly, a public repository under Higgsfield's organization exposes the local After Effects adapter and a substantial creative skill corpus. The central architecture is therefore partly inspectable, although the exact production configuration behind each promotional film remains unknown.

The three supplied X references show the newer **AI Motion Designer for ChatGPT and After Effects**, not simply the older Vibe Motion browser application. This distinction changes the implementation lesson: preserve the design and review loop while choosing an engine appropriate to the available environment. Adobe After Effects is absent from this machine. The implemented browser renderer can exercise the same observable production loop for original graphics, UI, and 3D work, but its output is not an editable AEP and its visual equivalence to the promotional examples has not been established.

Research was conducted on 13 September 2026. Claims below are labeled through their context: downloaded pixels are observations, vendor documentation describes vendor claims, source files establish the behavior of that public implementation, and proposed improvements are recommendations. Selected marketing clips establish a quality target; they do not establish average first-pass performance.

## The supplied examples

The original X pages were not readable through the web text surface. Public embed metadata supplied their canonical text, timestamps, and original video.twimg.com media locations. All three videos were downloaded from those original CDN locations and inspected through decoded frames and contact sheets. No account rotation or rate-limit evasion was used.

### Illustrative expressions reel

[Higgsfield X post](https://x.com/higgsfield/status/2098879968617140532), 12 September 2026, 21:02:34 UTC. Duration 9.968 seconds, original 2160×2160; analysis copy 1080×1080. 

The post frames the agent as handling expressions while the designer keeps providing creative input. The reel presents six simultaneous square illustration scenes above AE and ChatGPT views: a checkerboard/chess piece, layered pink floral/abstract geometry, tarot-like floating cards, rotating fish, an exploded fruit shape, and a radial heart composition. Strong purple, blue, pink, and pale-yellow relationships tie the grid together. Individual subjects build up, rotate or settle; the 10-second reel repeats a sequence around halfway through. Multiple AE layers are visible. The pixels support a workflow involving editable compositions and repeated animation systems; they do not reveal how assets were created or how many revisions preceded the example.

### AI Motion Designer launch

[Higgsfield X launch](https://x.com/higgsfield/status/2098409362041753708), 11 September 2026, 13:52:33 UTC. Duration 81.966 seconds, 1920×1080. Also published as [Higgsfield AI Motion Designer | ChatGPT x After Effects](https://www.youtube.com/watch?v=_J41U1ceZLA), 11 September 2026. 

The post explicitly says the plugin understands animation principles, writes expressions, and retains AE project context. The film depicts a music-platform year-end campaign evolving through animated typography, generated performer imagery, a mascot, then replacing that mascot with a supplied sketch. It demonstrates aspect-ratio adaptation and Japanese localization before packaging. A visible project panel groups work into `01_REFERENCES`, `02_ASSETS`, `03_PRECOMPS`, and `04_MASTERS`. These are useful public workflow clues: assets are separate from compositions, existing direction is preserved during changes, and final delivery includes an organized project. The film is an edited promotional narrative, so its elapsed production time and intervention count are unknown.

### Dragonfruit editorial demo

[Higgsfield AI X post](https://x.com/higgsfield_ai/status/2098824969124004135), 12 September 2026, 17:24:01 UTC. Duration 20.1 seconds, 2160×2160. 

The post explicitly names GPT-6 Astra plus the Higgsfield plugin. The upper panel shows a dragonfruit editorial film; lower panels show AE layers and a continuing chat. The design mixes acid-lime chapter fields, near-black macro frames, occasional warm-white backgrounds, very tall condensed typography, photographic fruit, and a growth-stage sequence. Selection rectangles become graphic motifs; loosely looping curves connect growth stages. Wet glass/macro treatments supply material contrast against the graphic typography. The shown revisions preserve the opening and redirect subsequent growth content. This is evidence for persistent project revision and mixed-media design, not proof that the entire film came from one unassisted prompt.

## Public local harness source

A targeted repository search found [higgsfield-ai/fnf-local-pluging-bridge-mcp](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp), publicly accessible under Higgsfield's organization on 13 September 2026. The main-branch commit query returned `d91306e4aba0078f7cd98e44fb580625e8c63b2e` (2026-09-12T16:47:11Z); its bundled manifest lists 11 skills and 34 documents. This substantially reduces the need to speculate: the repository includes a local After Effects MCP runtime, creative skill source, and a separate Blender adapter. The README maps a desktop MCP client to a local stdio process, OS scripting, a file mailbox, and AE. It describes 12 discovery/inspection/action/render/skill tools; offline skill retrieval is separate from actual AE operations. Local mode needs installed licensed AE and operating-system permissions but no Higgsfield account or cloud relay. This is the public local implementation; identical configuration in the promotional examples has not been proved.

The [primary AE skill](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-clean-rig/SKILL.md) is a router, with sixteen focused references and nine companions. It requires project inspection, capability discovery, a backup for structural changes, original-reference analysis, a semantic object/motion plan, native editable construction, sparse intentional animation, representative renders, and an actual content/control edit before delivery. Its media distinction is particularly useful: exact text/UI/diagrams stay native; generated material is used for photographic or footage content. It treats a text-only brief as weak and offers storyboard/reference/explicit invention routes. An autonomous original brief can explicitly authorize the invention route; no extra approval requirement follows merely from studying this corpus.

The [design-first module](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-design-first/SKILL.md) specifies a scene model of geometry, typography, colors, sources, and controls before detailed motion. It builds one representative native component and renders it before assembling the whole scene. It distinguishes HTML previews, native AE objects, Lottie, and project JSON, and rejects claims of equivalent appearance without comparing rendered output. The actionable lesson is to check the design system on one real component before multiplying a weak pattern.

The [build-orchestration module](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-build-orchestration/SKILL.md) uses small verified batches in dependency order: content sources, component geometry, hierarchy, controls, expressions, keys, effects. It separates constant layout from animation controls and tests values at boundaries and typical settings. Errors require inspecting partial work before retrying; an undo group is not a database transaction. In our web implementation, stable asset IDs, pure time evaluation, resumable scene renders, and bounded patches can provide the equivalent reliability.

The [animation-principles module](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-animation-principles/SKILL.md) records moving and stationary elements, beats, destinations and attention intent. It asks for reference-supported timing rather than arbitrary wobble, sparse keys with deliberate interpolation, physically related anticipation/overshoot/settling, and shared controls for related parts. It distinguishes time interpolation from spatial tangents and expression code from scripting code. Validation includes fastest motion, extrema, settled states, and seam velocity, at delivery timing. These instructions explain why a general-purpose agent can be made more reliable through a focused motion vocabulary and explicit checkpoints.

The [reference-motion guide](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-clean-rig/references/02-reference-motion.md) goes beyond aesthetic adjectives: retain original frame identities and presentation timestamps, separate camera/object/deformation/light causes, map contact and pivot points, inspect both sides of cuts, and preserve nonzero handoff velocity when an action continues. It warns against applying generic easing to every key or restarting an action after a match cut. It also contains concrete regression lessons from prior examples, evidence that accumulated failure knowledge is a meaningful part of the corpus.

The [editable-rig guide](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-clean-rig/references/06-editable-rigs.md) requires meaningful source identity, useful named controls, independent manual transforms, and testing a longer phrase, alternate asset, or changed parameter during animation. It distinguishes artwork reuse from playback reuse: a complete pose and an entrance animation must remain separately accessible when multiple shots share the same source. This is a precise fix for common generated-video regressions that source-code compilation cannot detect.

The [validation/delivery guide](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-clean-rig/references/09-validation-delivery.md) compares current output both to the reference and to the previous accepted version, inspects shared-source consumers, diagnoses gaps/banding/fonts/media, checks actual duration and exported decode, and packages dependency-complete editable work. It explicitly separates sampled technical checks from visual acceptance. The [UI guide](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-ui-mastery/SKILL.md) adds unified visual tokens, optical alignment, a dominant message, restrained metadata, and final-size legibility.

Licensing matters for direct copying: [UPSTREAM.md](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/UPSTREAM.md) attributes the runtime to the MIT-licensed kumo.productions project, but explicitly excludes the FNF skill instructions from that upstream MIT grant and provides no additional redistribution license. The recommendation is to cite the corpus and independently implement the observed methods, not copy its prose wholesale into our distributed skill. Public access also does not establish that this snapshot is the exact launch version.

## Model claims and the older product

Higgsfield's [GPT-6 Astra MCP guide](https://higgsfield.ai/blog/higgsfield-mcp-gpt6-astra-games-2), 7 September 2026, explicitly separates responsibilities: Astra handles coding, logic, reasoning, and orchestration; Higgsfield produces creative assets and supplies connected workflows. Although Games 2.0 is the main example, the page explicitly extends the model to motion graphics, animation, 3D modeling, rigging and reconstruction. This supports the user's model hypothesis for current workflows. It does not disclose a universal motion-design system prompt or establish that every example uses the identical model configuration.

Higgsfield's [agentic content guide](https://higgsfield.ai/blog/agentic-ai-for-content-creation), 15 June 2026, updated approximately late August 2026, describes an orchestrator selecting models per task, reasoning providers from several vendors, generative image/video tools, installable slash-command skills, and project memory/files. It lists a Motion Designer agent with 43 skills. The skill count is a marketing claim; the public AE corpus above provides concrete instructions, although it does not establish the full marketplace inventory. The reusable-skill and persistent-project architecture is nevertheless an explicit first-party description.

The official [MCP page](https://higgsfield.ai/mcp), undated/current, advertises a Motion & Design skill category and routes coding agents toward the [public CLI repository](https://github.com/higgsfield-ai/cli). The CLI is an asset-generation integration surface. It is distinct from the public native AE adapter above; a generative model catalog should not be confused with a compositing engine.

Higgsfield's earlier [AI Motion Design landing page](https://higgsfield.ai/ai-motion-design), undated/current, advertises code-based graphics, user SVG/logo/media inputs, motion presets, editable text/color/timing/easing, and exports up to 4K. Its public hero reel shows an Anthropic partnership label. The landing page itself does not identify Remotion. Repeated third-party Remotion claims are insufficient to establish the current AE product's implementation. Earlier descriptions should not be silently carried forward to the September launch.

## The detailed YouTube workflow

[GPT-6 Astra + Higgsfield MCP Made This ENTIRE Video in One Chat](https://www.youtube.com/watch?v=NuvA32_dmtg), Higgsfield AI, 6 September 2026. Metadata and public captions were retrieved for the chaptered analysis.

This is a stronger workflow source than a launch slogan. It starts with four existing inputs: a presenter video, an After Effects project, a render of those motion graphics, and a finished YouTube style reference. Its chaptered workflow covers a production brief, script/takes, presenter consistency review, meaningful visual demonstrations, AE motion graphics, Resolve editing, sound, and final export checks. Around 7:32 it describes using editable existing compositions and reusable finished animation, guided by dark backgrounds, lime accents, bold labels, and short readable titles. Near the end it calls for inspecting the actual export for gaps, unreadable text, speech problems, duration, and consistency. Therefore “one chat” does not mean “no reference assets,” “no template,” or “no review loop.” An established visual system is a substantial input.

For historical context, [Jake In Motion's public Vibe Motion reproduction test](https://www.youtube.com/watch?v=Kw3jM8DtWBo), 6 March 2026, describes reusing launch prompts and assets and encountering variable outcomes. That test addresses the older product and cannot establish the quality of the September AE integration. It does justify measuring distributional quality rather than treating selected promotion as a baseline success rate. No current quantitative head-to-head quality evaluation was found.

## Open systems that strengthen the portable design

### HyperFrames production architecture

HyperFrames is an HTML/CSS/media renderer driven through seekable browser animation. Its repository separates the composition contract, animation, keyframes, creative direction, asset resolution, audio, command execution, and registry discovery. This is relevant because the renderer is only one part of the system; task-specific knowledge is loaded separately. Its declared render path seeks headless Chrome and encodes with FFmpeg. This provides a publicly inspectable analogue for a prompt-to-code motion product, not proof of Higgsfield's internals. [HeyGen HyperFrames repository](https://github.com/heygen-com/hyperframes)

### A concrete Director and Builder workflow

The public short-motion workflow first drafts a shot plan, conditionally resolves assets, then finalizes the design around the assets that actually exist. A Builder writes the composition, followed by linting, runtime checks, and selected proof snapshots. Snapshot times must show the opening, signature motion, and end state. Repair runs on failed gates. The transferable feature is the intermediate shot plan and artifact-based handoff: do not ask one prompt to invent the concept, discover assets, implement, and decide its own quality invisibly. [HyperFrames motion-graphics skill](https://raw.githubusercontent.com/heygen-com/hyperframes/main/skills/motion-graphics/SKILL.md)

### Video composition knowledge is distinct from web design

HyperFrames explicitly distinguishes brand tokens from their presentation in a video frame. Colors and fonts may remain fixed while typography scale, density, spacing, shadow strength, and border weight change for the medium. A valid webpage can be a weak video frame because thin borders and small UI text do not survive viewing size and compression. This directly targets the common output of a coding agent: a centered landing-page composition animated with fades. [HyperFrames video composition reference](https://raw.githubusercontent.com/heygen-com/hyperframes/main/skills/hyperframes-creative/references/video-composition.md)

### House style is useful but can create a new monoculture

The public house-style reference asks agents to question repeated cards, equal-weight centering, neon defaults, and unmotivated gradient text. It also specifies decorative background layers and preferred type behavior. The first principle is useful; the fixed aesthetic prescriptions should not be imported wholesale. Requiring every frame to breathe with glows, ghost text, and particles would simply replace one generic look with another. The local harness should demand a reason for the treatment and judge the rendered result. [HyperFrames house style](https://raw.githubusercontent.com/heygen-com/hyperframes/main/skills/hyperframes-creative/references/house-style.md)

### Rhythm and motion continuity need written decisions

The beat-direction reference separates hard cuts, CSS transitions, and shader transitions by editorial purpose. It plans rhythm from the message and brand, and describes matching the outgoing acceleration with incoming deceleration. Its broad transition vocabulary is useful as capability discovery. The recommendation is not to enforce its numeric quotas or use shaders automatically: record focal subject, motion direction, timing, and the reason for the cut. [HyperFrames beat direction](https://raw.githubusercontent.com/heygen-com/hyperframes/main/skills/hyperframes-creative/references/beat-direction.md)

### Deterministic keyframes are an agent feedback interface

HyperFrames keyframe guidance treats animation as a sequence of visible poses with persistent subject identity. It uses paused, registered timelines and forbids wall-clock sources for render-critical state. This matters beyond reliability: if the critic says the subject is unreadable at 4.2 seconds, the builder must reproduce precisely that frame. A local `seek(seconds)` contract can provide the same property without tying every composition to one framework. [HyperFrames keyframes skill](https://raw.githubusercontent.com/heygen-com/hyperframes/main/skills/hyperframes-keyframes/SKILL.md)

### Remotion official skills distinguish timing from implementation style

The current official markup skill drives animation through `useCurrentFrame()` and interpolation, warns that native CSS timing does not follow its render clock, and supports custom Bézier and spring timing. It routes separately to text measurement, effects, 3D, audio, and media guidance. That supports a renderer-specific mechanics reference rather than a universal rule such as “always cubic.” Note that the older `skills/remotion/SKILL.md` path returned 404 during this audit; the current official monorepo path is below. [Remotion markup skill](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/skills/skills/remotion-markup/SKILL.md)

### OpenMontage carries creative direction through the entire pipeline

OpenMontage has an explicit taste profile with the intended design impression, visual variation, motion intensity, information density, palette discipline, references, and anti-patterns. Its downstream planning, asset prompts, composition, and review are expected to use that same profile. A particularly useful diagnostic asks whether the piece could serve an unrelated topic merely by changing its title. The transferable insight is a persistent creative contract, rather than reliance on vague adjectives such as “cinematic” or “premium.” [OpenMontage taste direction](https://raw.githubusercontent.com/calesthio/OpenMontage/main/skills/meta/taste-direction.md)

### Reusable mechanics and authored creative decisions are different

OpenMontage's bespoke-composition route deliberately separates renderer knowledge from finished scene components. It calls for a subject-specific visual metaphor and a per-scene plan before authoring, with still renders before final export. This is a useful counterweight to template libraries. Some rules in that source are too absolute for general adoption: a recurring subject can be essential to continuity, and shared brand components can be appropriate. Preserve original composition decisions while freely reusing reliable mechanics. [OpenMontage bespoke composition](https://raw.githubusercontent.com/calesthio/OpenMontage/main/skills/meta/bespoke-composition.md)

### LogoMotion provides empirical evidence for visual grounding and repair

LogoMotion analyzes layers, hierarchy, grouping, and a design concept before producing animation code. Its expert evaluation reports higher relevance for the full system than its ablation and Canva Magic Animate, while sequencing and execution were comparable. Its repair experiment reports a 0.96 solve rate with image context versus 0.82 without it after four attempts. These results concern detected layout errors in logo animations, not general film quality. Repair compares expected and rendered layer position, scale, rotation, and opacity, using isolated image pairs. The practical lesson is to combine objective geometry checks with targeted visual feedback, while evaluating creative quality separately. [Liu et al., LogoMotion, CHI 2025 / arXiv version 2](https://arxiv.org/html/2405.07065v2)

### Motion Canvas makes choreography explicit

Motion Canvas expresses animations as generator functions and flow generators, enabling sequential and concurrent motion. This provides another code representation for a beat plan. Its existence is relevant to the architecture decision: a harness can preserve semantic timing and object relationships independently of React or HTML. Migrating the current repo to Motion Canvas is not necessary to gain that benefit. [Motion Canvas flow documentation](https://motioncanvas.io/docs/flow/), [Motion Canvas tweening documentation](https://motion-canvas.io/docs/tweening/)

### GSAP supports richer motion than generic easing snippets

GSAP timelines group tweens and nested timelines, allowing global timing changes without rewriting isolated delays. MotionPath supports SVG paths, coordinate arrays, arbitrary property trajectories, and orientation along a path. These capabilities are useful for designed movement that follows the shape or behavior of the subject. A richer vocabulary should include arcs, anticipation, overshoot when appropriate, controlled overlap, and continuous camera trajectories. It should not force one easing family onto all motion. [GSAP timelines](https://gsap.com/docs/v3/GSAP/gsap.timeline%28%29/), [GSAP MotionPath](https://gsap.com/docs/v3/Plugins/MotionPathPlugin/)

### Three.js material quality depends on lighting and environment

Three.js `MeshPhysicalMaterial` supports clearcoat, iridescence, transmission, anisotropy, and sheen. The official documentation recommends an environment map for best results and notes added per-pixel cost. This is directly relevant to premium abstract 3D: selecting “metallic” in a prompt is insufficient if there is nothing meaningful to reflect. Model material, scene illumination, camera, composition, and output transform must be designed together. [Three.js MeshPhysicalMaterial](https://threejs.org/docs/pages/MeshPhysicalMaterial.html)

### Small skill libraries are useful retrieval examples, not quality evidence

The iart-ai repository packages motion fundamentals, typography, composition, engines, and brand elements as separate skills. The claude-remotion-skill repository packages creation, sound, and rendering guidance. These are inspectable approaches to knowledge organization; neither README proves comparative output quality. Their useful lesson is progressive disclosure: route to the few references needed for the visual idea, rather than loading a long universal prompt containing every effect. [iart-ai motion-design-skills](https://raw.githubusercontent.com/iart-ai/motion-design-skills/main/README.md), [claude-remotion-skill](https://raw.githubusercontent.com/haidrrrry/claude-remotion-skill/main/README.md)

## Changes appropriate to this repository

The existing editor already isolates animation slots, supports several rendering approaches, tracks frame-aware edits, and has a rich Manim teaching workflow. Its general animation guidance is less explicit about concept selection and visual repair. A stronger motion layer can fit this structure without replacing clip editing or forcing every design into Manim.

The audit found three broad defaults worth narrowing: a universal cubic-easing preference, a blanket prohibition on simultaneous independent reveals, and a fixed end hold. Those are sometimes useful narration-overlay heuristics. Applied universally, they erase deliberate constant-speed movement, coordinated ensembles, loops, and fast brand stings. The specialized motion route should choose timing from the material, scene purpose, and reference evidence while maintaining one clear focal event.

A palette, font, and engine are insufficient as a creative brief. They can produce a technically correct but interchangeable promo. The new route adds the visible premise, a representative hero frame, a signature transformation, type and material roles, rhythm, asset strategy, and failure conditions. Asset inspection happens before the scene is committed; a visually weak hero should not be compensated for with extra effects.

| File | Role in the improved structure | Why it matters |
|---|---|---|
| `SKILL.md` | Parent route for clip editing and animation; delegates substantial design work | Keeps motion design in the normal editor workflow |
| `skills/motion-design/SKILL.md` | Concise production route from visual premise to editable source and checked export | Carries creative intent across implementation |
| `skills/motion-design/references/art-direction.md` | Reference observation, type hierarchy, materials, rhythm, and continuity | Gives the agent concrete design decisions before code |
| `skills/motion-design/references/harness-architecture.md` | Intent, representation, tools, visual feedback, and asset responsibilities | Separates transferable production methods from a particular engine |
| `skills/motion-design/references/browser-rendering.md` | Absolute-time scene evaluation, asset readiness, and capture | Makes authored web scenes reproducible at named timestamps |
| `skills/motion-design/references/critique.md` | Separate technical checks and artistic critique, with timecoded repair briefs | Prevents codec success from being reported as aesthetic success |
| `helpers/motion_render.mjs` | Exact-time local HTML/CSS/SVG/canvas/WebGL capture and H264 encoding | Makes visual feedback reproducible across revisions |
| `helpers/motion_qa.py` | Full video/audio decode, delivery validation, review images | Checks the actual encoded artifact and surfaces suspicious intervals |
| `tests/test_motion_render.mjs` | Renderer contract and argument/path behavior checks | Protects deterministic rendering and local asset handling |
| `tests/test_motion_qa.py` | Meaningful delivery validation checks | Keeps technical acceptance tied to measured media properties |

The renderer accepts `window.seek(seconds)` and an optional `window.motionReady` promise. Asset and font readiness precede capture; render-critical state must not depend on wall-clock playback or previous frame order. It checks repeated/out-of-order seeks, captures representative stills, encodes the complete sequence, and records source/asset evidence in a manifest. Remote assets are blocked by default so the saved composition can be reproduced from local files.

The QA helper decodes the exported video, checks the delivery contract, and creates images from encoded frames. Flat intervals, near-identical frames, and large changes are review cues rather than universal failures: an intentional hold or hard cut can be correct. Required width, height, frame rate, duration, frame count, codec, and audio properties belong in the technical contract. Aesthetic claims require viewing the result.

The architecture can later expose native AE or Blender tools behind the same intent-level operations: inspect the project, render a named time, patch a semantic object, verify a content change, and package dependencies. Replacing the entire working renderer is unnecessary to learn from native AE construction. Avoid direct copies of FNF skill prose; the repository additions are independently authored guidance grounded in the cited techniques.

## The recommended creative operating loop

A practical agent harness separates responsibilities but need not create a separate model call for every step. For a small correction, the existing composition supplies most of the contract. For original or unfamiliar work, explicit intermediate artifacts materially improve review.

1. **Reference analysis.** Save canonical sources and classify each as original reference, approved result, or defect screenshot. Record composition, hierarchy, subject scale, typography, material, camera, motion direction, holds and cuts. Keep observations separate from guesses about implementation. Use sparse sheets for navigation and original consecutive frames for decisive timing.
2. **Art direction.** Consider distinct concepts where exploration can improve the piece. Select a premise whose visible behavior belongs to the subject. Specify the strongest frame and the event that transforms it; choose palette and typography roles to serve that event. Preserve the contract in project memory.
3. **Asset preparation.** Resolve or generate the hero asset, then inspect it. Bind exact files, dimensions, alpha behavior, and provenance into the project. Generate photography, illustration, or footage where it adds quality; retain exact type and interface geometry in a controllable representation.
4. **Representative construction.** Build one meaningful component and render its ordinary and extreme states. Correct proportions, type, light, and framing before propagating that system. Construct sources, object geometry, hierarchy, controls, motion, and effects in a dependency order that can be inspected after failure.
5. **Choreography.** Give important objects stable identities, explicit anchors, and shared controls for shared gestures. Record what stays still. Preserve position, shape, velocity or another meaningful property across transitions; use a deliberate cut when continuity is unnecessary. Add physical timing only where it improves the intended behavior.
6. **Render and critique.** Inspect opening, representative pose, fastest action, transition boundaries, settlement, and end state. An independent critic can assess the actual images/video against the contract, identifying a small prioritized set of timecoded visible defects. Model judgments remain hypotheses to inspect.
7. **Localized repair.** Patch the smallest affected object/time range, preserve accepted work, and rerender the matching timestamps. Review shared-source consumers after changing a component. Test at least one real content or parameter change where editability is part of the promise.
8. **Finish and delivery.** Review the completed video with sound at normal speed where available. Check the actual exported file and package editable source, local assets, proof images, and manifest. Record limitations and retain useful failure lessons without imposing one successful aesthetic on every future film.

A useful repair request identifies time, evidence, consequence, and action. For example: at 2.7 seconds the outgoing words overlap the incoming headline, obscuring the reading; complete the outgoing exit before the incoming text reveal and recapture the boundary. This is much more actionable than asking the builder to make the result feel expensive.

## Demonstrations and comparison limits

The five original studies accompanying this work intentionally use different visual mechanisms. They are demonstrations of the improved production route, not a controlled comparison with Higgsfield or with the previous harness. They do not copy the supplied fruit film, music campaign, or six-panel illustrations.

| Study | Visual mechanism | Quality question it exercises |
|---|---|---|
| PLAY | Acid/black kinetic typography and coordinated graphic movement | Can type behave as the main subject rather than a heading above cards? |
| ORBIT | Chrome identity and an object/camera/material relationship | Do reflection, light, silhouette, and framing work together? |
| AFTER RAIN | Fragrance imagery with a generated hero asset and precise graphic composition | Does asset quality carry the image while wording remains controlled? |
| FOLD | Warm copper sculptural transformation | Can the geometry and movement express a coherent material idea? |
| FLOW | The same spark transforms from an idea canvas to an editor interaction and playback | Do object identity, interface state, timing, and final brand payoff remain connected? |

FLOW provides a concrete documented repair example. Full-resolution frame review found a canvas overlapping the timeline, a brand mark colliding with the wordmark, and outgoing text crossing incoming text during the zoom. Each issue was corrected in source and rerendered. Its playhead was also aligned to the cursor's play action. The completed export is 1920×1080 at 30 fps for 15.000 seconds, with 450 decoded frames and matching 48 kHz stereo audio. The original procedural score combines soft plucks, bass, pulse, interaction ticks, and transition swells; its final measured loudness is -16.7 LUFS with -4.6 dBFS true peak and a fading finish.

Those measurements establish delivery correctness for FLOW, not taste. The source is editable JavaScript/canvas rather than a native After Effects project or a functioning SaaS interface. Frame inspection and technical decode were available during production; full subjective playback and direct matched-brief comparisons remain separate evidence. Other studies' individual manifests and QA reports are the appropriate source for their delivery specifications.

The final set contains 77 seconds: PLAY 14, ORBIT 16, AFTER RAIN 16, FOLD 16, and FLOW 15. All five exports use 1920×1080 at 30 fps with original stereo scores. Repeated-seek checks caught a Chrome canvas text-cache inconsistency; the renderer's CPU canvas path resolved it. A later export failure preserved the previous finished movie because encoding writes to a temporary file before replacement. Follow-up work added bounded browser shutdown and encoder errors that retain frame number and FFmpeg diagnostics. Seven Node and four Python regression tests passed, alongside real export and intentional-failure fixtures.

AFTER RAIN combines two original generated stills with an eight-second 1080p Veo 3.1 plate obtained through the configured OpenRouter account; its confirmed video-generation charge was $3.20. A separate Gemini 3.8 Flash critique of six ORBIT/AFTER RAIN proof frames cost about $0.0143. Its suggestions about thin-line contrast and busy backgrounds informed small repairs, but it incorrectly described an existing serif title as sans-serif. That recommendation was rejected after inspecting the pixels. This is a useful practical distinction: a critic supplies evidence to investigate, not a reliable automatic acceptance score. An earlier Astra critique request failed with a TLS error and produced no usable review.

The source references demonstrate richer illustration, compositing, macro material treatments, and native project depth than a basic HTML shape example can establish. Our studies intentionally test portable techniques under the existing environment. Reaching the full reference range will require sustained asset direction, native 3D/compositing when appropriate, and evaluation across more examples. Five attractive results cannot prove that the harness matches a commercial showcase distribution.

## Model choice and evaluation

The public evidence supports Astra's role in current Higgsfield orchestration. It does not identify a special private model, an exact reasoning-effort setting, or a universal sampling configuration. The documented asset/logic separation suggests matching models to roles: strong reasoning and code generation for planning/building, a vision-capable critic for actual renders, and specialized image/video models for assets that benefit from those modalities. A stronger model can improve invention and repair, but it cannot compensate automatically for an absent reference or weak visual premise.

The useful model experiment holds briefs, assets, engine, and review procedure constant. Log model identifier, provider, reasoning settings when available, attempts, cost, and generation/render time. Different prompts and source images confound model comparisons. Respect provider limits through queues, retry-after handling, backoff, and permitted paid capacity.

A focused next evaluation should compare several independently repeated outputs per brief, not one lucky render. Use five brief families—typography, product/material, UI, information design, and illustration/collage—plus a second held-out set not used while authoring the skill. Keep duration/aspect, required copy, assets, and cost accounting stable. Where output sampling exists, retain all attempts and explain selection; cherry-picking only successful runs disguises the actual failure rate.

Run ablations that isolate the likely contributions: baseline model with the old route; stronger model with the old route; the same model with art direction and representative stills; then the same setup with deterministic proof frames and independent critique. A final condition can add generated hero assets or a native renderer. This separates model gains from visual-grounding, review, and engine gains.

Use blind pairwise review for concept, composition/type, choreography, material finish, and coherence, alongside factual/technical failures and total cost. Ask reviewers to name the visible reason for a preference. The generating model's composite score is not independent evidence. Improvement should mean sustained preference across held-out briefs with fewer visible failures, while exact Higgsfield parity would require comparable tasks, input assets, iteration budgets, and uncurated outputs from both systems.

## Evidence archive and remaining unknowns

The local evidence archive is `/private/tmp/higgsfield-motion-20260913/edit/research/`. It contains three X metadata JSON files with canonical CDN video URLs, decoded contact sheets, the launch and full-workflow YouTube metadata/captions, the earlier landing-page snapshot/reel, the CLI README, and the public local bridge snapshot plus commit metadata. The rendered studies and source live under `/private/tmp/higgsfield-motion-20260913/edit/films/`. These temporary paths are evidence locations for this run; the reusable production guidance and helpers live in the repository paths listed above.

The important unknowns are the complete deployed system prompt, exact skill revision for each promotion, internal model routing/settings, human art-direction contribution, failed attempt count, and the average quality of ordinary user generations. Public code establishes real mechanisms and public tutorials reveal significant prepared inputs. Neither establishes that every finished promotional frame was created autonomously in one attempt.

Preserve an editable representation, supply visual context before coding, make important frames observable, and turn critique into bounded source changes. These methods are portable today; native AE fidelity and commercial parity remain claims to test.
