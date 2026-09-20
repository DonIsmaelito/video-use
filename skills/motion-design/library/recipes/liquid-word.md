# Liquid word

An original shader mechanism that turns editable glyphs into a merging liquid surface and back. `createLiquidWord({text,fontFamily,weight,width,height})` creates a full-frame Three.js mesh and returns `setState({liquefaction,phase})` and `dispose()`. The caller must load the chosen font first and owns the scene, renderer and time. `liquefaction` clamps to 0–1; `phase` controls the surface's changing unevenness. Both must be finite.

The component draws the actual word with the loaded font, computes a distance field on the CPU, and shades a union of deformed glyphs, drips and a puddle. This preserves exact wording and allows a real text edit. It is a designed liquid deformation rather than a physical fluid solver. The normalized layout is composed for wide delivery; recompose deliberately for other aspect ratios. The present material palette is yellow wax against cobalt and can be edited in the shader.

Example prompt: “Make the word MELT turn into warm yellow liquid and pull itself back into letters.” Load the Sora variable font using the library asset entry, retain OFL.txt, create the word and call `setState` from an absolute seek function. The only text is the transforming hero itself.

Verify a different word in a temporary proof and check the readable, dripping and fully pooled states. Long words shrink to fit. The component disposes its geometry, material and generated texture; it does not own the caller's renderer. Use `helpers/motion_render.mjs` for deterministic proofs and the final MP4, then inspect actual pixels and delivery metadata.

The font surface uses an independently implemented separable Euclidean distance transform based on [Felzenszwalb and Huttenlocher, Distance Transforms of Sampled Functions](https://cs.brown.edu/people/pfelzens/papers/dt-final.pdf), followed by a three-pixel Gaussian to stabilize bevel normals. Full-resolution floating-point distances avoid quantization and directional artifacts from an eight-neighbor approximation.
