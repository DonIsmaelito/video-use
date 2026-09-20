# Composable browser motion primitives

`../runtime/motion.mjs` is a dependency-free ES module. It handles numeric sampling, transform composition, and text measurement. It does not interpret prompts, select scenes, prescribe a palette, or generate creative direction. Use it from Canvas, DOM, SVG, or a renderer adapter; every function is optional.

## Time and controls

`keyframes([{time, value, ease?}, ...])` compiles a pure sampler. Values can be numbers or flat objects with any matching finite numeric properties. Times are strictly increasing and may be nonuniform or negative. Sampling before/after the range holds the first/last value. `ease` on a key controls its outgoing segment. Available curves: `linear`, `inCubic`, `outCubic`, `inOutCubic`, `smooth`, `outBack`; a custom pure function is also accepted. Overshoot is retained. Numeric angle controls interpolate numerically: author the intended rotation direction explicitly, including a full revolution when needed.

`interpolatePose(from, to, amount)` interpolates matching arbitrary named numeric properties. It intentionally does not guess how strings, colors, nested objects, or scene nodes should blend. Represent a color as channels or supply a renderer-specific conversion when appropriate.

`clip(time, {start, duration, rate=1})` returns `{active, progress, time}`. Activity uses a half-open global interval `[start, start+duration)`, preventing two adjacent shots from both claiming a boundary. Progress holds at 0/1 outside the interval; local time is `progress * duration * rate`. Duration and rate must be positive. Nested clips can consume the parent's local time.

`seededRandom(seed)` produces a repeatable sequence for a string/number seed. Generate composition data once when constructing the scene. Do not advance that generator inside `window.seek`: that would make the scene depend on seek history. Deterministic frame sampling means the same authored scene reproduces correctly; it does not mean that a natural-language prompt must select a fixed scene.

## Transform relationships

`matrix2D({x,y,rotation,scaleX,scaleY,skewX,skewY,anchorX,anchorY})` returns a Canvas/SVG affine array `[a,b,c,d,e,f]`. Angles are radians. An anchor is expressed in local coordinates and maps to `(x,y)` in its parent. `compose2D(parent, local)` applies local then parent. `apply2D(matrix, {x,y})` maps a point, useful for attachments or masks. `withTransform(context, transform, draw)` scopes a Canvas group and restores the parent even when the drawing callback throws. Nest groups as needed; there is no mandatory scene schema.

## Typography

Await local font loading before calling `measureText(context, text, style)` or `fitText(context, text, options)`. Styles include `family`, `weight`, `tracking` (pixels), `lineHeight` (font-size multiplier), and measurement `size`. Fitting options include required `width`, optional `height`, `minSize`, and `maxSize`. Explicit newlines are preserved; automatic word wrapping is deliberately an authoring decision. Fit results include size, width, height, per-line widths, and `fits`. A false result means even the minimum size exceeds the box; do not silently clip required content.

Tracking counts Unicode grapheme clusters where `Intl.Segmenter` is available. Tracking-aware drawing remains the scene's job. Height is an intentional line box (`size * lineHeight`) rather than the visible ink bounds; allow for the chosen font's ascenders and descenders when composing precise crops. Optical alignment and deliberate letter overlap still need rendered review.

The original kinetic-type example at `../examples/kinetic-type/` demonstrates independently authored content and timed compositions. Its wording, pacing, and art direction live in the example, never in this runtime. Run the runtime checks with `node --test tests/test_motion_runtime.mjs` from the repository root.

## Media and articulated rigs

Read [media-and-rigs.md](media-and-rigs.md) for image cropping, masks, explicit cel holds, media seek readiness, and two-bone inverse kinematics. Those modules compose with the time, pose, and parent-transform helpers above; they do not require a shared scene template.

## Consuming measured planar tracking

`../runtime/tracking.mjs` consumes schema version 1 from `helpers/motion_track.py`. It provides browser-side sampling and projective coordinate conversion; it does not estimate motion itself. The producer records actual frame timestamps, tracked reference-to-current homographies, confidence, and explicit lost frames.

`createTrackSampler(track)` returns a pure `sample(time)` function. Results contain `{visible, frame, reason?}`. The sampler holds the most recent observation on `[frame.time, next.time)`, respecting nonuniform source timestamps without smoothing or interpolating matrices. A lost frame immediately returns `visible:false`, discarding any stale geometry, and remains hidden until a subsequent tracked observation. Outside coverage, `frame` is null and the overlay is hidden. The last observation holds through `source.duration`; if duration is absent or does not exceed the last timestamp, the nominal frame period from `source.avgFrameRate` supplies the final interval. The producer currently does not automatically reacquire a lost plane.

