# Cached motion references

These original four-second samples illustrate visual approaches, not a user's project.
They are not a fixed prompt dispatcher or a substitute for art direction. `workflow.py`
selects at most two relevant examples; explicit preferences and precise edits skip them.

The five starter samples cover diagram-led teaching, editorial motion, restrained and
emphasized captions, and interface demonstrations. Caption footage is deliberately an
illustrated stand-in; the UI demonstration is fictional. None claim photorealistic 3D,
actual Manim rendering, or generative-video capability.

`source/scene.html` contains deterministic absolute-time compositions. Inter is bundled
under its adjacent OFL. `build.py` uses the video-use motion renderer, which validates
backward/repeated seeks and captures proof frames. Inspect these and run `motion_qa.py`
before publishing. Render with a dedicated Puppeteer dependency directory:

    python video_use_mcp/pilot/references/build.py --deps /path/to/deps --out /tmp/reference-build

To upload from the linked Studio project:

    python video_use_mcp/pilot/references/publish.py /tmp/reference-build

The public `video-references` InsForge bucket contains authored examples only. User
media stays private. Asset keys include content hashes, so changing a sample cannot
silently overwrite the appearance of an older choice. `manifest.json` pins public URLs,
posters, hashes and dimensions. Serving choices performs no generation or sandbox work.
The MCP resource CSP permits the project storage origin and `https://cdn.insforge.dev`
for media, not network fetches. InsForge public object URLs redirect to that CDN.
