"""Real-encoder checks for shared still/audio composition mechanics."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


HELPER = Path(__file__).parents[1] / "helpers" / "media_sequence.py"
SPEC = importlib.util.spec_from_file_location("media_sequence", HELPER)
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class MediaSequenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="video-use-sequence-")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        Image.new("RGB", (160, 90), "#FF0000").save(self.path / "first.png")
        Image.new("RGB", (90, 160), "#0000FF").save(self.path / "second.png")

    def audio(self, name="voice.wav", duration=1.4, *, frequency=440):
        rate = 48000
        samples = np.sin(np.arange(round(duration * rate)) * 2 * np.pi * frequency / rate) * .4
        path = self.path / name
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes((samples * 32767).astype("<i2").tobytes())
        return path

    def compose(self, spec, name="output.mp4"):
        return media.compose({"width": 160, "height": 90, "fps": 12, **spec}, self.path / name, base=self.path, timeout=20)

    def pixels(self, path, time=0):
        result = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(path),
                                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                capture_output=True, check=True)
        return np.frombuffer(result.stdout, np.uint8).reshape(90, 160, 3)

    def decoded_audio(self, path):
        result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                                 "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True)
        return np.frombuffer(result.stdout, "<f4")

    def test_sequence_preserves_order_duration_canvas_and_contain_fit(self):
        report = self.compose({"background": "#00FF00", "items": [
            {"file": "first.png", "duration": .5},
            {"file": "second.png", "duration": .75, "fit": "contain"},
        ]})
        self.assertTrue(report["full_decode_verified"])
        self.assertEqual((report["width"], report["height"], report["frames"]), (160, 90, 15))
        self.assertAlmostEqual(report["duration"], 1.25, places=3)
        self.assertEqual(report["audio_tracks"], 0)
        self.assertEqual([i["start"] for i in report["timeline"]], [0, .5])
        first = self.pixels(report["output"], .2)
        second = self.pixels(report["output"], .8)
        self.assertGreater(first[45, 80, 0], 230)
        self.assertGreater(second[45, 80, 2], 230)
        self.assertGreater(second[45, 4, 1], 230)
        # faststart places the index before the encoded media.
        data = Path(report["output"]).read_bytes()
        self.assertLess(data.index(b"moov"), data.index(b"mdat"))

    def test_audio_offsets_trim_and_mix_preserve_timing(self):
        self.audio(duration=2)
        self.audio("music.wav", .2, frequency=130)
        report = self.compose({"items": [{"file": "first.png", "duration": 1.5}], "audio": [
            {"file": "voice.wav", "start": .3, "source_start": .5, "duration": .7},
            {"file": "music.wav", "duration": 1.5, "loop": True, "gain": .1},
        ]})
        samples = self.decoded_audio(report["output"])
        def rms(start, end):
            return float(np.sqrt(np.mean(samples[int(start * 48000):int(end * 48000)] ** 2)))
        self.assertGreater(rms(.45, .8), rms(.08, .2) * 4)
        self.assertGreater(rms(.45, .8), rms(1.15, 1.4) * 4)
        self.assertGreater(rms(1.15, 1.4), .005)  # The short music source really loops.
        self.assertAlmostEqual(len(samples) / 48000, 1.5, delta=.03)
        self.assertEqual(report["audio_tracks"], 2)

    def test_audio_mode_cover_waveform_and_nonframe_duration(self):
        self.audio(duration=1.31)
        report = self.compose({"mode": "audio", "cover": {"file": "first.png"},
                               "audio": [{"file": "voice.wav"}],
                               "waveform": {"x": 10, "y": 55, "width": 140, "height": 30, "color": "#FFFFFF"}})
        self.assertEqual(report["frames"], 16)
        self.assertGreaterEqual(report["duration"], 1.31)
        self.assertLess(report["duration"] - 1.31, 1 / 12)
        pixels = self.pixels(report["output"], .5)
        self.assertGreater(pixels[70:85, 12:148, 1].max(), 100)  # Actual audio draws the waveform.
        self.assertLess(pixels[20, 80, 1], 15)  # Cover color remains outside waveform.
        self.assertTrue(report["waveform"])

    def test_audio_mode_without_cover_and_rational_frame_rate(self):
        self.audio(duration=.6)
        report = self.compose({"mode": "audio", "background": "#003399", "fps": "24000/1001",
                               "audio": [{"file": "voice.wav", "fade": 0}]})
        self.assertEqual(report["fps"], "24000/1001")
        self.assertEqual(report["frames"], 15)
        self.assertGreater(self.pixels(report["output"], .2)[45, 80, 2], 135)

    def test_explicit_motion_changes_crop_without_changing_timing(self):
        source = Image.new("RGB", (160, 90), "black")
        draw = ImageDraw.Draw(source)
        draw.rectangle((0, 0, 45, 90), fill="white")
        draw.rectangle((115, 0, 160, 90), fill="red")
        source.save(self.path / "motion.png")
        report = self.compose({"items": [{"file": "motion.png", "duration": 1,
                                         "motion": {"zoom_start": 2, "zoom_end": 2,
                                                    "focus_start": [0, .5], "focus_end": [1, .5], "easing": "smooth"}}]})
        first = self.pixels(report["output"], 0)
        last = self.pixels(report["output"], 11 / 12)
        self.assertGreater(first[:, :, 1].mean(), last[:, :, 1].mean() + 80)
        self.assertAlmostEqual(report["duration"], 1)

    def test_rejects_accidental_audio_truncation_before_writing_output(self):
        self.audio(duration=2)
        output = self.path / "output.mp4"
        output.write_bytes(b"previous output")
        with self.assertRaisesRegex(ValueError, "Audio would be truncated"):
            self.compose({"items": [{"file": "first.png", "duration": 1}], "audio": [{"file": "voice.wav"}]})
        self.assertEqual(output.read_bytes(), b"previous output")

    def test_rejects_bad_dimensions_motion_and_waveform(self):
        base = {"items": [{"file": "first.png", "duration": 1}]}
        for extra, match in [({"width": 161}, "even"), ({"width": 8000}, "between"),
                             ({"waveform": {}}, "requires an audio"), ({"duration": 4}, "comes from items")]:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, match):
                self.compose({**base, **extra})
        with self.assertRaisesRegex(ValueError, "focus_end"):
            self.compose({"items": [{"file": "first.png", "duration": 1, "motion": {"focus_end": [4, .5]}}]})

    def test_source_files_cannot_be_overwritten_and_failure_is_atomic(self):
        self.audio("source.mp4", .2)  # Valid audio bytes, intentionally misleading suffix.
        original = (self.path / "source.mp4").read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite a source"):
            self.compose({"mode": "audio", "audio": [{"file": "source.mp4"}]}, name="source.mp4")
        self.assertEqual((self.path / "source.mp4").read_bytes(), original)
        (self.path / "not-an-image.png").write_text("corrupted image")
        (self.path / "output.mp4").write_bytes(b"existing draft")
        with self.assertRaises(OSError):
            self.compose({"items": [{"file": "not-an-image.png", "duration": 1}]})
        self.assertEqual((self.path / "output.mp4").read_bytes(), b"existing draft")
        self.assertFalse(list(self.path.glob(".media-sequence-*")))

    def test_cli_resolves_assets_from_spec_and_outputs_json(self):
        spec = self.path / "spec.json"
        spec.write_text(json.dumps({"width": 160, "height": 90, "fps": 12,
                                    "items": [{"file": "first.png", "duration": .5}]}))
        result = subprocess.run([sys.executable, str(HELPER), str(spec), "-o", str(self.path / "cli.mp4")],
                                cwd="/", capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report["frames"], 6)
        self.assertTrue(report["full_decode_verified"])


if __name__ == "__main__":
    unittest.main()
