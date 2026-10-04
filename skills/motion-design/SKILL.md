---
name: motion-design
description: Create original design-led motion graphics, kinetic typography, brand films, abstract 3D, and polished animated overlays. Use for motion design where composition, material, and choreography determine quality; use manim-video for formal teaching animations and the parent video-use workflow for clip editing.
---

# Motion design

Build a visual idea that merits movement, then verify its rendered execution. Preserve the user's brand, content, references, requested scope, and existing authorization. Open-ended creative freedom is permission to choose a direction and finish the work.

## Design before implementation

For substantial original work, read [art-direction.md](references/art-direction.md). Record a compact creative contract in the animation slot: subject or visual metaphor, intended impression, type and material roles, strongest frame, signature transformation, rhythm, and asset needs. Reference qualities should become concrete observations, not claims about an inaccessible private harness.

When exploration is useful, compare distinct concepts or hero stills before building the full sequence. Do not turn this into a compulsory approval step when the user already asked for autonomous delivery. Inspect generated or sourced hero assets before finalizing the composition around them.

When the concept needs visual precedents, external assets, or an original reusable mechanism, read [library.md](references/library.md). Search the compact catalog by action or asset role, then load only relevant entries. References supply observed relationships; downloadable assets supply inspected files; original recipes supply geometry and controls. Their availability should expand the choices, not impose a house style.

For prompt trials, preserve the exact short request separately from the expanded creative contract. Record the selected catalog IDs, actual asset provenance, and visible repairs beside the output. [Prompt examples](library/prompt-examples.json) connect exact requests to editable implementations; they are starting points to adapt, not default film templates.

For typography stories, mixed-media sequences, character performance, brand families, product/UI narratives, or sound-led films, read [creative-systems.md](references/creative-systems.md). These are overlapping creative approaches, not prompt categories that select fixed scenes. Earlier eight-second, single-hero trials are example-specific briefs; do not carry their length or no-copy restriction into unrelated work.

For a complex build, prove one representative component in the chosen renderer before assembling its repetitions and shared controls. Use this sequence where it reduces risk: visible reference or authored design → component specification → real rendered proof → scene assembly → detailed motion. Read [harness-architecture.md](references/harness-architecture.md) when structuring the build, delegation, or repairs.

## Build the appropriate representation

- HTML/CSS/SVG with direct time functions, or GSAP when installed: typography, graphic shapes, UI, collage, masks, and 2.5D.
- Three.js or another suitable 3D renderer: sculptural objects, real camera movement, material and lighting studies.
- Remotion when installed: an existing React composition system or React-based content makes implementation simpler.
- Manim: diagrams, equations, and formal explanations; load its skill when applicable.

Match this choice to the actual execution environment. The hosted Claude/ChatGPT
pilot bundles Chromium/Puppeteer, Three.js and Manim; GSAP, Remotion and Blender
are not bundled. Its render worker has no external network: use local assets and
direct time functions, not CDN imports or runtime installs. Local-machine projects
can use separately installed frameworks; those workflows do not establish hosted
availability. Procedural 3D needs a small working proof in the actual worker before
promising a complex reference treatment.

Reuse rendering, asset-loading, and timeline mechanics. Author the concept and layout for the piece. A component catalog can supply a suitable primitive; its availability should not decide the visual idea.

Keep each project under `edit/animations/slot_<id>/` or a similarly explicit isolated output directory. Store source, local assets, creative contract, rendered proof frames, and final video together. For direct browser compositions, expose a deterministic `window.seek(seconds)`; optionally expose a `window.motionReady` promise for assets and fonts. Every frame must be reconstructible without depending on previous playback. A framework's native deterministic clock is equally valid.

For the repository's direct browser renderer, read [browser-rendering.md](references/browser-rendering.md). It describes the actual helper commands, local dependencies, asynchronous asset readiness, deterministic inspection, and editable packaging.

Small optional building blocks live in [runtime.md](references/runtime.md): arbitrary numeric keyframes, local shot clocks, transform hierarchies, measured text fitting, image crops/masks, held cels, footage seeking, and two-bone joints. Import only what the concept needs. [audio-motion.md](references/audio-motion.md) describes measured sound features; [footage-tracking.md](references/footage-tracking.md) covers planar feature tracking and explicit lost-track handling. These helpers accept authored data and assets; none interprets a prompt or chooses a film.

Use [project-replay.md](references/project-replay.md) to preserve a portable project with a separate exact prompt, creative contract, local assets and render settings. The `motion_project.py` helper scaffolds, checks, renders, and packages agent-authored source. A repeated natural-language prompt can lead to a different design; a saved source/assets/runtime bundle preserves the chosen design. Do not promise identical fresh model output from the prompt alone.

## Choreography

Choose timing from the behavior: spring or overshoot for elastic objects, decisive acceleration for a cut, constant speed for a conveyor or orbit, restrained drift for atmosphere. Coordinate overlapping layers around a clear focal event. Holds serve reading, recognition, anticipation, or payoff; loops and continuous motion may not need a frozen ending.

Make relationships visible: a shape may become a letter, a seam may drive a wipe, or a camera move may reveal scale. A transition should preserve a meaningful property or make a deliberate editorial break. Avoid using generic entrances as the whole animation.

## Render and repair

Read [critique.md](references/critique.md) for substantial output. Inspect a representative still early, then proof frames around important motion and boundaries. Review the complete render at normal speed. Repair visible weaknesses before export; codec success does not establish design quality.

Keep factual/technical validation separate from artistic judgments. If using another model for critique, provide actual images or video and the creative contract. Keep critiques timecoded and actionable. Record which observed failure each revision resolves. Do not claim that a model rating proves parity with a commercial showcase.

For an original authored film, deliver the final video and a usable editable project: source, required local assets, dependency versions and lockfile where packages are used, and exact preview/render instructions. List external font or renderer requirements and include assets only when their distribution terms permit. A directory of source files without its dependencies is not a reproducible handoff. Report the most important design result, how it was checked, and any material limitation. When the work changes repository helpers or references, briefly explain their role in the pipeline.
