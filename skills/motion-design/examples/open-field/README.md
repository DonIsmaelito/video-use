# Open Field

An original product narrative, logo ident, and editorial title built from one authored visual language. It uses the general motion runtime for time, transforms, and text fitting; the renderer does not infer or select this example from a prompt.

Change `content.json` for brand, headlines, project labels, card copy, and palette. Copy length is fitted to its intended width; major composition changes remain creative authoring decisions in `scene.mjs`.

From the video-use root:

```sh
python3 helpers/motion_project.py check skills/motion-design/examples/open-field
python3 helpers/motion_project.py render skills/motion-design/examples/open-field --deps /path/to/renderer/dependencies --output /path/to/open-field.mp4 --qa
python3 helpers/motion_project.py pack skills/motion-design/examples/open-field --output /path/to/open-field.zip
```

Use the source package's `REPLAY.md` after extraction. The exact natural-language prompt is in `prompt.txt`; the contract preserves the choices made for this particular interpretation. Re-running authoring on a prompt may produce a different design. Replaying the saved source preserves this one.
