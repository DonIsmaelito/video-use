# Color zipper

An original zipper whose slider separates attached teeth and dark fabric panels to reveal a continuous river of layered color. The same seam position drives fabric, sewn tape, stitches and hardware. The caller owns the scene, camera, environment, timeline and export.

Exact prompt: **Make a silver zipper unzip a midnight surface and reveal a flowing river of color.**

## Interface

```js
const zipper = createColorZipper({
  length: 8.4,
  toothCount: 46,
  colors: ['#ae0f49', '#f23e45', '#ff941f', '#bad830', '#0bc5cb', '#3d70d7', '#a43aab'],
  metalMaterial,  // optional caller-owned material
  fabricMaterial // optional caller-owned material
});
scene.add(zipper.group);
zipper.setState({ open: 0.65, flow: 4.8, spread: 1.45, pullTilt: 0.38 });
zipper.dispose();
```

The module imports local Three.js and uses browser Canvas for the original weave map. `length` accepts finite values from 4 to 14; `toothCount` is an integer from 20 to 100 per side. `colors` contains 3–12 values accepted by Three.js Color. Reconstruct the component for another topology or palette. Hardware dimensions and fabric margins are authored around the example scale, so changing length or tooth density requires inspection.

`setState` assigns an absolute state: `open` clamps to 0–1 and moves the slider from left to right; fabric separation follows behind it. `flow` is a finite unwrapped phase for the continuous colored surfaces. `spread` clamps to 0.45–1.8 and changes the opening width without moving the slider. `pullTilt` clamps to −0.2–0.8 radians and controls the hinged tab. Omitted values reset to defaults. Nonfinite state values throw.

The return value contains `group`, `setState`, `dispose` and `parts`. Parts expose panel grids, tooth instances, slider, tab pivot, ribbon grids and stitches for inspection. World placement belongs to `group`; transforms governed by state are reassigned by the next call. The example camera widens from a close hardware view to the opening river.

`dispose` is idempotent, detaches the group and releases owned geometry, default materials, weave texture and canvas. It preserves supplied metal/fabric materials and caller-owned environment resources. State changes after disposal throw. The component creates no renderer, clock, event listener, network request or audio.

## Assets and selective lighting

All geometry, weave, stitching, colors and motion are original code. The demonstrated scene uses local Three.js 0.186.0 and `polyhaven-studio-small-09-1k`, a pinned CC0 environment acquired into the project with its receipt. No zipper model, font, stock image or generated bitmap is required. The component does not fetch or embed the HDR.

The first proof's broad lighting made the hardware nearly white and diluted the river. The demonstration moved the light off the main reflection angle, reduced illumination, deepened the palette and assigned the HDR explicitly to the shared hardware material for independent reflection intensity. In the pinned Three.js renderer, a material that relies on `scene.environment` receives `scene.environmentIntensity`; merely changing its `envMapIntensity` did not override that scene value. The final example supplies the environment map directly to the hardware material and sets its own intensity, retaining the same environment for the rest of the scene. Inspect actual pixels after changing this light/material balance.

Copy the module and example HTML into an isolated project, with local `node_modules/three`, the expected `assets/studio_small_09_1k.hdr` and its receipt. A demo is not served from the catalog root. Its `window.motionReady` awaits the HDR and its `window.seek(seconds)` reconstructs any frame. The film is intentionally silent; omit the renderer's audio option.

## Controls, evidence and limits

The meaningful variation changes `spread` from 1.45 to 0.85 under the same camera, open progress, flow and material setup. This changes the attached opening width rather than substituting a second image. Inspect teeth at the moving junction, the tab opening, the cloth edge, color continuity and the full final framing. Recheck deterministic out-of-order seeks and render provenance after a change.

The geometry is a dimensional graphic interpretation of a zipper, not a garment pattern, collision solver or engineering-accurate slider. Ribbons are authored deformed surfaces, not fluid simulation. Existing catalog observations from `mediawork-pinterest-objects` informed attached construction; `ordinary-folk-webflow` informed exposing related layers. No referenced artwork was copied, and the current production did not newly review those complete reference films at normal speed.

The frozen eight-second film passed four exact repeated seeks, all 240 decoded frames at 1920×1080/30 fps, and an explicit zero-audio-stream check. A 24-frame encoded sequence was inspected across the opening and resolved flow. This is sampled encoded-frame review, not uninterrupted human playback or a general quality benchmark.
