# OpenScreen product demo integration

Video Use authors a compact editing brief. **OpenScreen supplies the real native
compositor**, camera easing, backgrounds, shadow, rounded window and encoder.
This integration contains no alternate renderer and does not change the signed
OpenScreen application. It is isolated from the video-use-fast cloud/UI work.

## Start here

Tested platform: Apple Silicon macOS. Requirements: Python 3.10+, ffmpeg/ffprobe,
Git, Node/npm, and the official **OpenScreen 1.11.0** app. The upstream project
pins Node 22.22.1/npm 10.9.4. Use those versions for new installations.

Install the [official Apple Silicon 1.11.0 release](https://github.com/getopenscreen/openscreen/releases/download/v1.11.0/Openscreen-macOS-Apple-Silicon-1.11.0.dmg)
as `/Applications/Openscreen.app`. Keep several GB free for the development
runtime and exported media. Then run from this Video Use checkout:

```sh
python3 integrations/openscreen/setup.py --runtime "$HOME/Developer/openscreen-runtime"
```

Setup clones the pinned upstream source, applies one small CLI geometry fix,
installs its locked dependencies, tests the fix and builds the JS application.
The native addon comes from the official installed app; no Rust rebuild or
modification of its signed bundle is needed. Setup is done once, not per video.
The stamp records built files, the patch and all native-library hashes so export rejects a
changed or mismatched runtime.

Confirm the installed native runtime with a two-second 4:3 geometry/audio test:

```sh
python3 integrations/openscreen/smoke.py \
  --runtime "$HOME/Developer/openscreen-runtime" --out /path/to/edit/native-smoke
```

This calls the actual renderer, measures whether a square remains square, and
compares delivered AAC packets with the original. Unit tests run separately:
`python3 -m unittest discover -s tests -p 'test_openscreen*.py'`.

```sh
python3 helpers/openscreen.py prepare /path/to/recording.mov \
  --spec integrations/openscreen/example-spec.json \
  --out /path/to/edit/demo

python3 helpers/openscreen.py export /path/to/edit/demo/manifest.json \
  --runtime "$HOME/Developer/openscreen-runtime" \
  --out /path/to/edit/demo.mp4
```

Each preparation uses a **new directory** and copies the original beside
`demo.openscreen`, satisfying OpenScreen's media-path access rule. Sources and
previous outputs are not overwritten. The example cue needs a recording at
least 9 seconds long; use `"zooms": []` for a simple background-only test.

The source route accepts SDR H264/HEVC, 8-bit yuv420p, BT709 limited range,
square pixels and no rotation metadata. Unsupported sources fail before
rendering; normalization must be explicit. This initial route fixes delivery
at 1920x1080, H264, 60fps because the pinned OpenScreen CLI has that frame-rate
contract. Original time is preserved with frame-grid rounding, not cuts or
speed changes. It is a contained first integration, not support for every
OpenScreen editor feature.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `helpers/openscreen_project.py` | Validate cues/source; copy media; write project and hashed preparation manifest |
| `helpers/openscreen.py` | Invoke native CLI; retain real logs; verify and publish MP4 without overwrites |
| `setup.py` | Build and fingerprint the pinned runtime using the installed native addon |
| `patches/cli-source-dimensions.patch` | Fill actual source dimensions before OpenScreen lays out an imported recording |
| `references/openscreen-product-demo.md` | Product-demo editorial guidance and visual review |

The patch is against upstream commit
`47ab52fd0907ed07336fa1ff868e671d5d5a469f` (`v1.11.0`). The CLI originally probed
dimensions for output sizing but omitted them from its migrated document.
Native layout consequently assumed a 16:9 source and stretched other ratios.
The fix updates the primary asset metadata before the existing scene builder;
regression tests cover the supplied 2940x1760 ratio, 4:3 and portrait sources.

## What the internal-tool agent should integrate

1. Let Browser Harness perform browser actions. Capture a real continuous
   recording; a sequence of action screenshots is not an equivalent video.
2. For already-recorded footage with a visible cursor, use `prepare` and
   `export` above. The cue specification is the agent's editing interface;
   all effect implementation stays inside OpenScreen.
3. For new native recordings, OpenScreen already has `sources`, `record`,
   `pack` and `export` commands. Use its returned `.openscreen` project and
   `<video>.cursor.json` together to retain editable cursor data. **Do not
   pass that project through the import helper**, which deliberately treats
   the source cursor as baked in. Native recording integration is the next
   separate path for the Browser Harness agent to wire and test.
4. Keep the recorder process alive while Browser Harness acts. Wait for the
   actual recording-started event before actions, then write `stop\n` to its
   stdin after the task finishes and await the successful final event. Use a
   local desktop session with required OS recording permissions.
5. Read real NDJSON progress for UI updates. `info --json` returns a plain
   summary; export returns `started/progress/done` events. Never manufacture
   preview frames or announce success based only on a filename.
6. Keep project artifacts local to a job, store native stdout/stderr, and wait
   for technical verification plus visual review before publishing the final
   download. The native compositor is a desktop/native dependency, not a
   browser-only library to import into a web server.

Raw native commands, using the built checkout and official app's addon:

```sh
export OPENSCREEN_COMPOSITOR_VIEW_NODE="/Applications/Openscreen.app/Contents/Resources/electron/native/bin/darwin-arm64/compositor_view.node"
env -u ELECTRON_RUN_AS_NODE "$HOME/Developer/openscreen-runtime/node_modules/.bin/electron" \
  "$HOME/Developer/openscreen-runtime" sources --json
```

For native **recording**, use the installed app binary, which also includes
capture helpers. The development runtime override above supplies the exporter,
not all capture helper paths:

```sh
/Applications/Openscreen.app/Contents/MacOS/Openscreen \
  record --window "My Product" --project /path/to/demo.openscreen --json
```

Native recordings and direct editor changes do not use the import helper's
manifest contract. Their integration must preserve telemetry, validate their
own scene inputs and perform the same final-media checks. We do not claim
Browser Harness recording has been tested by the imported-video smoke test.

## Delivery and known limits

- The original recording is preserved at 1x. A single source audio track is
  taken from the original during final mux, preventing the native exporter's
  silent-audio fallback from hiding a decode error. AAC is copied; other audio
  codecs are encoded to AAC. Silent recordings deliver no audio track.
- The final mux copies the video bitstream, adds known BT709 metadata and
  `faststart`, then checks dimensions, fps, frame count, duration and complete
  decoding. Frame counting happens during that single full decode. No second
  image encode or separate frame-count decode occurs.
- Source/project/spec hashes are checked before and after export. Failed jobs
  retain evidence but publish no final output. Existing outputs are never
  replaced, including when another process creates the destination mid-render.
- A completed native render is checkpointed before packaging. If packaging
  fails, retry without rendering again:
  `python3 helpers/openscreen.py resume /path/to/export/result.json /path/to/manifest.json --out /path/to/final.mp4`.
  Resume requires unchanged source, project, native output and completion
  evidence. It retains earlier failed attempts rather than hiding their errors.
- The native process has no graceful per-render abort. Interrupting our wrapper
  terminates its whole process group; a watchdog bounds execution time.
- Technical verification is not a visual acceptance. Inspect encoded frames
  and actual motion, particularly when adding backgrounds or new source ratios.
- Native easing and background units differ from the earlier custom renderer:
  padding is OpenScreen's 0–100 slider; gradients use two colors; zoom depths
  are 1.25x, 1.5x, 1.8x, 2.2x, 3.5x and 5x. Custom easing, mesh CSS, arbitrary
  zoom scales and cursor replacement are not exposed by this import contract.

Authoritative context: [recording](https://getopenscreen.com/docs/recording/),
[editing](https://getopenscreen.com/docs/editing-timeline/),
[native export](https://getopenscreen.com/docs/export/), and the
[pinned CLI source/docs](https://github.com/getopenscreen/openscreen/blob/v1.11.0/docs/cli.md).
Some upstream CLI prose still describes the old Pixi/WebCodecs exporter; the
pinned implementation and the native export documentation describe the path
used here. Preserve the upstream license when distributing its software.
