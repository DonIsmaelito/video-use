# Citrus slices

Original geometry for a whole citrus fruit whose curved rind bands separate into a helix and return to the same sphere. Each neighboring pair shares a cut-face material and corresponding UV orientation. The original film begins with dimpled peel, opens into a ruby spiral, cuts briefly to the pulp, and snaps back into one fruit. There are no baked scene, camera, or timing assumptions in the component.

Exact example prompt: **Make a blood orange split into juicy slices, spiral open, and snap back together.**

## Interface

```js
import { createCitrusSlices } from './citrus-slices.mjs';
const citrus = createCitrusSlices({
  sliceCount: 7,
  radius: 1.35,
  seed: 709,
  cutImage,       // optional, already decoded caller-owned image
  peelMaterial,   // optional caller-owned Three.js material
});
scene.add(citrus.group);
citrus.setState({ separation: 0.8, spiral: 1, rotation: 0.1 });
// Caller owns scene placement, clock, camera, lights, renderer and readiness.
citrus.dispose();
```

`sliceCount` is an integer from 3 through 11 and determines topology at construction. `radius` is a positive finite sphere radius in world units; the authored surface and separation constants are tuned around 1.35. `seed` supplies the deterministic procedural variation, coerced to a 32-bit state. Reconstruct the component to change topology or its seed.

`setState` assigns an absolute pose. `separation` clamps to 0–1; `spiral` clamps to 0–1.4 and controls both the helical radius and angular spread; `rotation` changes the opening helix phase in radians. Omitted values return to their defaults, so send a full state when retaining other values. Nonfinite values throw. The top cap tilts to show its underside. `parts` contains the slice groups in bottom-to-top order. Apply whole-object rotation or translation to `group` independently.

`dispose()` releases the component's geometries, default materials, derived textures and generated canvases, then detaches its group. It preserves a caller-supplied peel material and the supplied image. Disposal is idempotent; setting state afterward throws.

## Surfaces and dependencies

The component imports local Three.js and uses browser Canvas APIs. The demonstrated scene uses Three.js 0.186.0. The rind color and pore bump maps are original deterministic procedural resources. Without `cutImage`, the component generates an irregular radial cross-section with membranes and cell marks. That fallback establishes citrus anatomy but appeared illustrated in macro proof; it does not reproduce the final film's photographic detail.

The final film supplies one original image generated specifically as a flat blood-orange cut appearance. The project preserves the exact expanded prompt, original PNG, hash, byte size and provenance manifest. The component derives its own Canvas textures with a small overscan suited to the inspected image. The image contains photographic microglints; this is an appearance texture rather than a measured PBR scan or volumetric fruit simulation. A different image may need a different crop. Decode the image before constructing the component, include it as a local project dependency, and preserve its applicable rights/provenance. No image binary is bundled in the recipe directory.

The demonstrated studio uses the catalog asset `polyhaven-studio-small-09-1k`, fetched project-locally with its CC0 receipt. The component itself neither fetches an HDR nor owns the environment. Its camera, floor, scene lighting and score remain caller-owned. Copy any example HTML into an isolated project with the same relative module, asset and local Three.js paths; do not serve an example directly from the catalog root.

## Discovery and proof scope

Catalog discovery used `assembly`, `radial`, `macro` and `hdri`. `mediawork-pinterest-objects` informed construction-driven separation; `lilium-flower-family` informed the relationship between a botanical whole and close detail. These are inspiration references, not reusable fruit assets. No source-reference artwork was copied.

The film's native-control proof changes `spiral` from 1 to 0.45 at the same 3.65-second beat, retaining the camera, slice count, cut image, lighting and timeline. Four repeated out-of-order seeks test absolute rendering in the production helper. These checks concern the demonstrated component and browser scene; they are not a general performance benchmark or a claim that every new count, radius or texture already has visual approval. Reproof a changed topology, new texture crop or revised camera before export.
