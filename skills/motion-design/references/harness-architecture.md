# Motion harness architecture

## What the public evidence establishes

Higgsfield's [local application bridge](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp) exposes After Effects through a local MCP process, operating-system scripting, and a file mailbox, with separately served creative guidance. It also contains an independent Blender package. Its [September 2026 launch demonstration](https://x.com/higgsfield/status/2098409362041753708) visibly names GPT-6 Astra and After Effects. These are concrete public mechanisms, but the local repository does not establish every detail of the hosted service or the exact configuration of every promotional result.

The bridge's [design planning](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-design-first/SKILL.md), [build orchestration](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-build-orchestration/SKILL.md), and [validation guidance](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/skills/ae-clean-rig/references/09-validation-delivery.md) describe an inspectable production loop: plan geometry and content, verify a component in the real renderer, assemble dependencies, animate, inspect output, and package an editable result. Its [provenance notice](https://github.com/higgsfield-ai/fnf-local-pluging-bridge-mcp/blob/main/UPSTREAM.md) distinguishes the runtime's MIT license from its skill corpus. The workflow below is independently authored for video-use; do not vendor that corpus under an assumed runtime license.

## Map mechanisms to this repository

| Mechanism | Local equivalent | Artifact that proves it |
|---|---|---|
| Inspect the original visual evidence | Timecoded reference observations or an authored hero design | Reference frames and a short design contract |
| Discover available native capabilities | Read installed renderer APIs and helper `--help`; check asset/font availability | Exact runtime and dependency versions |
| Define meaningful objects | Named functions, DOM groups, scene objects, and explicit content inputs | Component or scene specification |
| Prove a component before repetition | Render its ordinary and extreme poses with the actual material/type | Component stills and a focused motion test |
| Assemble controlled relationships | Shared values and parents drive the related elements | Scene with editable content and clear controls |
| Build intentional motion | Explicit phase timing, curves, camera, and persistent object identity | Seekable animation with beat times |
| Inspect rendered results | Deterministic captures plus encoded-video QA and artistic review | Proof frames, video, QA report, repair notes |
| Package editable delivery | Local source/assets, lockfile, runtime requirements, and commands | Reproducible project plus final MP4 |

The architecture does not require an After Effects adapter to improve browser-rendered motion. It does require equivalent visibility into the actual output. If the requested deliverable is an editable AEP or Blender project, use that native toolchain instead of presenting an HTML project as equivalent.

## Build dependencies in a useful order

Start with the uncertain visual subject. A material study needs a believable lit surface; kinetic type needs its actual font and extreme poses; a data animation needs values and geometry that agree. A rough complete storyboard cannot prove any of those details by itself.

Describe component inputs before multiplying it: content, dimensions, anchors, material, and controllable phase. Render one representative component in the scene's intended camera or nested scale. Once its appearance and behavior work, assemble instances and relationships. This avoids reproducing the same defect across an entire film.

Keep static layout separate from the time-varying controls. For example, the text width can be measured once while a reveal phase controls its mask; the camera can move without changing the object's authored geometry. Use shared parameters for parts that must stay synchronized. Test ordinary and boundary values when the project advertises editable controls.

Expose named content, style, and motion inputs rather than scattering the same editable value across drawing code. A manual control should produce its stated pose without needing the demonstration clock to run first. In a native timeline tool, keep those controls independent of optional autoplay keys; in a browser scene, separate control evaluation from the function that maps film time onto those controls. Do not advertise an interactive rig if the delivered project exposes only hard-coded playback.

Delegate independent shots, asset creation, or a focused critic pass when those jobs can proceed without conflicting writes. Give each job the creative contract, assets, coordinate/frame convention, required poses, and owned paths. Reassemble shared scene behavior in one controlled place. More agents do not help when every worker silently chooses a different type system or camera grammar.

## Repair at the smallest responsible level

Classify the visible failure before changing anything:

1. **Input:** missing asset, wrong font, incorrect source value, or poor hero image.
2. **Component:** incorrect glyph fit, seam, surface, anchor, or local effect.
3. **Relationship:** parent transform, camera projection, z-order, synchronized phase, or dependency shared with other instances.
4. **Timing:** onset, velocity, overlap, cut boundary, or hold.
5. **Whole direction:** the premise or composition fails even when its mechanics work.

Fix the responsible source and inspect its consumers. A bad seam should not cause a blanket blur; a local text change should not recenter an unrelated scene; a critique of pacing should not replace approved material. Preserve a previous render for regression comparison and compare the changed result against the intended design separately.

A renderer failure can also be environmental. During the PLAY demonstration, browser GPU canvas text caching produced different pixels for repeated seeks even though animation state was absolute. A CPU canvas path and renderer diagnostics resolved the repeatability failure. Diagnose the saved expected/observed frames before weakening the deterministic check or randomizing the animation to hide it.

## What this does not prove

Passing this production loop establishes a reproducible artifact with inspected evidence. It does not prove parity with a curated commercial showcase. Use stable briefs and blind preference comparisons across held-out work to test quality improvements. Model identity, prompt complexity, or number of review rounds is not a substitute for that evidence.
