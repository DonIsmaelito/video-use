import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "cursor", Path(__file__).parents[1] / "helpers/openscreen_cursor.py")
cursor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cursor)


class CursorTests(unittest.TestCase):
    def test_baked_cursor_never_gets_a_second_overlay(self):
        self.assertEqual(cursor.editor_cursor_settings(cursor.validate_cursor_spec({})),
                         {"cursorShow": False})
        with self.assertRaisesRegex(ValueError, "require mode recorded"):
            cursor.validate_cursor_spec({"size": 4.5})

    def test_enlarged_recorded_cursor_settings_and_strict_schema(self):
        spec = cursor.validate_cursor_spec({"mode": "recorded"})
        self.assertEqual(cursor.editor_cursor_settings(spec)["cursorSize"], 4.5)
        for raw in ({"size": True}, {"size": float("nan")}, {"click_bounce": 7},
                    {"interaction_zooms": "yes"}, {"zoom_depth": 1.5}, {"typo": 1}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                cursor.validate_cursor_spec({"mode": "recorded", **raw})

    def test_requires_recorders_mode_source_and_sidecar_together(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mov"
            source.touch()
            project_path = root / "capture.openscreen"
            project = {"version": 2, "media": {"screenVideoPath": source.as_uri(),
                       "cursorCaptureMode": "editable-overlay"}}
            with self.assertRaisesRegex(ValueError, "missing its cursor sidecar"):
                cursor.validate_capture_project(project, project_path, source)
            sidecar = Path(str(source) + ".cursor.json")
            sidecar.write_text('{"samples": []}')
            self.assertEqual(cursor.validate_capture_project(project, project_path, source), sidecar.resolve())
            project["media"]["cursorCaptureMode"] = "system"
            with self.assertRaisesRegex(ValueError, "editable-overlay"):
                cursor.validate_capture_project(project, project_path, source)
            project["media"]["cursorCaptureMode"] = "editable-overlay"
            other = root / "other.mov"
            other.touch()
            with self.assertRaisesRegex(ValueError, "different source"):
                cursor.validate_capture_project(project, project_path, other)


if __name__ == "__main__":
    unittest.main()
