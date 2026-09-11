import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


SPEC = importlib.util.spec_from_file_location(
    "openscreen_backgrounds", Path(__file__).parents[1] / "helpers" / "openscreen_backgrounds.py"
)
backgrounds = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backgrounds)


class BackgroundPresetTests(unittest.TestCase):
    def test_catalog_has_three_unique_portable_images_with_provenance(self):
        catalog = backgrounds.list_backgrounds()
        self.assertEqual([asset["name"] for asset in catalog], ["aurora", "spectrum", "coastline"])
        self.assertEqual([asset["name"] for asset in catalog if asset["default"]], ["aurora"])
        for asset in catalog:
            with self.subTest(preset=asset["name"]):
                path = backgrounds.resolve_preset(asset["name"])
                self.assertTrue(path.is_absolute())
                self.assertEqual(str(path), asset["path"])
                self.assertEqual(asset["license"], "MIT")
                self.assertEqual(len(asset["upstream_revision"]), 40)
                self.assertTrue(asset["upstream_path"].startswith("public/wallpapers/"))
                with Image.open(path) as image:
                    self.assertEqual(image.size, (asset["width"], asset["height"]))
                    self.assertEqual(image.format, "JPEG")
                    image.verify()
        json.dumps(catalog)

    def test_catalog_can_be_changed_by_caller_without_changing_defaults(self):
        catalog = backgrounds.list_backgrounds()
        catalog[0]["name"] = "changed"
        self.assertEqual(backgrounds.list_backgrounds()[0]["name"], backgrounds.DEFAULT_PRESET)

    def test_unknown_names_and_paths_fail_before_export(self):
        for name in ("unknown", "../aurora", "aurora.jpg", "https://example.com/image.jpg", None, 1):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unknown OpenScreen"):
                backgrounds.resolve_preset(name)

    def test_changed_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            manifest = json.loads((backgrounds.BACKGROUND_DIR / "manifest.json").read_text())
            (folder / "manifest.json").write_text(json.dumps(manifest))
            (folder / "aurora.jpg").write_bytes(b"not the pinned wallpaper")
            with patch.object(backgrounds, "BACKGROUND_DIR", folder):
                with self.assertRaisesRegex(ValueError, "has changed"):
                    backgrounds.resolve_preset("aurora")

    def test_missing_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "manifest.json").write_bytes((backgrounds.BACKGROUND_DIR / "manifest.json").read_bytes())
            with patch.object(backgrounds, "BACKGROUND_DIR", folder):
                with self.assertRaises(FileNotFoundError):
                    backgrounds.resolve_preset("aurora")


if __name__ == "__main__":
    unittest.main()
