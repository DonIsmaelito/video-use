import importlib.util
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HELPERS = Path(__file__).parents[1] / "helpers"
sys.path.insert(0, str(HELPERS))
try:
    SPEC = importlib.util.spec_from_file_location("openscreen_export", HELPERS / "openscreen.py")
    export = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(export)
finally:
    sys.path.pop(0)


def bundle(root):
    artifacts = {}
    for name, filename, data in [
        ("source", "recording.mp4", b"immutable source"),
        ("project", "demo.openscreen", b'{"version":2}'),
        ("spec", "demo-spec.json", b'{"schema_version":1}'),
    ]:
        path = root / filename
        path.write_bytes(data)
        artifacts[name] = {"path": filename, "sha256": export.sha256_file(path)}
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "status": "prepared", "render_verified": False,
        "artifacts": artifacts,
        "source_metadata": {"has_audio": False, "duration_s": 1},
        "expected_video": {"width": 1920, "height": 1080, "fps": 60,
                           "frame_count": 60, "duration_s": 1},
    }))
    return manifest


def native_completion(evidence):
    done = {"event": "done", "success": True, "outputPath": str(evidence / "native.mp4")}
    events = evidence / "native-events.jsonl"
    events.write_text(json.dumps(done) + "\n")
    (evidence / "native-stderr.log").write_text("")
    return {"elapsed_s": 0, "exit_code": 0, "events_sha256": export.sha256_file(events), "result": done}


class InputEvidenceTests(unittest.TestCase):
    def test_byte_changes_are_rejected_for_every_input(self):
        for name in ("recording.mp4", "demo.openscreen", "demo-spec.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = bundle(root)
                self.assertEqual(export.validate_inputs(manifest)["status"], "prepared")
                (root / name).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "changed"):
                    export.validate_inputs(manifest)

    def test_valid_hash_does_not_allow_paths_outside_the_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inside = root / "bundle"
            inside.mkdir()
            manifest = bundle(inside)
            outside = root / "outside.mp4"
            outside.write_bytes(b"outside")
            data = export.read_json(manifest)
            data["artifacts"]["source"] = {"path": "../outside.mp4", "sha256": export.sha256_file(outside)}
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "escaped"):
                export.validate_inputs(manifest)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inside = root / "bundle"
            inside.mkdir()
            manifest = bundle(inside)
            outside = root / "outside.mp4"
            outside.write_bytes(b"immutable source")
            (inside / "recording.mp4").unlink()
            (inside / "recording.mp4").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "escaped"):
                export.validate_inputs(manifest)


class NativeProtocolTests(unittest.TestCase):
    def test_requires_both_successful_exit_and_successful_done(self):
        cases = [
            ('print(\'{"event":"done","success":true}\')', True),
            ('print(\'{"event":"done","success":false}\')', False),
            ('print(\'{"event":"progress","percentage":100}\')', False),
            ('print(\'{"event":"done","success":true}\'); raise SystemExit(1)', False),
            ('print(\'{"event":"done","success":"true"}\')', False),
            ('print(\'{"event":"done","success":true}\'); print(\'{"event":"done","success":false}\')', False),
        ]
        for script, succeeds in cases:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as directory:
                evidence = Path(directory)
                args = ([sys.executable, "-c", script], dict(os.environ), evidence)
                if succeeds:
                    self.assertTrue(export.run_native(*args)["result"]["success"])
                else:
                    with self.assertRaisesRegex(ValueError, "export failed"):
                        export.run_native(*args)
                self.assertTrue((evidence / "native-events.jsonl").is_file())
                self.assertTrue((evidence / "native-stderr.log").is_file())

    def test_timeout_stops_the_process_and_keeps_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            script = 'import time; print("started", flush=True); time.sleep(10)'
            with self.assertRaises(subprocess.TimeoutExpired):
                export.run_native([sys.executable, "-c", script], dict(os.environ), evidence, timeout_s=0.2)
            self.assertIn("started", (evidence / "native-events.jsonl").read_text())


