# Jelly chair

An original sculptural lounge chair with a continuous elliptical swept back and arm shell, a deep rounded cushion, four organic supports and a restrained molded seat seam. [jelly-chair.mjs](jelly-chair.mjs) owns its shape and deformation. The caller owns lighting, renderer, ground, camera, timing and audio.

## Use

`createJellyChair({ width=1, material, seamMaterial })` returns `group`, `setState`, `parts` and `dispose`. Attach the group to a Three.js scene. Supply `MeshPhysicalMaterial` instances when the brief needs a different rubber, translucent resin or upholstery treatment. The default cherry material is only a starting point; inspect transmission, thickness and reflected highlights under the chosen environment. The demonstration assigns a cloned material to `parts.cushion` with lower specular intensity and clearcoat, preserving the seat's cherry tone under a broad reflection. That clone remains caller-owned.

`width` is a positive uniform scale applied to the authored chair. The default chair is approximately 2.75 units wide and 2.30 units tall. `parts` exposes the shell, cushion, piping and four supports for inspection. Changing the composition's camera or the recipe's source dimensions is preferable to distorting an assembled group without considering its contact plane.

`setState({ squash=1, lift=0, bend=0, yaw=0 })` assigns absolute state:

- `squash`: vertical scale, limited to 0.42–1.5; reciprocal square-root horizontal expansion preserves deformation volume.
- `lift`: nonnegative distance above the floor. With zero lift, the authored supports remain on y=0 through squash and bend.
- `bend`: a restrained quadratic horizontal shear, limited to −0.5–0.5, so the upper shell can lag the grounded supports.
- `yaw`: whole-chair rotation around its vertical axis in radians.

Omitted values reset to defaults. Position and normals are reconstructed from saved rest arrays at every call; there is no accumulated simulation state. Analytic inverse-transpose normal transport follows the deformation. The quadratic shear and reciprocal scaling preserve the local deformation Jacobian determinant; this is an authored elastic deformation, not a soft-body solver, collision system or material simulation. The caller must choose a plausible lift/contact timeline.

`dispose()` frees owned geometry and default materials, then detaches the group. Caller-supplied materials and textures remain caller-owned. The module has no renderer, network requests, random source or wall clock.

## Art direction and proof

The original demonstration prompt is “Make a cherry-red jelly chair land, squash, and spring back into shape.” Discovery queries `soft`, `contact` and `pinterest` selected `mediawork-pinterest-objects`; `HDRI` selected `polyhaven-studio-small-09-1k`. The reference's connected cushion/support compression informed the behavior. Its footage, geometry, colors and staging are not embedded in this recipe.

Use a grounded front three-quarter camera, a broad reflected light source and a legible floor shadow. Preserve red midtones: a large white reflection can erase the softness that the geometry was built to reveal. Ground contact should coincide with visible compression; do not let the whole chair float while its supports appear loaded. A restrained one-time camera push can register recovery without an unrelated continuous orbit.

Before export, render the deepest squash, rebound apex and settled chair. Verify actual earlier/later state replay and a meaningful `squash` variation. Inspect supports, cushion-to-shell attachments, silhouette and frame margins at both deformation extremes. The accompanying isolated project records source, original prompt, discovery selections, asset receipt and render evidence; it should not be treated as a reusable staging template.

Requires Three.js and its `BufferGeometryUtils` module; the demonstrated project pins Three.js 0.186.0. For the repository's browser renderer, import from a real local dependency directory, await the selected HDR in `window.motionReady`, and expose an absolute `window.seek(seconds)`. See [browser rendering](../../references/browser-rendering.md) for the caller's rendering contract.
