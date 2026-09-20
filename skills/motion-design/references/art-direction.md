# Art direction for motion

## The decision that changes quality

A palette and a font do not constitute an idea. Name the subject-specific behavior that makes the motion worth watching: pressure folds a surface into a letter, a product's spectrum becomes its packaging, or type acts like a physical object. The mechanism should remain interesting before explanatory copy is added.

Record these decisions succinctly in the project:

| Decision | Useful specificity |
|---|---|
| Intended impression | An audience, a feeling, and the reason this subject merits it |
| Visual premise | What the audience sees and what changes |
| Hero frame | A precise composition worth exporting as a still |
| Signature transformation | A visible relationship unique to the concept |
| Type roles | Display/body/detail choices, weight, measure, and optical spacing |
| Materials and palette | Surface, illumination, background, contrast, and accent purpose |
| Rhythm | Where anticipation, acceleration, interruption, and payoff occur |
| Assets | What must be generated, acquired, or modeled before design can settle |
| Failure conditions | Specific ways this direction could become generic or unreadable |

For a simple edit, the existing composition may already answer most of this. Record only decisions the task needs.

## Choose a concept with consequences

For an open brief, sketch a few substantially different premises before committing: a functional change, a material transformation, or an editorial sequence of related views. Prefer the premise with a distinctive silhouette, an intelligible change, and assets that can actually be produced well. A list of visual treatments such as chrome, blur and particles is not a concept.

Write the visible argument in one sentence: “a folded charger unfolds in hinge order, catches light and activates its core.” Name what initiates the action, which property survives it, and how the audience recognizes completion. An abstract film can use visual rather than literal causality—pressure, attraction, balance or a shared contour—as long as the chosen relationship reads in the image. Do not make every piece a product assembly simply because that mechanism worked once.

Before expensive animation, prove the difficult asset or action. A character may need a small pose sheet; a folding object needs believable attachments; a botanical collage needs related macro images; an aperture needs a readable open and closed silhouette. Reject a weak premise or unsuitable asset here instead of adding copy to explain it.

## Study references as visual evidence

Inspect actual frames and motion when available. Preserve source URLs and useful timecodes. Describe hierarchy, scale, silhouette, text density, crop, lighting, texture, camera path, transition mechanics, and hold durations. Separate “the object appears to fold” from “the vendor uses a mesh deformer”; only the former is directly observable.

Translate reference qualities into original decisions. A reference can establish tactile lighting, a strong scale contrast, or a carefully timed collision without donating its layout, logo, or complete scene. If a referenced clip cannot be accessed, say so and use accessible material; do not invent its contents.

## Compose for a moving frame

Design at the intended delivery aspect and inspect at realistic viewing size. The hero subject and type must carry the image without relying on barely visible hairlines or tiny interface labels. Intentional cropping can create scale; accidental clipping of required copy is a defect.

Use hierarchy to choose density. A dense field can work when one object clearly leads; a sparse field can work when silhouette, spacing, and material make the frame complete. There is no universal element count, mandatory glow, or required amount of empty space.

Typography is geometry. Inspect the actual font before selecting final line breaks. Pay attention to side bearings, optical alignment, baseline relationships, and cropped letter shapes. Keep important copy vector/DOM when exactness and sharpness matter. Text can act as an object, a mask, or a spatial plane; it need not enter as a heading above cards.

Decide what text belongs in the film before composing it. Do not invent slogans, specimen numbers, corner labels, or supporting copy merely to fill negative space or make a motion study resemble a campaign. When the user requests only a transforming hero, remove that supporting layer entirely and recompose the hero into the space it occupied. A word may itself be the hero: develop its geometry, spacing, counterforms, or physical behavior instead of cycling headings, fonts, and colors. In a group of demonstrations, review whether the same heading-and-caption entrance has become the hidden template beneath different artwork.

## Asset and material direction

If an image, sculpture, product, or illustration is the main subject, inspect or generate it early. A visually weak hero cannot be rescued by extra particles. Use specialized image generation for bitmap assets when it adds real value; do not rasterize editable type merely to make the workflow easier.

Plan an asset family, not a pile of downloads. Record each asset's role, production route, and required states. Roles can include hero, detail view, interaction partner, evidence, environment and surface treatment; use only those the concept needs. Related images should share shape language, perspective, material and lighting. Generate or acquire the required alternate views before relying on them in a transition. Keep source, creator, exact license, local path and file hash with acquired files; [library.md](library.md) describes discovery and fetching.

Richer asset usage does not require a denser frame. A wordless single hero may depend on several well-made mesh parts, a coherent surface-map set, a real light environment and close detail views. Evaluate assets for the information and visual specificity they add. Compare a sourced material against the simpler version under the same camera and lighting; texture scale, seams or unsuitable wear can make the result worse.

For 3D, design what the surface reflects: environment, large luminous surfaces, key/fill/rim relationships, and background. Shape, roughness, metalness, camera, and lighting work together. Clearcoat, transmission, bloom, and depth of field are treatments with costs, not automatic quality switches. Verify tone mapping and highlights in the actual render.

## Rhythm and continuity

Keep a short beat table containing time, focal subject, visible change, camera, and sound cue when relevant. Let durations differ with purpose. Build anticipation before an important change and allow its strongest state to register. Fast accents need recognition; informational copy needs reading time.

Preserve a meaningful property across a handoff: shape, direction, velocity, color, anchor, scale, or object identity. A hard cut can also be the right decision. Do not repeat one transition just because it rendered reliably, or rotate effects solely to create variety.

For important beats, add “what this reveals” to the beat table. Separation can expose construction; contact can establish softness or weight; a close crop can reveal a material feature; a cut can compare related states. Let rigid, elastic, liquid and illustrated subjects move according to their chosen behavior. Preserve actual hinges and attachment anchors when the premise implies construction. One hero can support multiple shots—continuous camera drift is not a requirement for continuity.

For multiple films, differentiate the underlying visual grammar, not only the color. A typographic poster, tactile product study, data sculpture, and editorial collage should use different composition and motion logic. Shared mechanics and export tools can remain the same.

## Public precedents

These support workflow decisions, not claims about a private vendor's implementation:

- [LogoMotion](https://arxiv.org/html/2405.07065v2): visually grounded hierarchy, grouping, concept synthesis, and focused program repair.
- [HyperFrames video composition](https://raw.githubusercontent.com/heygen-com/hyperframes/main/skills/hyperframes-creative/references/video-composition.md): adapting brand primitives to the video frame.
- [OpenMontage taste direction](https://raw.githubusercontent.com/calesthio/OpenMontage/main/skills/meta/taste-direction.md): carrying a creative contract through planning, assets, and review.
- [Three.js physical materials](https://threejs.org/docs/pages/MeshPhysicalMaterial.html): material behavior and environment-lighting requirements.