class PublicationTests(unittest.TestCase):
    def test_external_drive_publication_copies_then_links_without_overwrite(self):
        for conflict in (False, True):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, output = root / "ready.mp4", root / "out.mp4"
                source.write_bytes(b"verified render")
                if conflict:
                    output.write_bytes(b"existing output")
                real_link = os.link
                calls = []

                def cross_device_link(src, dst):
                    calls.append(src)
                    if len(calls) == 1:
                        raise OSError(errno.EXDEV, "different filesystem")
                    return real_link(src, dst)

                with patch.object(export.os, "link", side_effect=cross_device_link):
                    if conflict:
                        with self.assertRaises(FileExistsError):
                            export.publish_file(source, output)
                        self.assertEqual(output.read_bytes(), b"existing output")
                        self.assertTrue(source.exists())
                    else:
                        export.publish_file(source, output)
                        self.assertEqual(output.read_bytes(), b"verified render")
                        self.assertFalse(source.exists())
                self.assertEqual(list(root.glob(".openscreen-*")), [])

    def test_existing_output_is_never_overwritten_or_rendered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "existing.mp4"
            output.write_bytes(b"previous delivery")
            with patch.object(export, "runtime_command") as runtime:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    export.export_project(root / "missing.json", root, root, output)
            runtime.assert_not_called()
            self.assertEqual(output.read_bytes(), b"previous delivery")

    def _export_with(self, root, before_native=None, before_verify=None):
        manifest = bundle(root)
        output = root / "delivery.mp4"

        def native(command, env, evidence, **kwargs):
            (evidence / "native.mp4").write_bytes(b"native picture")
            if before_native:
                before_native(manifest, output)
            return native_completion(evidence)

        def remux(command, **kwargs):
            Path(command[-1]).write_bytes(b"verified picture")
            return subprocess.CompletedProcess(command, 0, "", "")

        def verify(path, expected, audio):
            if before_verify:
                before_verify(manifest, output)
            return {"streams": []}

        with (
            patch.object(export, "runtime_command", return_value=(["fake-native"], {})),
            patch.object(export, "run_native", side_effect=native),
            patch.object(export, "checked", side_effect=remux),
            patch.object(export, "probe", return_value={"streams": [{"codec_type": "video"}]}),
            patch.object(export, "verify_media", side_effect=verify),
        ):
            return export.export_project(manifest, root, root, output)

    def test_publication_race_does_not_replace_another_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def race(manifest, output):
                output.write_bytes(b"another delivery arrived")
            with self.assertRaises(FileExistsError):
                self._export_with(root, before_verify=race)
            self.assertEqual((root / "delivery.mp4").read_bytes(), b"another delivery arrived")
            reports = list(root.glob("export-*/result.json"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(export.read_json(reports[0])["status"], "failed")

    def test_manifest_cannot_change_during_native_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def mutate(manifest, output):
                data = export.read_json(manifest)
                data["timeline"] = {"speed": 2}
                manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "[Mm]anifest.*changed"):
                self._export_with(root, before_native=mutate)
            self.assertFalse((root / "delivery.mp4").exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class MediaVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.audio = cls.root / "audio.mp4"
        cls.silent = cls.root / "silent.mp4"
        cls.wrong_color = cls.root / "wrong-color.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=60",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-bsf:v", "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
            "-movflags", "+faststart", str(cls.audio),
        ], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(cls.audio), "-map", "0:v:0",
                        "-c", "copy", str(cls.silent)], check=True, capture_output=True)
        subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(cls.silent), "-c", "copy", "-bsf:v",
            "h264_metadata=colour_primaries=6:transfer_characteristics=6:matrix_coefficients=6",
            "-colorspace", "smpte170m", "-color_trc", "smpte170m", "-color_primaries", "smpte170m",
            str(cls.wrong_color),
        ], check=True, capture_output=True)
        cls.expected = {"width": 320, "height": 180, "fps": 60, "frame_count": 60, "duration_s": 1}

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_real_silent_and_audio_videos_decode_and_verify(self):
        for path, audio in [(self.silent, False), (self.audio, True)]:
            with self.subTest(audio=audio):
                data = export.verify_media(path, self.expected, audio)
                self.assertEqual(data["decode_verification"]["frame_count"], 60)

    def test_wrong_duration_dimensions_frames_and_audio_are_rejected(self):
        for field, value in [("duration_s", 2), ("width", 640), ("frame_count", 61)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                export.verify_media(self.silent, {**self.expected, field: value}, False)
        with self.assertRaisesRegex(ValueError, "Audio"):
            export.verify_media(self.silent, self.expected, True)
        with self.assertRaisesRegex(ValueError, "Audio"):
            export.verify_media(self.audio, self.expected, False)

    def test_incorrect_color_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "BT709"):
            export.verify_media(self.wrong_color, self.expected, False)

    def test_decode_count_is_required_even_without_a_declared_frame_count(self):
        metadata = export.probe(self.silent)
        metadata["streams"][0].pop("nb_frames", None)
        for progress, valid in [
            ("frame=30\nprogress=continue\nframe=60\nprogress=end\n", True),
            ("frame=59\nprogress=end\n", False),
            ("frame=60\nprogress=continue\n", False),
        ]:
            response = subprocess.CompletedProcess([], 0, progress, "")
            with self.subTest(progress=progress), patch.object(export, "probe", return_value=metadata):
                with patch.object(export, "checked", return_value=response) as decode:
                    if valid:
                        self.assertEqual(export.verify_media(self.silent, self.expected, False)["decode_verification"]["frame_count"], 60)
                    else:
                        with self.assertRaises(ValueError):
                            export.verify_media(self.silent, self.expected, False)
                decode.assert_called_once()
                self.assertIn("-xerror", decode.call_args.args[0])
                self.assertIn("passthrough", decode.call_args.args[0])

    def test_truncated_media_cannot_pass_verification(self):
        broken = self.root / "broken.mp4"
        broken.write_bytes(self.silent.read_bytes()[:300])
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            export.verify_media(broken, self.expected, False)

    def test_export_preserves_original_aac_even_when_native_has_no_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = bundle(root)
            shutil.copy2(self.audio, root / "recording.mp4")
            data = export.read_json(manifest)
            data["artifacts"]["source"]["sha256"] = export.sha256_file(root / "recording.mp4")
            data["expected_video"] = self.expected
            manifest.write_text(json.dumps(data))

            def native(command, env, evidence, **kwargs):
                shutil.copy2(self.silent, evidence / "native.mp4")
                return native_completion(evidence)

            with (
                patch.object(export, "runtime_command", return_value=(["fake-native"], {})),
                patch.object(export, "run_native", side_effect=native),
            ):
                result = export.export_project(manifest, root, root, root / "delivery.mp4")
            self.assertEqual(result["status"], "technically_verified")
            self.assertEqual(result["visual_review"], "pending")
            def aac_bytes(path):
                return subprocess.check_output([
                    "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                    "-c", "copy", "-f", "adts", "pipe:1",
                ])
            self.assertEqual(aac_bytes(self.audio), aac_bytes(root / "delivery.mp4"))


