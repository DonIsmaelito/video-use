import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))

SPEC = importlib.util.spec_from_file_location(
    "openscreen_project", Path(__file__).parents[1] / "helpers" / "openscreen_project.py"
)
project = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project)


def cue(settle=4, end=5):
    return {"settle_s": settle, "hold_end_s": end, "depth": 1,
            "focus": [0.65, 0.4], "reason": "Show the product action"}


class SpecTests(unittest.TestCase):
    def test_defaults_are_native_and_preserve_the_full_timeline(self):
        normalized = project.validate_spec({}, 187.725)
        data = project.build_project(Path("/bundle/recording.mov"), normalized)
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["media"]["cursorCaptureMode"], "system")
        for key in ("trimRegions", "speedRegions", "zoomRegions"):
            self.assertEqual(data["editor"][key], [])
        self.assertEqual(data["editor"]["cropRegion"], {"x": 0, "y": 0, "width": 1, "height": 1})
        self.assertFalse(data["editor"]["autoZoomEnabled"])
        self.assertFalse(data["editor"]["autoFocusAll"])
        self.assertEqual(normalized["background"]["preset"], "aurora")
        self.assertTrue(data["editor"]["wallpaper"].startswith("file://"))

    def test_explicit_gradients_retain_their_previous_native_settings(self):
        for raw in ({"colors": ["#ABCDEF", "#102030"]}, {"angle": 80}):
            with self.subTest(background=raw):
                normalized = project.validate_spec({"background": raw}, 10)
                self.assertNotIn("preset", normalized["background"])
                data = project.build_project(Path("/recording.mov"), normalized)
                colors = [c.lower() for c in raw.get("colors", ["#283653", "#101722"])]
                self.assertEqual(data["editor"]["wallpaper"],
                                 f"linear-gradient({raw.get('angle', 135)}deg, {colors[0]}, {colors[1]})")

    def test_preset_paths_can_point_to_the_reproducible_bundle(self):
        normalized = project.validate_spec({"background": {"preset": "spectrum", "padding": 25}}, 10)
        path = Path("/project with spaces/background.jpg")
        data = project.build_project(Path("/recording.mov"), normalized, wallpaper_path=path)
        self.assertEqual(data["editor"]["wallpaper"], path.as_uri())
        self.assertEqual(data["editor"]["padding"], 25)

    def test_cues_account_for_native_settle_offset(self):
        normalized = project.validate_spec({"zooms": [cue()]}, 12)
        region = project.build_project(Path("/recording.mov"), normalized)["editor"]["zoomRegions"][0]
        self.assertEqual(region["startMs"], 3500)
        self.assertEqual(region["endMs"], 5000)
        self.assertEqual(region["focusMode"], "manual")
        self.assertEqual(region["focus"], {"cx": 0.65, "cy": 0.4})

    def test_two_spaced_cues_keep_overview(self):
        self.assertEqual(len(project.validate_spec({"zooms": [cue(), cue(10, 11)]}, 15)["zooms"]), 2)

    def test_unknown_keys_and_invalid_values_are_rejected(self):
        bad = [
            {"duration": 5}, {"schema_version": True}, {"schema_version": 2},
            {"background": {"image": "wall.jpg"}}, {"background": {"colors": ["#ffffff"]}},
            {"background": {"colors": ["red", "#ffffff"]}},
            {"background": {"padding": float("nan")}}, {"background": {"padding": True}},
            {"background": {"motion_blur": 2}}, {"zooms": "automatic"},
            {"background": {"preset": "unknown"}}, {"background": {"preset": None}},
            {"background": {"preset": "aurora", "colors": ["#000000", "#ffffff"]}},
            {"background": {"preset": "aurora", "angle": 20}},
        ]
        for spec in bad:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                project.validate_spec(spec, 20)
        for key, value in [("depth", True), ("depth", 7), ("focus", [0, float("inf")]),
                           ("focus", [-0.1, 0.5]), ("reason", ""), ("extra", 1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                project.validate_spec({"zooms": [{**cue(), key: value}]}, 20)

    def test_effect_envelopes_cannot_run_off_the_video_or_join(self):
        for cues in ([cue(1, 2)], [cue(8, 9)], [cue(4, 9)],
                     [cue(), cue(7, 8)], [cue(8, 9), cue()]):
            with self.subTest(cues=cues), self.assertRaises(ValueError):
                project.validate_spec({"zooms": cues}, 10)

    def test_validation_does_not_mutate_input(self):
        spec = {"background": {"colors": ["#ABCDEF", "#102030"]}, "zooms": [cue()]}
        before = copy.deepcopy(spec)
        self.assertEqual(project.validate_spec(spec, 12)["background"]["colors"][0], "#abcdef")
        self.assertEqual(spec, before)


class ProbeTests(unittest.TestCase):
    def test_rejects_unsupported_metadata(self):
        stream = {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
                  "width": 320, "height": 180, "duration": "10", "color_range": "tv",
                  "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709"}
        cases = [("color_range", "pc"), ("color_transfer", "smpte2084"),
                 ("sample_aspect_ratio", "4:3"), ("side_data_list", [{"rotation": 90}]),
                 ("start_time", "1.0"), ("width", 319), ("duration", "nan"),
                 ("pix_fmt", "yuv420p10le")]
        for key, value in cases:
            result = subprocess.CompletedProcess([], 0, json.dumps({"streams": [{**stream, key: value}]}), "")
            with self.subTest(key=key), patch.object(project.subprocess, "run", return_value=result):
                with self.assertRaises(ValueError):
                    project.probe_source(Path(__file__))

    def test_duplicate_json_keys_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_text('{"zooms": [], "zooms": []}')
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                project.read_json(path)

    def test_audio_timing_and_track_count_must_preserve_the_recording(self):
        video = {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
                 "width": 320, "height": 180, "duration": "10", "color_range": "tv",
                 "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709"}
        audio = {"codec_type": "audio", "codec_name": "aac", "duration": "10", "start_time": "0"}
        for tracks in ([audio, audio], [{**audio, "start_time": "0.5"}],
                       [{**audio, "duration": "10.5"}], [{**audio, "duration": "nan"}]):
            result = subprocess.CompletedProcess([], 0, json.dumps({"streams": [video, *tracks]}), "")
            with self.subTest(tracks=tracks), patch.object(project.subprocess, "run", return_value=result):
                with self.assertRaises(ValueError):
                    project.probe_source(Path(__file__))
        result = subprocess.CompletedProcess([], 0, json.dumps({"streams": [video, audio]}), "")
        with patch.object(project.subprocess, "run", return_value=result):
            metadata = project.probe_source(Path(__file__))
            self.assertTrue(metadata["has_audio"])
            self.assertEqual(metadata["audio_duration_s"], 10)


class CaptureBundleTests(unittest.TestCase):
    def test_native_capture_preserves_hashed_telemetry_and_disables_webcam(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "capture.mp4"
            source.write_bytes(b"fixture source only for preparation not rendering")
            capture = root / "capture.openscreen"
            capture.write_text(json.dumps({"version": 2, "media": {
                "screenVideoPath": str(source), "cursorCaptureMode": "editable-overlay",
                "webcamVideoPath": "ignored-webcam.mp4"}}))
            sidecar = Path(str(source) + ".cursor.json")
            sidecar.write_text(json.dumps({"version": 2, "samples": [
                {"timeMs": 0, "cx": .4, "cy": .5, "interactionType": "move"},
                {"timeMs": 4000, "cx": .4, "cy": .5, "interactionType": "click"},
                {"timeMs": 4100, "cx": .4, "cy": .5, "interactionType": "mouseup"},
                {"timeMs": 9990, "cx": .4, "cy": .5, "interactionType": "move"}]}))
            spec = {"cursor": {"mode": "recorded"}}
            with patch.object(project, "probe_source", return_value={"duration_s": 10}):
                with self.assertRaisesRegex(ValueError, "recording-project"):
                    project.prepare_project(source, spec, root / "missing")
                report = project.prepare_project(source, spec, root / "bundle", recording_project=capture)
            data = project.read_json(Path(report["project_path"]))
            self.assertNotIn("webcamVideoPath", data["media"])
            self.assertEqual(data["editor"]["webcamLayoutPreset"], "no-webcam")
            self.assertTrue(data["editor"]["cursorShow"])
            self.assertEqual(data["editor"]["cursorSize"], 4.5)
            self.assertEqual(data["editor"]["zoomRegions"][0]["focusMode"], "auto")
            copied_sidecar = Path(str(Path(report["source_path"])) + ".cursor.json")
            self.assertEqual(sidecar.read_bytes(), copied_sidecar.read_bytes())
            self.assertEqual(report["artifacts"]["cursor_data"]["sha256"], project.sha256_file(sidecar))
            for artifact in report["artifacts"].values():
                self.assertEqual(project.sha256_file(root / "bundle" / artifact["path"]), artifact["sha256"])
            hidden_data = project.read_json(sidecar)
            hidden_data["samples"][1]["visible"] = False
            sidecar.write_text(json.dumps(hidden_data))
            with patch.object(project, "probe_source", return_value={"duration_s": 10}):
                with self.assertRaisesRegex(ValueError, "hidden cursor intervals"):
                    project.prepare_project(source, spec, root / "hidden", recording_project=capture)
            self.assertFalse((root / "hidden").exists())

    def test_manual_and_automatic_cameras_cannot_overlap(self):
        with self.assertRaisesRegex(ValueError, "combining them can overlap"):
            project.validate_spec({"cursor": {"mode": "recorded"}, "zooms": [cue()]}, 12)
        spec = project.validate_spec({"cursor": {"mode": "recorded", "interaction_zooms": False},
                                      "zooms": [cue()]}, 12)
        self.assertFalse(spec["cursor"]["interaction_zooms"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class RealMediaTests(unittest.TestCase):
    def test_prepare_preserves_source_and_creates_portable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source with spaces.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30",
                "-t", "1", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-color_range", "tv", "-colorspace", "bt709", "-color_trc", "bt709",
                "-color_primaries", "bt709", "-bsf:v",
                "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
                str(source),
            ], check=True, capture_output=True)
            original = project.sha256_file(source)
            source.with_suffix(".cursor.json").write_text("[]")
            report = project.prepare_project(source, {}, root / "bundle")
            self.assertEqual(project.sha256_file(source), original)
            self.assertEqual(project.sha256_file(Path(report["source_path"])), original)
            self.assertEqual(report["source_metadata"]["width"], 320)
            self.assertEqual(report["source_metadata"]["height"], 240)
            self.assertEqual(report["source_metadata"]["duration_s"], 1)
            self.assertFalse(report["source_metadata"]["has_audio"])
            self.assertEqual(report["expected_video"]["frame_count"], 60)
            self.assertEqual(report["expected_video"]["duration_s"], 1)
            self.assertFalse(report["render_verified"])
            self.assertEqual(report["status"], "prepared")
            self.assertEqual(report["timeline"]["source_end_s"], 1)
            saved = project.read_json(Path(report["manifest_path"]))
            self.assertIn("background", saved["artifacts"])
            wallpaper = root / "bundle" / saved["artifacts"]["background"]["path"]
            data = project.read_json(Path(report["project_path"]))
            self.assertEqual(data["editor"]["wallpaper"], wallpaper.resolve().as_uri())
            for artifact in saved["artifacts"].values():
                self.assertFalse(Path(artifact["path"]).is_absolute())
                self.assertEqual(project.sha256_file(root / "bundle" / artifact["path"]), artifact["sha256"])
            self.assertEqual(list((root / "bundle").glob("*.cursor.json")), [])
            with self.assertRaisesRegex(ValueError, "already exists"):
                project.prepare_project(source, {}, root / "bundle")
            gradient = project.prepare_project(source, {"background": {"angle": 135}}, root / "gradient")
            self.assertNotIn("background", gradient["artifacts"])
            self.assertEqual(list((root / "gradient").glob("background-*.jpg")), [])

    def test_failed_copy_cleans_only_its_new_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"source must remain intact")
            metadata = {"duration_s": 2, "width": 1920, "height": 1080}
            with patch.object(project, "probe_source", return_value=metadata):
                with patch.object(project.shutil, "copy2", side_effect=OSError("copy failed")):
                    with self.assertRaisesRegex(OSError, "copy failed"):
                        project.prepare_project(source, {}, root / "bundle")
            self.assertEqual(source.read_bytes(), b"source must remain intact")
            self.assertFalse((root / "bundle").exists())


if __name__ == "__main__":
    unittest.main()
