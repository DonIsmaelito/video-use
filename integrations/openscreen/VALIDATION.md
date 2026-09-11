# Validation record

Validated locally on Apple Silicon macOS using OpenScreen v1.11.0
(`47ab52fd0907ed07336fa1ff868e671d5d5a469f`) and the included geometry patch.

- 48 Video Use tests pass, including 32 OpenScreen adapter tests. Media tests
  use actual ffmpeg; wrapper failure tests simulate the native subprocess.
- The patched upstream runtime passed both TypeScript checks, changed-file
  linting, the Vite build and 2,690 upstream tests (two skipped). The initial
  sparse checkout lacked some test fixtures; the affected tests passed after
  those tracked files were restored.
- The real native smoke test rendered a 4:3 source into 1080p. A white square
  measured 395x395 pixels in the encoded output, verifying preserved geometry.
  Delivered AAC packets matched the original source byte for byte.
- The full local product recording (2940x1760, 187.725 seconds) exported as
  1920x1080 H264 at 60fps: 11,264 frames, 187.733333 seconds, BT709 limited,
  no audio track. The 8.3ms difference is frame-grid rounding.
- Encoded overview/focus/result/end frames were inspected. The full timeline
  remained intact with eight brief focus moves and recurring complete app views.
- Native rendering took 99.71 seconds for that full recording. This is one
  local render, not an end-to-end benchmark or a promised speedup.
- Final packaging initially failed because the Mac ran out of disk space.
  The completed native picture was manually remuxed and fully decoded after
  cleanup. The output was not re-rendered. This exposed the need for the new
  hash-checked `resume` path, whose failure/recovery tests now pass.
- The final adapter also passed the actual native geometry/audio smoke after
  adding durable checkpoints and single-pass decode verification.

## Cursor and expressive background revision

- 77 repository tests pass. New cases cover capture provenance, preserved
  telemetry, cursor settings, hidden-interval rejection, interaction coverage,
  immutable wallpapers and the three-patch runtime stamp.
- The cursor loader fix passed 27 targeted upstream tests; the local wallpaper
  URL fix passed 36 native-bridge tests. Both TypeScript configurations and the
  Vite build passed. The native binary is still the official unmodified addon.
- Two actual native 15-second exports compared a normal size-3 pointer with
  the production size-4.5 pointer, click bounce 1.0 and interaction zooms. The
  fixture is explicitly synthetic: authored UI and 60Hz pointer samples, with
  a click at 4s and a drag at 10–11.5s. Both outputs fully decoded with 900 frames.
- Encoded cursor height increased from 87px to 130px (1.494x). The press was
  99px, rebound 151px. The camera magnified the scene 1.245x during the click;
  it shifted 282px following the drag versus zero in the control, and returned
  to final overview. These checks measure native output, not only JSON settings.
- The original click-bounce value 2.5 produced a visibly excessive press and
  rebound (52px to 182px). Production default and example were reduced to 1.0
  and the actual native test was repeated successfully.
- Review caught a native wallpaper loader issue: the editor understood file
  URLs but the image decoder needed a filesystem path. The bridge now decodes
  valid local URLs and rejects invalid, missing or remote wallpaper inputs.
- The refreshed original 187.725-second recording rendered with Aurora in
  99.20 seconds and delivered 11,264 frames at 1920x1080/60fps, 187.733333 seconds,
  BT709 limited, silent. The original baked cursor is retained; this particular
  MOV has no editable cursor telemetry.
- Two agents inspected the refreshed encoded timeline: 12 sample times and
  full-resolution overview/focus/end frames. Aurora loaded visibly, proportions
  stayed intact, rounded edges and shadow looked clean, and final overview showed
  the whole app and Download. No blocking findings, webcam or duplicate cursor
  were observed. This is sampled review, not a complete temporal watch-through.
- Packaging again hit the Mac's disk limit. An old downloadable test source
  and the failed mux partial were removed, retaining acquisition metadata,
  native output and error logs. iCloud hydration briefly delayed reading the
  manifest. The public `resume` command then packaged and fully verified the
  existing native render successfully. No second picture render was performed.
  For unattended use, choose local scratch storage with adequate free space;
  avoid an actively offloading iCloud project directory.
- New recordings use the actual CLI flag `--cursor editable-overlay` and the
  original recorder project. Baked cursor imports explicitly disable overlays.
  Per-sample hidden intervals fail because the pinned native binary ignores
  that field; the adapter does not pretend those intervals were respected.

Not tested here: native Browser Harness recording, recording permissions,
webcam capture, actual editable cursor capture, Windows/Linux operation, or
arbitrary OpenScreen GUI edits. The synthetic cursor test verifies export with
known telemetry, not capture. The internal-tool agent must validate the real
recording path separately as described in README.

The original media, generated demo and private logs are local artifacts and
are not included in this repository. The supplied smoke command is the public,
reproducible native runtime test.
