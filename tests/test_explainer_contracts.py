import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]


def load_helper(name: str):
    path = ROOT / "helpers" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"video_use_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = load_helper("render")
web_source = load_helper("web_source")


class OverlayContractTests(unittest.TestCase):
    def test_split_composition_rejects_protected_illustration_collision(self):
        overlay = {
            "id": "web_beat",
            "file": "clip.mp4",
            "start_in_output": 10,
            "duration": 5,
            "composition": "split_left",
        }
        protected = [{
            "owner": "matrix",
            "start_in_output": 8,
            "duration": 10,
            "rect": {"x": 0.03, "y": 0.15, "width": 0.5, "height": 0.6},
        }]
        with self.assertRaisesRegex(ValueError, "protected illustration"):
            render.validate_overlay_contracts([overlay], protected, False)

    def test_cutaway_may_cover_a_protected_base_illustration(self):
        overlay = {
            "id": "cutaway",
            "file": "clip.mp4",
            "start_in_output": 10,
            "duration": 5,
            "composition": "cutaway",
        }
        protected = [{
            "owner": "matrix",
            "start_in_output": 8,
            "duration": 10,
            "rect": {"x": 0.03, "y": 0.15, "width": 0.9, "height": 0.6},
        }]
        render.validate_overlay_contracts([overlay], protected, False)

    def test_picture_in_picture_requires_a_pip_layout(self):
        overlay = {
            "file": "clip.mp4",
            "start_in_output": 0,
            "duration": 2,
            "composition": "picture_in_picture",
            "layout": "right",
        }
        with self.assertRaisesRegex(ValueError, "pip_left"):
            render.resolve_overlay_rect(overlay, False)

    def test_web_asset_reuse_must_reference_same_file(self):
        common = {
            "media_kind": "web",
            "source_url": "https://example.com/video",
            "source_start": 12,
            "source_end": 16,
            "asset_id": "asset123",
            "duration": 2,
            "composition": "cutaway",
        }
        overlays = [
            {**common, "id": "beat_1", "file": "first.mp4", "start_in_output": 0},
            {
                **common,
                "id": "beat_2",
                "file": "second.mp4",
                "start_in_output": 4,
                "reuse_of": "beat_1",
            },
        ]
        with self.assertRaisesRegex(ValueError, "same prepared file"):
            render.validate_overlay_contracts(overlays, [], False)


class WebSelectionTests(unittest.TestCase):
    def _source_folder(self, edit_dir: Path) -> Path:
        folder = edit_dir / "downloads" / "youtube-demo"
        folder.mkdir(parents=True)
        web_source.write_json(folder / "metadata.json", {
            "extractor": "youtube",
            "id": "demo",
            "webpage_url": "https://www.youtube.com/watch?v=demo",
            "title": "Demo",
        })
        web_source.write_json(folder / "inspection.json", {
            "schema_version": 1,
            "max_source_windows": 3,
            "windows": [{
                "tag": web_source.range_tag(10, 14),
                "source_start": 10,
                "source_end": 14,
                "proxy": "preview.mp4",
                "filmstrip": "inspection.png",
            }],
        })
        return folder

    def test_generic_talking_head_is_rejected_as_a_keep(self):
        with tempfile.TemporaryDirectory() as temporary:
            edit_dir = Path(temporary)
            folder = self._source_folder(edit_dir)
            with patch.object(web_source, "inspect_metadata", return_value=({}, folder)):
                with self.assertRaisesRegex(ValueError, "generic talking-head"):
                    web_source.select_window(
                        "https://www.youtube.com/watch?v=demo",
                        edit_dir,
                        (10, 14),
                        beat_id="beat_1",
                        decision="keep",
                        purpose="physical-object",
                        shot_type="talking-head",
                        visible_subject="a presenter",
                        visible_action="talks to camera",
                        why_footage="shows a real object",
                        rights_status="needs-review",
                        reuse_of=None,
                    )

    def test_exact_interval_requires_explicit_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            edit_dir = Path(temporary)
            folder = self._source_folder(edit_dir)
            kwargs = dict(
                url="https://www.youtube.com/watch?v=demo",
                edit_dir=edit_dir,
                source_range=(10, 14),
                decision="keep",
                purpose="physical-demo",
                shot_type="demonstration",
                visible_subject="an accelerator",
                visible_action="a hand points to memory modules",
                why_footage="shows the physical board",
                rights_status="cleared",
            )
            with patch.object(web_source, "inspect_metadata", return_value=({}, folder)):
                web_source.select_window(**kwargs, beat_id="beat_1", reuse_of=None)
                with self.assertRaisesRegex(ValueError, "exact source interval"):
                    web_source.select_window(**kwargs, beat_id="beat_2", reuse_of=None)
                web_source.select_window(**kwargs, beat_id="beat_2", reuse_of="beat_1")

            manifest = json.loads(
                (edit_dir / "downloads" / "web_selections.json").read_text()
            )
            self.assertEqual(manifest["selections"][1]["reuse_of"], "beat_1")

    def test_one_source_exception_requires_a_documented_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            edit_dir = Path(temporary)
            path, manifest = web_source.selections_record(edit_dir)
            manifest["selections"] = [
                {
                    "beat_id": f"beat_{index}",
                    "decision": "keep",
                    "source_key": "youtube:one",
                    "asset_id": f"asset_{index}",
                }
                for index in range(4)
            ]
            web_source.write_json(path, manifest)
            report = web_source.selection_summary(edit_dir)
            self.assertTrue(report["warnings"])
            report = web_source.selection_summary(
                edit_dir, "Only the official hardware demonstration shows the object"
            )
            self.assertFalse(report["warnings"])


if __name__ == "__main__":
    unittest.main()
