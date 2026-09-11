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

Not tested here: native Browser Harness recording, recording permissions,
webcam capture, editable cursor capture, Windows/Linux operation, or arbitrary
OpenScreen GUI edits. The first integration supports imported recordings with
their captured cursor. The internal-tool agent should validate the native
recording route separately as described in README.

The original media, generated demo and private logs are local artifacts and
are not included in this repository. The supplied smoke command is the public,
reproducible native runtime test.
