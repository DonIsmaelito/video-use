# Signal Garden

Exact prompt:

> Turn an original electronic rhythm into a living graphic garden. Let bass, bright percussion, and quiet passages produce visibly different movement, with a clear build and release.

The creative expansion and provenance are in `creative.json`. `scene.mjs` authors the botanical artwork; `generate_audio.py` authors the original score. These are a single example, not a runtime preset. `helpers/motion_audio.py` is the reusable analyzer and consumes arbitrary decoded audio without knowing this score's notes or tempo.

From the repository root, create a portable project in your chosen output directory (commands below use a shell variable):

```bash
garden_project=/absolute/path/to/signal-garden
mkdir -p "$garden_project"
cp skills/motion-design/examples/signal-garden/{index.html,scene.mjs,creative.json,creative-contract.md,prompt.txt,motion-project.json,generate_audio.py,README.md} "$garden_project/"
python3 "$garden_project/generate_audio.py" "$garden_project/soundtrack.wav"
python3 helpers/motion_audio.py "$garden_project/soundtrack.wav" -o "$garden_project/analysis.json"
node helpers/motion_render.mjs "$garden_project/index.html" \
  -o "$garden_project/final.mp4" --duration 16 --width 1920 --height 1080 \
  --fps 30 --audio "$garden_project/soundtrack.wav" --poster-time 11.8 \
  --deps /absolute/path/to/puppeteer-dependencies
python3 helpers/motion_qa.py "$garden_project/final.mp4" \
  --expect-width 1920 --expect-height 1080 --expect-fps 30 \
  --expect-duration 16 --expect-audio
```

There are no runtime JavaScript packages, remote assets or external fonts in the scene. The renderer requires the repository's documented Node, Puppeteer, Chrome and FFmpeg setup; score generation and analysis use NumPy. Preview the directory with an HTTP server and call `window.seek(seconds)` to inspect any time. `window.motionReady` resolves after the local analysis JSON has loaded.

The repository example also includes its generated score and analysis, so it can be replayed immediately with `python3 helpers/motion_project.py render skills/motion-design/examples/signal-garden --deps /absolute/path/to/puppeteer-dependencies`. The preparation commands above regenerate those assets from source for a portable copy.

Change palette and botanical geometry in `scene.mjs`; change sound-to-shape relationships in `draw`. `compileAudio` interpolates analysis values and precomputes cumulative energy with no visual constants. To use another track, replace `soundtrack.wav` and regenerate `analysis.json`. This example's authored duration is 16 seconds; edit its time clamp and render duration for a different length. Keep the same source and assets for exact replay. Repeating the prompt with an agent can produce a different creative expansion.
