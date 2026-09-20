# Next seven video editing features

Status: feature backlog after PySceneDetect  
Date: 2026-09-05

PySceneDetect is the first planned addition. These are the seven projects/features to evaluate afterward. Each should be added as a focused helper and reference while the existing EDL and FFmpeg renderer continue to work.

## 1. Subject tracking

Projects: OpenCV, MediaPipe, Norfair, and optionally SAM 2.

What it gives the agent:

- Face- and subject-following vertical reframing.
- Smooth virtual camera movements.
- Automatic split-screen and picture-in-picture placement.
- Moving labels, highlights, and blur regions.
- Reusable object masks.
- Motion measurements for selecting montage shots.

Planned files:

- `helpers/track_subject.py` detects, associates, and smooths subject positions.
- `helpers/preview_track.py` draws the track and proposed crop onto a preview.
- `references/subject-tracking.md` explains detector choice, occlusion handling, smoothing, and failure cases.

Output: normalized position, scale, confidence, and optional mask keyframes that existing EDL reframe and overlay features can consume.

Scope boundary: start with faces and people. Add general segmentation only when bounding-box tracking is insufficient.

## 2. Revideo motion graphics

Project: Revideo.

What it gives the agent:

- Programmatic motion-design scenes.
- Reusable animated layouts and components.
- Audio-synchronized animation.
- Partial-range rendering for faster iteration.
- Worker-parallel rendering.
- Transparent overlays and full-frame video compositions.

Planned files:

- `helpers/revideo_slot.py` creates, renders, and validates an isolated Revideo animation slot.
- `references/revideo.md` covers scene structure, timing, audio, alpha output, and verification.

Output: a standard animation slot containing source, reasoning, preview frames, and a rendered MP4 or transparent WebM referenced by the EDL.

Scope boundary: Revideo does not replace Manim or HyperFrames. It must first beat HyperFrames on an A/B fixture for the kind of animation being requested.

## 3. Color-managed finishing

Projects: OpenColorIO and libplacebo.

What it gives the agent:

- Explicit camera-log conversion.
- ACES and other managed color workflows.
- Reliable source, working, display, and output color spaces.
- Better HDR-to-SDR tone and gamut mapping.
- LUT validation and baking.
- High-quality GPU scaling, debanding, and dithering when libplacebo is available.

Planned files:

- `helpers/inspect_color.py` reports transfer, primaries, matrix, range, bit depth, and HDR metadata.
- `helpers/color_transform.py` validates and applies an OCIO transform or baked LUT.
- `references/color-management.md` distinguishes technical transforms from creative grading.

Output: a color report, transform provenance, and an FFmpeg-ready filter or LUT.

Scope boundary: ordinary Rec.709 phone footage should keep the current path unless inspection finds a reason to use managed color.

## 4. Blender 3D and compositing

Project: Blender.

What it gives the agent:

- 3D product scenes and device mockups.
- Animated cameras, lighting, materials, and depth of field.
- 3D titles and logos.
- Particle and procedural animation.
- Motion tracking and compositor effects.

Planned files:

- `helpers/blender_slot.py` creates a slot, runs Blender headlessly, and validates the render.
- `references/blender-scenes.md` covers scene organization, camera safety, output formats, and verification.
- Starter assets for product turntables, device screens, titles, and simple camera moves.

Output: PNG sequences, MP4, ProRes 4444, or transparent WebM composed by the existing renderer.

Scope boundary: use Blender only for genuine 3D or compositor needs. Keep ordinary overlays in PIL, HyperFrames, Revideo, or Manim.

## 5. VapourSynth restoration

Project: VapourSynth and individually reviewed plugins.

What it gives the agent:

- Denoising and compression cleanup.
- Deinterlacing and inverse telecine.
- Debanding and chroma repair.
- Sharpening and halo removal.
- Frame interpolation and difficult cadence repair.

Planned files:

- `helpers/restore_video.py` selects a tested restoration chain and pipes `vspipe` into FFmpeg.
- `references/restoration.md` helps diagnose noise, interlacing, cadence, ringing, and banding before applying a treatment.

Output: a restored intermediate or a reproducible VapourSynth script that feeds the normal edit pipeline.

Scope boundary: restoration is opt-in and evidence-driven. Every plugin needs its own availability and license check.

## 6. MLT multitrack rendering

Project: MLT and its `melt` executable.

What it gives the agent:

- Multiple video and audio tracks.
- Overlap transitions.
- Effect stacks.
- Nested playlists and more NLE-like timeline composition.
- Access to installed MLT services used by editors such as Kdenlive and Shotcut.

Planned files:

- `helpers/render_mlt.py` compiles a supported edit into MLT XML and invokes `melt`.
- `references/mlt.md` documents profiles, producers, playlists, tractors, transitions, consumers, and timing traps.

Output: MLT XML, a capability report, render logs, and the final media artifact.

Scope boundary: FFmpeg remains the default. MLT is selected only when it makes a multitrack or transition-heavy edit materially simpler.

## 7. GPAC packaging and delivery

Project: GPAC and MP4Box.

What it gives the agent:

- Track and metadata preservation.
- Chapters and alternate audio/subtitle tracks.
- Fragmented MP4 output.
- DASH and HLS packaging.
- Delivery remuxing without another full video encode.

Planned files:

- `helpers/package_output.py` validates and executes packaging operations.
- `references/packaging.md` covers container, streaming, chapter, subtitle, and metadata choices.

Output: packaged MP4, DASH, or HLS deliverables plus a stream/metadata verification report.

Scope boundary: GPAC improves professional delivery rather than editorial quality, so it comes after the creative and finishing tools.

## Common shipping contract

Every feature should include:

1. One focused helper with a capability check.
2. One concise agent reference.
3. One realistic fixture and example output.
4. Structured progress and actionable failures.
5. Output validation with the existing FFmpeg/ffprobe workflow.
6. A version and license record for the engine, models, and plugins used.
7. A comparison showing that the project unlocks a new capability or materially improves the current workflow.

The projects should add new editing verbs without becoming mandatory dependencies or replacing the working renderer.
