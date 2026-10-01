# Cached motion references

These six original short samples illustrate visual approaches, not a user's
project. They are not a fixed prompt dispatcher or a substitute for art direction.
`show_video_choices` can show two or three relevant catalog IDs through its
`reference_ids` argument, including for custom and mixed requests. Category
suggestions are optional defaults. Explicit preferences and precise edits usually
make a picker unnecessary; samples never create an approval gate.

The five original four-second samples cover diagram-led teaching, editorial
motion, restrained and emphasized captions, and interface demonstrations.
`product_3d` adds a three-second procedural speaker assembly. Caption footage is
an illustrated stand-in; the interface is fictional; the speaker is a stylized
original object, not a validated engineering model. None claims photorealism,
actual Manim rendering or generative-video capability. Reference appearance does
not prescribe which renderer the assistant uses for a user's piece.

`source/scene.html` contains the five initial deterministic absolute-time
compositions. Inter is bundled under its adjacent OFL. `build.py` uses the
video-use motion renderer, which validates backward/repeated seeks and captures
proof frames. Inspect these and run `motion_qa.py` before publishing. Render with
a dedicated Puppeteer dependency directory:

    python video_use_mcp/pilot/references/build.py --deps /path/to/deps --out /tmp/reference-build

The original Three.js composition lives at
[`tests/fixtures/browser_workflows/product_3d.html`](../../../tests/fixtures/browser_workflows/product_3d.html).
Its companion script copies the pinned local Three.js 0.186.0 modules, MIT license
and RoomEnvironment into an isolated composition, then renders and runs QA:

    python tests/fixtures/browser_workflows/render_product_3d.py

That fixture uses the installed motion runtime dependencies, Chromium and FFmpeg;
it does not download assets or require an image/video-generation provider. Its
640×360, 12 fps result proves a bounded procedural technique. It does not promise
production-resolution speed, accurate product reconstruction or arbitrary model
compatibility on a CPU/software-WebGL worker.

To upload a reviewed build with its manifest from the linked Studio project:

    python video_use_mcp/pilot/references/publish.py /tmp/reference-build

The publisher merges those samples into the checked-in catalog, retaining samples
built independently, including `product_3d`. For an independently built sample,
include its video, `<id>.render/poster.png` and metadata in the build manifest
before publishing. Never publish unreviewed user assets as reference examples.

The public `video-references` InsForge bucket contains authored examples only.
User media stays private. Asset keys include content hashes, so changing a sample
cannot silently overwrite the appearance of an older choice. `manifest.json`
pins public URLs, posters, hashes, durations and dimensions. Serving choices
performs no generation or sandbox work. The MCP resource CSP permits the project
storage origin and `https://cdn.insforge.dev` for media playback; public storage
URLs can redirect to that CDN. Private source upload uses the coordinator's
separate scoped upload endpoint.
