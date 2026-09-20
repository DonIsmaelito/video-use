# Botanical editorial

An original Canvas composition mechanism for a coherent photographic asset family. It turns a supplied full hero image into related close crops, vertical reveals and radial shutters. It does not generate a new viewpoint or simulate plant growth.

`createBotanicalEditorial({image,width,height})` accepts an already decoded image and returns `render(ctx,state)`. Modes are `hero`, `macro`, `strips` and `radial`; controls include `focus` in normalized image coordinates, `zoom`, `rotation`, shutter `progress`/`opening`, and `sectors`. The caller owns image loading, shot selection, timing and canvas lifetime. Each render resets composition state and paints the complete frame.

Select an image whose detail can survive the intended crop. In the example, a generated passionflower supplies the silhouette, filaments and pollen details; the underlying asset is recorded with its exact generation prompt in the project. No Motionimo or studio artwork is reused. A new project can supply another appropriately licensed or generated image.

Example prompt: “Make a purple passionflower become a bold, wordless botanical fashion film.” The film uses macro → full hero → related details → radial reconstruction → hero. No slogans, specimen labels or ornamental UI appear. A second image focus or sector-count proof should verify that a new asset remains framed correctly. Review actual crop resolution and edge continuity, not merely successful seeks.

This recipe belongs to the motion library; discover it with `python3 helpers/motion_library.py search botanical`. The source example and exact prompt are indexed in the five-prompt creation notes. Its method is an editorial interpretation of the LILIUM asset-family lesson, not a copy of the reference layout.


The demonstrated margin repair prepares a feathered copy of the image in a private canvas and leaves the supplied image unchanged. Only the outer 2.5 percent on each edge fades; keep essential artwork away from that margin. The prepared image lives with the returned composition closure, and the caller releases it by dropping the composition and image references when the scene is no longer needed. No animation loop or event listener is installed.

The Night Bloom trial verified four exact repeated/backward seeks and an actual sector-count edit: fourteen to seven at the radial reveal. Both settings preserve the same later hero pose. Its complete 240-frame scored export passed the technical delivery checks. Visual review covered the generated asset, hero/macros, repaired plate margin, radial control and twelve sampled encoded frames; uninterrupted audiovisual playback was not performed in that agent review. The project keeps the original image-generation prompt, asset hash, procedural sound source, control HTML and validation record. This is authored editorial motion of one still, not native image-to-video generation.
