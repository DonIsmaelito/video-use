# Satin bow

An original continuous ribbon surface that gathers into two bow loops, a central wrap and trailing tails. The [module](satin-bow.mjs) owns the mesh and absolute pose controls; callers own material, environment, staging, camera, timeline and sound. It is a designed visual approximation, not a cloth solver, collision guarantee or physically validated knot.

`createSatinBow({ width, segments, crossSegments, material, edgeMaterial })` returns `group`, `ribbon`, `edges`, `setState`, `controls` and `dispose`. Add `group` to a Three.js scene. The supplied physical or standard materials should be designed with a suitable environment; satin is conveyed by surface orientation and broad reflections as well as roughness, sheen and anisotropy.

| Control | Meaning / range |
| --- | --- |
| `tie` | 0–1 gathering state from loose strip to full bow. Default 1. |
| `cinch` | 0–1 compression of the central wrap. Default 1. |
| `flutter` | 0–1 local depth and vertical wave amplitude. Default 0. |
| `phase` | Absolute wave phase in radians; no accumulated clock. Default 0. |
| `loopSpread` | 0.72–1.28 lateral spread of the authored bow, clamped. Default 1. |
| `tailDrop` | 0.65–1.25 vertical extension of the tails, clamped. Default 1. |

Width is clamped to 0.35–0.9 world units. Default tessellation is 320 length segments × 12 cross segments, with a pair of fine continuous selvedges. The component keeps the same indexed surface throughout construction and explicitly controls width; its arc length changes during the authored deformation. The shallow cup across the surface catches a broad specular band. Tails have small chevron cuts.

Assign every animated state field at each seek; omitted fields reset to their defaults. `dispose()` releases all recipe geometry, disposes only recipe-created default materials and detaches its group. Caller-supplied materials and textures remain caller-owned. Three.js is imported from `three`, so the caller must provide a local module import map or an appropriate bundler.

The portable [demonstration](satin-bow-demo.html) exposes `motionReady` and deterministic `seek(seconds)`, with a `?variant=wide` mode for a meaningful loop-spread comparison. Its original production project is `/private/tmp/motion-five-more-20260914/06-satin-bow/`. The exact prompt is “Make a satin ribbon tie itself into a floating bow.”

Related registry entries are `mediawork-pinterest-objects` for construction order, `mediawork-office-motion-tests` for proving deformation poses, and `polyhaven-studio-small-09-1k` for broad studio reflections. Third-party films remain reference-only. The optional HDR is CC0 and acquired project-locally; it is not embedded in this recipe.

Validation: final export passed encoded QA for 240 frames, 1920 × 1080, 30 fps, eight seconds and stereo audio. Four full-size proof poses and 20 encoded samples were visually inspected. Final rendering and the independent loop-spread variant each passed four exact repeated/backward seek checks. The control changes `loopSpread` from 1 to 1.24 while retaining material, camera and timing; its wider loops and tails remain recognizable. Evidence is in the production project's `final.qa/` and `control-proof.render/` directories. This is frame-sequence review, not a claim of normal-speed playback or subjective audio audition.

Repairs preserved in the prompt log include smooth transport of the width frame, a wider central wrap, distributed chevron cuts, deeper material midtones and explicitly uploaded smooth tangents for anisotropy. The frozen module SHA-256 is `8f177fcdd4190357cef7ce28e3efafe0fdb545abe7f3a0d30641f193e964ab0f`.
