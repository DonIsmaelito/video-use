# Toy planet

An original ceramic miniature world with a red locomotive, configurable wagons, a progressively drawn circular railway, a raised viaduct and landscape pulled into place. The geometry, track frames and component state are reusable; the caller owns the studio, camera, lights, asset loading, timeline and score.

`createToyPlanet({radius=2.25,wagonCount=2})` returns `group`, `setState`, `trackFrame`, `parts` and `dispose`. Radius must be finite and at least 1.5; wagon count is an integer 0–3. The original demo uses radius 2.25 and two wagons. Changing the radius changes the planet/path while keeping miniature part dimensions fixed; reframe and inspect construction clearance for a different radius.

## Absolute controls

`setState({travel=0,trackProgress=1,landscapeProgress=travel,pull=1})` assigns every affected transform from fixed inputs. All inputs must be finite.

- `travel` is unwrapped turns along the track. It may exceed 1 so the train can continue around a finished world. The upper-hemisphere track sits at latitude 0.62 radians, begins at longitude 0.35 radians and progresses in the positive X/Z angular direction.
- `trackProgress` clamps to 0–1 and reveals rail geometry, the cream bed and sleepers in route order. It also builds the supporting viaduct before the engine reaches its raised track section.
- `landscapeProgress` advances the eight fixed landscape events. Each cluster rises from below its spherical ground anchor after the train has passed its longitude; values above approximately 1.05 complete this original arrangement.
- `pull` enables the short visible thread between the last wagon and the currently rising cluster when positive. It is a connection cue, not a physical cable solver.

`trackFrame(turns)` returns fresh `position`, `tangent`, `normal`, `side` and `quaternion` values in the returned group's coordinates. Tangent follows the actual raised track, normal is perpendicular to it, and the quaternion maps local X forward, Y outward/up and Z sideways. The demo uses this frame to keep its following camera related to the engine. The planet's global Y axis is its polar axis.

Cars follow the path independently. Every axle is also sampled on the same path at its longitudinal offset, so it stays attached to the curved rail instead of resting on an imagined flat tangent plane. Wheel centers sit 0.128 above the track center and their radius is 0.108, matching the 0.021 rail radius within 0.001 world unit. Rolling spokes receive absolute phase from the nominal latitude-circle distance. Bridges and scenery are original illustrative construction, not engineering or collision simulation.

## Ownership and setup

The module creates its own Three.js geometry and materials. `dispose()` is idempotent, releases them and removes the group from its parent. Calling `setState` after disposal throws. It installs no animation loop, event listener, network fetch or renderer. `parts` exposes globe, cars, axles, scenery, bridge, rails and sleepers for inspection; state-controlled transforms are reassigned on the next call.

The module requires Three.js; the demo pins 0.186.0 in real local `node_modules/three`. Its reflection environment uses the catalog asset `polyhaven-studio-small-09-1k` in the isolated project's assets directory, with its verified CC0 receipt. The HDR belongs to the demo, not the recipe. No downloaded train/model, external font, image-generated hero or reference-film pixel is included. Supply lighting appropriate to the ceramic and lacquered materials.

The exact trial prompt is “Make a tiny train race around a ceramic planet and pull its landscape into place.” The authored project includes an actual one-wagon-versus-two-wagon control under the same camera and timing; its topology and state replay were checked independently. Inspect readable car order, wheels on rails, the raised viaduct, sphere-attached scenery and connected pull threads. The project `PROMPT.md` records rendered iterations and the final evidence scope.

The authored eight-second demo passed four exact out-of-order image seeks and full 240-frame 1080p30/audio decode. Component checks include opening axle coverage and single-disposal ownership. The one-wagon bridge proof changes topology under the final camera. These checks support deterministic editing and delivery correctness; they are not a general quality benchmark.