class ResumeTests(unittest.TestCase):
    def failed_export(self, root):
        manifest = bundle(root)
        def native(command, env, evidence, **kwargs):
            (evidence / "native.mp4").write_bytes(b"completed immutable native picture")
            return native_completion(evidence)
        def failed_mux(command, **kwargs):
            Path(command[-1]).write_bytes(b"incomplete mux")
            raise subprocess.CalledProcessError(1, command, output="mux progress", stderr="No space left on device")
        with (
            patch.object(export, "runtime_command", return_value=(["fake-native"], {})),
            patch.object(export, "run_native", side_effect=native),
            patch.object(export, "probe", return_value={"streams": [{"codec_type": "video"}]}),
            patch.object(export, "checked", side_effect=failed_mux),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                export.export_project(manifest, root, root, root / "delivery.mp4")
        report = next(root.glob("export-*/result.json"))
        return manifest, report

    def test_completed_render_is_checkpointed_before_failed_mux(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, report = self.failed_export(root)
            result = export.read_json(report)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["manifest_sha256"], export.sha256_file(manifest))
            self.assertEqual(result["native_sha256"], export.sha256_file(report.parent / "native.mp4"))
            attempt = result["finalization_attempts"][0]
            self.assertEqual((report.parent / attempt["ready_path"]).read_bytes(), b"incomplete mux")
            details = attempt["subprocess_error"]
            self.assertEqual((report.parent / details["stderr"]).read_text(), "No space left on device")
            self.assertEqual((report.parent / details["stdout"]).read_text(), "mux progress")

    def test_resume_retries_only_delivery_with_a_new_ready_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, report = self.failed_export(root)
            partial = export.read_json(report)["finalization_attempts"][0]["ready_path"]
            def remux(command, **kwargs):
                Path(command[-1]).write_bytes(b"complete verified mux")
                return subprocess.CompletedProcess(command, 0, "", "")
            with (
                patch.object(export, "runtime_command") as runtime,
                patch.object(export, "run_native") as native,
                patch.object(export, "probe", return_value={"streams": [{"codec_type": "video"}]}),
                patch.object(export, "checked", side_effect=remux),
                patch.object(export, "verify_media", return_value={"streams": []}),
            ):
                result = export.resume_export(report, manifest, root / "delivery.mp4")
            native.assert_not_called()
            runtime.assert_not_called()
            self.assertEqual(result["status"], "technically_verified")
            self.assertEqual((root / "delivery.mp4").read_bytes(), b"complete verified mux")
            self.assertEqual((report.parent / partial).read_bytes(), b"incomplete mux")
            self.assertEqual(len(result["finalization_attempts"]), 2)
            self.assertNotEqual(result["finalization_attempts"][1]["ready_path"], partial)
            self.assertTrue((report.parent / "native.mp4").exists())

    def test_resume_rejects_changed_native_manifest_or_evidence(self):
        for changed in ("native.mp4", "native-events.jsonl", "manifest.json"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, report = self.failed_export(root)
                path = manifest if changed == "manifest.json" else report.parent / changed
                path.write_bytes(path.read_bytes() + b" ")
                with patch.object(export, "run_native") as native, patch.object(export, "checked") as command:
                    with self.assertRaisesRegex(ValueError, "changed"):
                        export.resume_export(report, manifest, root / "delivery.mp4")
                native.assert_not_called()
                command.assert_not_called()
                self.assertFalse((root / "delivery.mp4").exists())

    def test_resume_rejects_unbound_or_misdirected_completion(self):
        for failure in ("missing_hash", "wrong_path", "failed_exit"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, report = self.failed_export(root)
                result = export.read_json(report)
                if failure == "missing_hash":
                    result.pop("native_sha256")
                elif failure == "wrong_path":
                    result["native"]["result"]["outputPath"] = str(root / "unrelated.mp4")
                    events = report.parent / "native-events.jsonl"
                    events.write_text(json.dumps(result["native"]["result"]) + "\n")
                    result["native"]["events_sha256"] = export.sha256_file(events)
                else:
                    result["native"]["exit_code"] = 1
                report.write_text(json.dumps(result))
                with self.assertRaises(ValueError):
                    export.resume_export(report, manifest, root / "delivery.mp4")

    def test_failed_report_write_preserves_native_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "result.json"
            report.write_text('{"status":"native_complete"}')
            with patch.object(export.json, "dump", side_effect=OSError(errno.ENOSPC, "disk full")):
                with self.assertRaises(OSError):
                    export.write_report(report, {"status": "failed"})
            self.assertEqual(report.read_text(), '{"status":"native_complete"}')
            self.assertEqual(list(report.parent.glob(".result-*")), [])


class RuntimeEvidenceTests(unittest.TestCase):
    def test_runtime_rejects_changed_library_or_integration_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, app = root / "runtime", root / "Openscreen.app"
            addon = app / "Contents/Resources/electron/native/bin/darwin-arm64/compositor_view.node"
            addon.parent.mkdir(parents=True)
            addon.write_bytes(b"native addon")
            library = addon.with_name("libavcodec.dylib")
            library.write_bytes(b"tested codec library")
            electron = runtime / "node_modules/.bin/electron"
            electron.parent.mkdir(parents=True)
            electron.write_text("runtime")
            built = runtime / "compiled.js"
            built.write_text("tested code")
            stamp = {
                "upstream_sha": export.UPSTREAM_SHA,
                "patch_sha256": export.sha256_file(export.ROOT / "integrations/openscreen/patches/cli-source-dimensions.patch"),
                "files": {"compiled.js": export.sha256_file(built)},
                "native_addon_sha256": export.sha256_file(addon),
                "native_files": {p.name: export.sha256_file(p) for p in (addon, library)},
            }
            stamp_path = runtime / "video-use-runtime.json"
            stamp_path.write_text(json.dumps(stamp))
            with patch.dict(os.environ, {"ELECTRON_RUN_AS_NODE": "1"}):
                command, env = export.runtime_command(runtime, app)
            self.assertEqual(command, [str(electron.resolve()), str(runtime.resolve())])
            self.assertNotIn("ELECTRON_RUN_AS_NODE", env)
            library.write_bytes(b"incompatible library")
            with self.assertRaisesRegex(ValueError, "Native library changed"):
                export.runtime_command(runtime, app)
            library.write_bytes(b"tested codec library")
            stamp["patch_sha256"] = "stale patch"
            stamp_path.write_text(json.dumps(stamp))
            with self.assertRaisesRegex(ValueError, "different integration patch"):
                export.runtime_command(runtime, app)


if __name__ == "__main__":
    unittest.main()
