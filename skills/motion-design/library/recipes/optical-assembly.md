# Optical assembly

An original parametric aperture, housing and lens stack for a wordless mechanical study. The reusable [module](optical-assembly.mjs) owns geometry and functional states; the [demonstration](optical-assembly-demo.html) owns the renderer, lighting, material assets, camera and eight-second choreography. It is an authored visual mechanism, not an engineering simulation or a reconstruction of an existing studio's work.

## Use and controls

`createOpticalAssembly({ bladeCount, radius, shellMaterial, bladeMaterial, trimMaterial, lensMaterial })` returns:

- `group`: attach this Three.js group to your scene or staging group.
- `setState({ aperture, separation, rotation })`: assign absolute state; aperture and separation clamp to 0–1, rotation is radians. Omitted fields reset to their defaults, so provide all animated fields at each seek.
- `parts`: casing, actuator, blade pivots and lens stack for inspection or further authored work.
- `dispose()`: disposes recipe geometry and recipe-created materials, then detaches the group. Caller-supplied materials and their textures remain caller-owned.

`bladeCount` accepts integers 5–16; six and eight were visually exercised in the supplied proof. `radius` scales the whole assembly relative to its authored radius parameter of 2. Aperture is normalized blade travel, not a physical f-number. Travel is reduced for lower blade counts to keep the wider blades inside the housing when assembled. The separated pose deliberately exposes blade profiles and their pivots. Caller materials should include appropriate lighting; a highly metallic face can reflect a dark environment and become unreadable.

The demo's `DESIGN` object sets blade count and delivery dimensions. `ASSETS` sets local file paths. `state(seconds)` defines opening, separation and return, and `pose(seconds)` assigns mechanism and camera state. The visible subject is the mechanism alone; there is no title, caption, label or interface layer. `motionReady` awaits the HDR and four material maps, creates the environment and assembly, and paints the initial frame. `seek(seconds)` waits for that readiness promise and then evaluates absolute time.

The weathered PBR maps belong on the housing. Clean blades use directional metallic highlights for contrast, and glass reveals the optical core. Adjust the texture scale, lighting and exposure after inspecting the chosen camera pose. An HDRI and more maps do not automatically improve every material. The demonstrated blade material reduces environment intensity and clearcoat while broadening roughness so directional reflections retain gray gradients. Camera orbit and rear lens travel are limited together: the separated pose must reveal construction while keeping the rear optic visible through the pupil.

## Prepare an isolated project

Run from the video-use checkout. Choose a new project directory outside this recipe folder:

```bash
OPTICAL_PROJECT=/absolute/path/to/optical-study
mkdir -p "$OPTICAL_PROJECT/assets"
cp skills/motion-design/library/recipes/optical-assembly.mjs "$OPTICAL_PROJECT/"
cp skills/motion-design/library/recipes/optical-assembly-demo.html "$OPTICAL_PROJECT/"
python3 helpers/motion_library.py fetch polyhaven-studio-small-09-1k --out "$OPTICAL_PROJECT/assets"
python3 helpers/motion_library.py fetch polyhaven-metal-plate-02-1k --out "$OPTICAL_PROJECT/assets"
npm install --prefix "$OPTICAL_PROJECT" --save-exact three@0.186.0 puppeteer-core@25.10.0
```

The fetcher verifies bytes and SHA-256 and writes asset/license receipts. The assets are [Poly Haven CC0](https://polyhaven.com/license): Studio Small 09 by Sergej Majboroda and Metal Plate 02 by Rob Tuytel. They are acquired project-locally; no third-party binary belongs in the recipe directory. Keep the generated package lock and receipts for handoff. The tested runtime uses Node 22.14, local Chrome and FFmpeg. On a machine with the project package files, use `npm ci` to reproduce dependencies.

The demo's import map expects a real local `node_modules/three` inside the served project. A symlink escaping the server root will be rejected by the browser renderer. `--deps` may point to another existing Puppeteer installation, but browser imports and assets still must resolve beneath the served root.

## Render and inspect

```bash
node helpers/motion_render.mjs "$OPTICAL_PROJECT/optical-assembly-demo.html" -o "$OPTICAL_PROJECT/hero.mp4" --deps "$OPTICAL_PROJECT" --duration 8 --stills-only --stills 0,1.5,2.5,3.8,5.8,7.9 --poster-time 2.5
node helpers/motion_render.mjs "$OPTICAL_PROJECT/optical-assembly-demo.html" -o "$OPTICAL_PROJECT/final.mp4" --deps "$OPTICAL_PROJECT" --duration 8 --width 1920 --height 1080 --fps 30 --poster-time 2.5
python3 helpers/motion_qa.py "$OPTICAL_PROJECT/final.mp4" --expect-width 1920 --expect-height 1080 --expect-fps 30 --expect-duration 8
```

This demonstration is intentionally silent. The renderer checks repeated and backward seeks before capture; QA then decodes the MP4. Inspect the closed pupil, opening, maximum separation and reassembled pose. Change `DESIGN.bladeCount` to 6 in a temporary copy and render proof frames to verify an actual structural edit. Restore 8 for the delivered demo. Keep that control proof and the final render manifest separate so a previous source version is not mistaken for the current result.
