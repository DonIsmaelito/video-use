# Motion design creative range

This change expands agent-authored motion beyond single-object demonstrations. Shared infrastructure supplies mathematical timing, layout, media handling, articulated controls, audio measurements, planar tracking and portable replay. It does not interpret prompt keywords or select completed films. The agent still invents each project's composition and choreography.

## Infrastructure

| File | Responsibility |
|---|---|
| `skills/motion-design/runtime/motion.mjs` | Nonuniform numeric keyframes, shot-local clocks, seeded construction data, transform hierarchies, measured text fitting |
| `skills/motion-design/runtime/media.mjs` | Image crops, decoded loading, masks, cel/sprite timing, paused footage seeking |
| `skills/motion-design/runtime/rig.mjs` | General two-bone inverse kinematics with explicit unreachable targets |
| `helpers/motion_audio.py` | Arbitrary audio to time-indexed RMS, peak, envelope, frequency bands and onsets |
| `helpers/motion_track.py` | A selected planar region to measured per-frame homographies; rational PTS timing and explicit loss |
| `skills/motion-design/runtime/tracking.mjs` | Observed-frame sampling and projective mapping into scaled browser compositions |
| `helpers/motion_project.py` | Draft scaffolding, contract checks, rendering and portable source packages with checksums |
| `helpers/motion_render.mjs` | Exact-time browser rendering; local asset serving including seekable media byte ranges |
| `skills/motion-design/SKILL.md` and references | Select a creative approach, author the visual relationships, inspect output and preserve exact briefs separately |

Prompt/content/style/geometry choices stay in examples. Project scaffolding deliberately refuses to render until source is authored. The library remains an optional source of mechanisms rather than a list of canned prompt responses.

## The five authored briefs

The [machine-readable index](../skills/motion-design/examples/index.json) and each example's `prompt.txt` preserve these exactly. Every example has a separate creative contract, local assets and `motion-project.json`.

1. **One clear thought — typography, 16 seconds.** “Make a short typographic film about the feeling of having too many tabs open in your head, then finding one clear thought. Let the words behave like the feeling. Use only type and simple graphic shapes.”
2. **Room to breathe — photographic collage, 18 seconds.** “Make a tactile editorial film about leaving the city for the ocean. Let photographs, cut paper, and drawn lines hand off movement to one another. No voiceover.”
3. **Small courage — character performance, 16 seconds.** “Animate a small paper character trying to carry a circle that is much too big. Give it hesitation, a failed attempt, a clever solution, and a quiet proud ending. No dialogue or captions.”
4. **Open Field — product/identity/editorial family, 18 seconds.** “Create a launch film for an imaginary creative workspace called Open Field. Show scattered ideas becoming a connected project, then extend the same visual language into a logo ident and an editorial title.”
5. **Signal Garden — audio-driven graphic animation, 16 seconds.** “Turn an original electronic rhythm into a living graphic garden. Let bass, bright percussion, and quiet passages produce visibly different movement, with a clear build and release.”

All films are 1920×1080 at 30 fps. Signal Garden has an original score; the other four are intentionally silent. The collage uses three original built-in imagegen photographs; asset prompts are preserved in its `assets/image-prompts.json`. Other artwork is original code-native type, geometry and illustration. Bundled fonts include their OFL licenses. No studio animation assets or code were copied.

## Evidence and limits

- The final targeted suites pass: 61 Python tests and 40 Node tests. Skill validation, dependency-lock validation and whitespace checks also pass.
- All five films fully decode and have the expected dimensions, frame rate and 2,520 combined frames. Repeated/backward seek captures pass. Proofs and dense encoded contact sheets were inspected; normal-speed audiovisual playback was not directly reviewed.
- Content-only typography and Open Field variations used longer text and different palettes without changing scene code. This proves those controls work, not universal fresh-prompt quality.
- Five packaged projects were extracted and rendered from another working directory on the same runtime. All 38 sampled PNG hashes matched their original proofs, and served source asset hashes matched. This caught and repaired a temporary-server-URL seed in the collage. After updating the packaged media server, five additional poster comparisons also matched; the replay report records current archive hashes separately from the historical verification.
- The 84-second viewing reel copies the original video packets. Every decoded frame matches the corresponding original film; only audio is normalized for concatenation.
- Planar tracking is tested against known synthetic translations, rotation, scale and projective tilt, plus missing/featureless planes and nonuniform timestamps. This is a technical validation rather than a natural live-action showcase. It does not provide semantic rotoscoping, depth occlusion or a 3D camera solve.
- Shared media serving must support byte ranges for browser seeking. A seek completion event alone is insufficient if the browser clamps to the beginning, and an approximate playback clock does not identify the decoded frame. `seekMedia` accepts an optional measured `frameEnd` and samples inside the actual source-frame interval. The 48-frame browser integration export passes; independently decoded browser pixels match FFmpeg frames 24, 25 and 47 exactly after forward, repeated and backward seeks. This repaired a real preceding-frame error at fractional timestamps. Evidence is in `tracking-validation/browser-proof/decoded-frame-verification.json` beside the delivered films.
- Replaying saved source/assets fixes the selected creative interpretation. Repeating a natural-language brief may choose different compositions or generated assets. Different Chrome/OS/renderer versions may also change pixels or encoded bytes.

Validation runtime: Node 22.14.0, Puppeteer Core 25.10.0, Chrome 152.0.7977.83. Python tests used NumPy 2.3.5, Pillow 11.1.0 and OpenCV 4.11.0; the optional dependency lock may resolve a newer compatible OpenCV. The source package records the installed rendering requirements and the render manifests record actual versions.

Local delivery is `/Users/ismaelito/Movies/video-use-tests/creative-range-20260915/edit/`: individual films, `all-five.mp4`, exact prompts, project source ZIPs, replay reports and synthetic tracking evidence. Session renders stay outside the repository. The repository example sources are reusable authoring evidence; rendering remains independent of this machine's delivery paths.

## Reproduce or author a new brief

From a clone, install the documented Node runtime once with `npm ci --prefix skills/motion-design/runtime`. Render any example using `python3 helpers/motion_project.py render skills/motion-design/examples/<id> --deps skills/motion-design/runtime --output /your/videos/edit/final.mp4`. Chrome/Chromium, FFmpeg/ffprobe and Python 3.10+ must be available. No model API or transcription credential is needed to replay these finished projects.

For new work, ask the agent to use the motion-design skill, provide the brief and output folder, and let it author a fresh project using relevant primitives. The project helper's `init` command only preserves the request and creates an empty scaffold; it does not itself generate a film. See [creative systems](../skills/motion-design/references/creative-systems.md) and [project replay](../skills/motion-design/references/project-replay.md).
