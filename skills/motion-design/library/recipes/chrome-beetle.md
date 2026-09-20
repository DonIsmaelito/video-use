# Chrome beetle

An original stylized jewel beetle with sculpted body sections, two domed engraved elytra, six articulated legs, segmented antennae and two translucent veined hindwings. Its material and geometry are designed for a close three-quarter view. It illustrates plausible insect mechanisms rather than reproducing a particular species or claiming an aerodynamic simulation.

## Contract

```js
const beetle = createChromeBeetle({size: 1});
scene.add(beetle.group);
beetle.setState({wingOpen: 1, unfurl: 1, flight: 0.8,
                legTuck: 0.6, flapPhase: 2.4, antennaSweep: 0.1});
```

`createChromeBeetle()` accepts positive finite `size` and optional `shellMaterial`, `darkMaterial`, `accentMaterial`, `membraneMaterial`. It returns `group`, `setState`, `parts` and `dispose`. The body points along positive Y and its dorsal surface faces positive Z; use camera up `(0,0,1)` or orient the parent group as needed.

- `wingOpen`: 0–1, lifts and spreads the two rigid wing cases around their anterior pivots.
- `unfurl`: 0–1, sweeps the membrane roots and unfolds the outer wing panels at secondary hinges. Membranes remain hidden when fully folded.
- `flight`: 0–1, controls membrane wingbeat amplitude, independently of body position.
- `legTuck`: 0–1, articulates hip and tibia joints after lift begins.
- `flapPhase`: radians, an absolute wingbeat phase. The host supplies time and cadence.
- `antennaSweep`: finite signed value, gives both antennae a small opposed sensing gesture.

Normalized fields clamp. All fields default to zero when omitted, so supply every animated value on each seek. Invalid nonfinite state values throw before applying a pose. The module has no clock, renderer, environment, camera, randomness, network access or autonomous playback. Body translation and overall attitude are host-owned; keep them on a staging parent if other effects also address the recipe group.

`parts` exposes named body meshes plus cases, flight-wing root/tip pairs, leg hip/knee chains and antenna roots. Treat these as inspection and authoring handles. Direct edits to the rotations managed by `setState` are overwritten on the next pose evaluation.

`dispose()` is idempotent, frees all recipe-created geometry/materials, and removes the group from its parent. Supplied materials and textures remain caller-owned. Calling `setState` after disposal fails clearly.

## Use and inspection

Use a real reflection environment and large studio highlights when using the default metal materials. The supplied film selected the catalog's `polyhaven-studio-small-09-1k` HDR. Fetch it into the project with `helpers/motion_library.py`; keep its receipt. The chrome should retain tonal shape and restrained color, while amber belongs to joints, edge trim and the membrane veins. The membrane material uses transparency and transmission, which require proof under the final camera and lighting.

Inspect closed cases, intermediate opening, the fully unfolded wings and tucked legs. The original film develops its wingbeat before liftoff and pulls the camera back as the span increases. Do not derive each pose from the previous frame. A useful editability proof is a second render with maximum `wingOpen: 0.55`, using the same camera and time as the fully open pose.

The demonstration lives in its isolated production project with exact prompt, catalog selection, local HDR receipt, local Three.js 0.186.0, HTML choreography and the render command. The module alone intentionally does not impose that film's violet studio, eight-second timing, camera or soundtrack.

## Limits and validation

This is an authored sculpture, not a biological rig or an engineering insect model. Parameters express normalized travel. The supports and folding order are visually motivated; extreme direct part edits can intersect geometry. Antennae and veins are built for 1080p close views rather than far-away crowds.

The initial contract check verified exact absolute pose replay after later and earlier states, finite geometry, six leg chains, two case hinges, two membrane wings, nonfinite input rejection and disposal guards. Four rendered poses passed exact repeated/backward seeks. The 3.7s fully open hero was independently accepted; a second proof changing only maximum case opening to 0.55 visibly changed that control and passed the same seek validation. Repairs to opening-frame clearance, membrane fold direction and material balance are recorded in the production `PROMPT.md`.