Source dimensions describe original stored video pixels, with top-left origin. An optional `initialQuad` must be a convex, ordered four-point polygon inside those dimensions. Observed quads may move outside the image; that is a valid plane moving out of frame. Invalid, folded, or singular geometry is rejected. Track data is snapshotted on construction, and returned geometry is copied, so a drawing component cannot accidentally mutate later seeks.

`applyHomography(H, {x,y})` maps any reference-frame source point into the current source frame using perspective division. Points on the projective horizon fail explicitly. This is useful for tracking an individual label anchor or checking where a reference point landed.

`homographyToMatrix3d(H, {sourceWidth,sourceHeight,outputWidth,outputHeight,offsetX=0,offsetY=0})` returns 16 numbers in CSS `matrix3d` order. Author an overlay element at the full original source dimensions; position its children in reference-frame source pixels. Set `transform-origin: 0 0`, then apply the returned matrix. Output dimensions and offsets describe the actual placed video image, including any letterboxing or crop offset. Scaling accounts for perspective, not just the final translation.

```js
const sampleTrack = createTrackSampler(trackData);
overlay.style.width = `${trackData.source.width}px`;
overlay.style.height = `${trackData.source.height}px`;
overlay.style.transformOrigin = '0 0';

function positionOverlay(seconds) {
  const observation = sampleTrack(seconds);
  overlay.style.visibility = observation.visible ? 'visible' : 'hidden';
  if (!observation.visible) return;
  const values = homographyToMatrix3d(observation.frame.homography, {
    sourceWidth: trackData.source.width,
    sourceHeight: trackData.source.height,
    outputWidth: placedVideo.width,
    outputHeight: placedVideo.height,
    offsetX: placedVideo.x,
    offsetY: placedVideo.y,
  });
  overlay.style.transform = `matrix3d(${values.join(',')})`;
}
```

Synchronize the footage before capturing an overlay frame. For a measured source frame, call `seekMedia(video, frameStart, {frameEnd})`, using its actual presentation timestamp and the next source frame's timestamp, or the final frame's known end. The helper samples the interior of that explicit interval, checks that the landed playback position remains inside it, and rejects intervals that collapse at browser microsecond precision. Do not invent the interval from nominal FPS for variable-frame-rate footage, or substitute the next sparse tracking observation when intermediate source-frame timestamps are missing.

Generic `seekMedia(video, time)` verifies readiness and coarse seekability; it does not prove decoded frame identity at an exact boundary. The tested Chrome path rounds the requested browser-clock target forward to an integer microsecond and avoids binary floating-point truncation below that tick. A new integer target triggers a seek even if only one microsecond separates it from the current clock. Post-seek validation allows at most two microseconds of playback-clock reporting error. This small reporting allowance is never used to skip an unverified seek, and it does not certify which source frame was decoded. The return value distinguishes `{requestedTime, seekTime, landedTime}` and includes `frameInterval` when supplied. Browser `currentTime` is an approximate playback position, not a decoded presentation timestamp; use presented-frame metadata or independent pixel comparisons when frame identity matters.

A time whose rounded representation reaches the source duration is rejected; use actual source-frame coverage instead of a nearly-end-of-file guess. This clock contract is tested on Chrome and does not promise identical timer precision in every browser.

The local renderer asset server supplies single HTTP byte ranges so HTML video can actually seek. A `seeked` event with stale frame-zero media no longer passes: the helper checks the landed timestamp and reports missing seekability or byte-range support. Range requests preserve hashes for the complete source asset.

Track `frame.time` is normalized to the first actual video timestamp, while `sourceTime` preserves the original timestamp. Keep any trim/time-offset mapping consistent between the video and tracking data. The tracker decodes stored pixels without metadata autorotation; normalize rotation metadata into pixels before tracking and browser rendering when the source carries a display rotation.

This is planar surface tracking. It is not general 3D camera reconstruction, depth-aware occlusion, automatic rotoscoping, or a guarantee of successful tracking through blur, featureless surfaces, or occlusion. A synthetic moving-board test checks geometry and data flow; it does not establish quality on natural live-action footage. Run browser-consumer tests with `node --test tests/test_motion_tracking_runtime.mjs`.
