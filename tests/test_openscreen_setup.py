import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SETUP_PATH = Path(__file__).parents[1] / "integrations/openscreen/setup.py"
SPEC = importlib.util.spec_from_file_location("openscreen_setup", SETUP_PATH)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class RuntimeStampTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.git("init", "-q")
        for name in ("geometry.ts", "cursor.ts", "wallpaper.ts"):
            (self.runtime / name).write_text("before\n")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "fixture")
        self.revision = self.git("rev-parse", "HEAD").strip()
        self.patches = []
        for name in ("geometry.ts", "cursor.ts", "wallpaper.ts"):
            (self.runtime / name).write_text("after\n")
            patch_path = self.root / f"{name}.patch"
            patch_path.write_text(self.git("diff", "--", name))
            self.patches.append(patch_path)
        for name in ("dist/index.html", "dist-electron/main.js",
                     "src/cli/cursorSettings.test.ts",
                     "electron/native-bridge/services/compositorViewService.ts",
                     "src/components/video-editor/projectPersistence.ts"):
            file = self.runtime / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("fixture\n")
        self.app = self.root / "Openscreen.app"
        self.addon = self.app / "Contents/Resources/electron/native/bin/darwin-arm64/compositor_view.node"
        self.addon.parent.mkdir(parents=True)
        self.addon.write_bytes(b"native fixture")
        self.addCleanup(patch.stopall)
        patch.object(setup, "SHA", self.revision).start()
        patch.object(setup, "PATCHES", tuple(self.patches)).start()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.runtime, text=True)

    def test_stamp_binds_every_patch_and_cursor_source(self):
        setup.stamp(self.runtime, self.app)
        stamp = json.loads((self.runtime / "video-use-runtime.json").read_text())
        self.assertEqual(stamp["patches"], {
            path.name: setup.digest(path) for path in self.patches
        })
        self.assertEqual(stamp["native_addon_sha256"], setup.digest(self.addon))
        for name in ("src/cli/cursorSettings.test.ts",
                     "electron/native-bridge/services/compositorViewService.ts",
                     "src/components/video-editor/projectPersistence.ts"):
            self.assertEqual(stamp["files"][name], setup.digest(self.runtime / name))

    def test_geometry_only_runtime_cannot_be_stamped(self):
        self.git("checkout", "--", "cursor.ts")
        with self.assertRaises(subprocess.CalledProcessError):
            setup.stamp(self.runtime, self.app)
        self.assertFalse((self.runtime / "video-use-runtime.json").exists())

    def test_changed_cursor_patch_cannot_be_stamped(self):
        (self.runtime / "cursor.ts").write_text("unexpected\n")
        with self.assertRaises(subprocess.CalledProcessError):
            setup.stamp(self.runtime, self.app)
        self.assertFalse((self.runtime / "video-use-runtime.json").exists())

    def test_missing_wallpaper_patch_cannot_be_stamped(self):
        self.git("checkout", "--", "wallpaper.ts")
        with self.assertRaises(subprocess.CalledProcessError):
            setup.stamp(self.runtime, self.app)
        self.assertFalse((self.runtime / "video-use-runtime.json").exists())


if __name__ == "__main__":
    unittest.main()
