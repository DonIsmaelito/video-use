"""A real short render verifies motion, opacity, audio trimming and seek stability."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_scene", ROOT / "helpers" / "render_scene.py"
)
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def sample():
    return {
        "duration": 1.2,
        "width": 320,
        "height": 180,
        "fps": 10,
        "background": "#000000",
        "marks": [
            {
                "id": "moving",
                "kind": "rect",
                "x": 10,
                "y": 50,
                "w": 30,
                "h": 30,
                "fill": "#ffffff",
                "stroke_width": 0,
                "opacity": 0.5,
                "keyframes": [{"time": 0, "ease": "linear"}, {"time": 1, "x": 160}],
            },
            {
                "id": "title",
                "kind": "text",
                "text": "A moving, editable scene",
                "x": 20,
                "y": 12,
                "w": 280,
                "h": 28,
                "size": 70,
                "font": "bold",
            },
        ],
    }


class SceneValidationTests(unittest.TestCase):
    def test_validate_cli_reports_every_bad_keyframe_without_render_or_writes(self):
        scene = sample()
        scene["duration"] = 3.8
        scene["marks"] = [
            {
                "id": name,
                "kind": "ellipse",
                "keyframes": [{"time": -0.1}, {"time": 0.5, "opacity": 1}],
            }
            for name in ("hhalo", "hwl0", "hwl1")
        ]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "scene.json"
            original = json.dumps(scene)
            source.write_text(original)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "helpers/render_scene.py"),
                    str(source),
                    "--validate",
                ],
                env={**os.environ, "PATH": ""},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertFalse(report["valid"])
            self.assertEqual(len(report["errors"]), 3)
            for name, error in zip(("hhalo", "hwl0", "hwl1"), report["errors"]):
                self.assertIn(f"id='{name}'", error)
                self.assertIn("time=-0.1", error)
                self.assertIn("scene duration 3.8s", error)
            self.assertEqual(source.read_text(), original)
            self.assertEqual(list(Path(tmp).iterdir()), [source])
            source.write_text('{"marks": [')
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "helpers/render_scene.py"),
                    str(source),
                    "--validate",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["valid"])
            self.assertIn("line 1", json.loads(result.stdout)["errors"][0])

    def test_motion_path_validates_geometry_work_bounds_and_parent_instances(self):
        scene = sample()
        scene["marks"][0]["motion_path"] = {
            "points": [[0, 0], [100, 0], [100, 50]],
            "seconds": 3,
            "count": 3,
            "loop": True,
            "closed": True,
        }
        original = copy.deepcopy(scene)
        normalized = renderer.validate_scene(scene)
        self.assertEqual(normalized["marks"][0]["motion_path"]["stagger"], 1)
        self.assertEqual(renderer.validate_scene(normalized), normalized)
        self.assertEqual(scene, original)
        invalids = [
            {"points": [[0, 0], [0, 0]]},
            {"seconds": 0},
            {"count": 33},
            {"count": 1.5},
            {"stagger": -1},
            {"loop": "true"},
            {"start": 2},
            {"url": "https://example.com"},
        ]
        for invalid in invalids:
            candidate = copy.deepcopy(scene)
            candidate["marks"][0]["motion_path"].update(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                renderer.validate_scene(candidate)
        scene["marks"][1]["parent"] = "moving"
        with self.assertRaisesRegex(ValueError, "repeated path instances"):
            renderer.validate_scene(scene)
        scene["marks"] = [
            dict(
                original["marks"][0],
                id=f"particle{i}",
                motion_path={
                    "points": [[0, 0], [10, 10]],
                    "seconds": 1,
                    "count": 32,
                },
            )
            for i in range(13)
        ]
        with self.assertRaisesRegex(ValueError, "400 expanded"):
            renderer.validate_scene(scene)

    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_path_speed_loop_spacing_wave_phase_and_backward_sampling(self):
        scene = sample()
        scene["duration"] = 6
        scene["marks"] = [
            {
                "id": "flow",
                "kind": "ellipse",
                "x": 10,
                "y": 20,
                "motion_path": {"points": [[0, 0], [80, 0], [80, 20]], "seconds": 5},
            },
            {
                "id": "loop",
                "kind": "ellipse",
                "motion_path": {
                    "points": [[0, 0], [100, 0], [100, 50], [0, 50]],
                    "seconds": 3,
                    "loop": True,
                    "closed": True,
                    "count": 3,
                },
            },
            {
                "id": "wave",
                "kind": "wave",
                "phase": 0,
                "keyframes": [
                    {"time": 0, "ease": "linear"},
                    {"time": 1, "phase": -360},
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            renderer.prepare_scene(scene, Path(tmp))
            script = """import fs from 'node:fs';
import {compileScene} from './scene_runtime.mjs';
const scene=JSON.parse(fs.readFileSync('./scene.json','utf8')), before=JSON.stringify(scene);
const sample=compileScene(scene);
const at0=sample(0), at1=sample(1), at45=sample(4.5), atQuarter=sample(.25), reversed=sample(0);
console.log(JSON.stringify({at0,at1,at45,atQuarter,reversed,unchanged:JSON.stringify(scene)===before}));"""
            proc = subprocess.run(
                ["node", "--input-type=module", "-e", script],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(proc.stdout)
            self.assertTrue(result["unchanged"])
            self.assertEqual(result["at0"], result["reversed"])
            self.assertEqual(result["at1"][0]["matrix"][4:], [30, 20])
            self.assertEqual(result["at45"][0]["matrix"][4:], [90, 30])
            positions = [row["matrix"][4:] for row in result["at0"][1:4]]
            self.assertEqual(positions[0], [0, 0])
            self.assertAlmostEqual(positions[1][0], 50)
            self.assertAlmostEqual(positions[1][1], 50)
            self.assertAlmostEqual(positions[2][0], 100)
            self.assertAlmostEqual(positions[2][1], 0)
            self.assertEqual(result["atQuarter"][-1]["pose"]["phase"], -90)

    def test_keyframe_bounds_error_identifies_mark_index_time_and_duration(self):
        scene = sample()
        scene["duration"] = 3.8
        scene["marks"][0]["id"] = "hhalo"
        for invalid in (-0.1, 4.2, float("inf")):
            scene["marks"][0]["keyframes"] = [{"time": invalid, "opacity": 1}]
            with self.subTest(time=invalid), self.assertRaises(ValueError) as error:
                renderer.validate_scene(scene)
            message = str(error.exception)
            self.assertIn(
                "marks[0] (id='hhalo').keyframes[0].time=" + repr(invalid), message
            )
            self.assertIn("scene duration 3.8s", message)
        scene["marks"][0]["keyframes"] = [{"time": 0.5}, {"time": 0.2}]
        with self.assertRaises(ValueError) as error:
            renderer.validate_scene(scene)
        self.assertIn("(id='hhalo').keyframes[1].time=0.2", str(error.exception))
        self.assertIn("previous keyframe time 0.5s", str(error.exception))
        self.assertIn("scene duration 3.8s", str(error.exception))

    def test_normalized_source_is_stable_across_python_hash_seeds(self):
        scene = sample()
        scene["marks"][0]["keyframes"] = [
            {"time": 0.5, "x": 70, "y": 20, "rotation": 40, "scale": 0.8}
        ]
        script = (
            "import json,sys; from helpers.render_scene import validate_scene; "
            "print(json.dumps(validate_scene(json.load(sys.stdin))))"
        )
        results = [
            subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env={**os.environ, "PYTHONHASHSEED": seed},
                input=json.dumps(scene),
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            for seed in ("1", "42")
        ]
        self.assertEqual(*results)

    def test_normalizes_frame_duration_without_mutating_input(self):
        scene = sample()
        original = copy.deepcopy(scene)
        scene["duration"] = 1.21
        normalized = renderer.validate_scene(scene)
        self.assertEqual(normalized["duration"], 1.3)
        self.assertEqual(normalized["marks"][0]["scale"], 1)
        self.assertEqual(scene["marks"], original["marks"])
        self.assertEqual(renderer.validate_scene(normalized), normalized)

    def test_rejects_code_external_assets_unbounded_and_invalid_motion(self):
        variants = []
        for key, value in (
            ("duration", 21),
            ("width", 321),
            ("fps", 60),
            ("background", "url(https://example.com)"),
        ):
            scene = sample()
            scene[key] = value
            variants.append(scene)
        for key, value in (
            ("x", float("nan")),
            ("opacity", 2),
            ("url", "https://example.com"),
            ("keyframes", [{"time": 0.5}, {"time": 0.2}]),
            ("keyframes", [{"time": 0.2, "ease": "eval('bad')"}]),
        ):
            scene = sample()
            scene["marks"][0][key] = value
            variants.append(scene)
        scene = sample()
        scene["marks"][1]["id"] = "moving"
        variants.append(scene)
        scene = sample()
        scene["marks"][0]["parent"] = "title"
        scene["marks"][1]["parent"] = "moving"
        variants.append(scene)
        scene = sample()
        scene["marks"][0]["parent"] = "missing"
        variants.append(scene)
        for scene in variants:
            with self.subTest(scene=scene), self.assertRaises(ValueError):
                renderer.validate_scene(scene)

    def test_user_text_remains_data_and_runtime_has_no_remote_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = sample()
            text = '</script><script>fetch("https://example.com")</script>'
            scene["marks"][1]["text"] = text
            renderer.prepare_scene(scene, Path(tmp))
            self.assertNotIn(text, (Path(tmp) / "index.html").read_text())
            self.assertEqual(
                json.loads((Path(tmp) / "scene.json").read_text())["marks"][1]["text"],
                text,
            )

    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_absolute_time_keyframes_hold_values_and_parent_transforms(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = sample()
            scene["marks"].append(
                {"id": "child", "kind": "ellipse", "parent": "moving", "x": 5, "y": 7}
            )
            renderer.prepare_scene(scene, Path(tmp))
            script = """import fs from 'node:fs';
import {compileScene} from './scene_runtime.mjs';
const sample=compileScene(JSON.parse(fs.readFileSync('./scene.json','utf8')));
const a=sample(.5), b=sample(1), c=sample(.5);
console.log(JSON.stringify({a,b,c}));"""
            proc = subprocess.run(
                ["node", "--input-type=module", "-e", script],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(proc.stdout)
            self.assertEqual(result["a"], result["c"])
            self.assertEqual(result["a"][0]["pose"]["x"], 85)
            self.assertEqual(result["b"][0]["pose"]["x"], 160)
            self.assertEqual(result["a"][2]["matrix"][4:], [90, 57])
            self.assertEqual(result["a"][2]["opacity"], 0.5)


@unittest.skipUnless(
    CHROME.exists()
    and shutil.which("node")
    and shutil.which("ffmpeg")
    and (renderer.RUNTIME / "node_modules" / "puppeteer-core").exists(),
    "Local browser renderer required",
)
class SceneRenderTests(unittest.TestCase):
    def test_scaled_render_preserves_authored_coordinates_and_animates_path_wave(self):
        scene = {
            "duration": 1,
            "width": 320,
            "height": 180,
            "fps": 10,
            "background": "#000000",
            "marks": [
                {
                    "id": "electron",
                    "kind": "ellipse",
                    "x": -5,
                    "y": -5,
                    "w": 10,
                    "h": 10,
                    "fill": "#ff0000",
                    "stroke_width": 0,
                    "motion_path": {"points": [[40, 60], [120, 60]], "seconds": 1},
                },
                {
                    "id": "wave",
                    "kind": "wave",
                    "x": 10,
                    "y": 130,
                    "w": 100,
                    "h": 20,
                    "color": "#00ff00",
                    "stroke_width": 3,
                    "cycles": 1,
                    "keyframes": [
                        {"time": 0, "ease": "linear"},
                        {"time": 1, "phase": 360},
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory(prefix="video-use-path-") as tmp:
            path = Path(tmp)
            original = copy.deepcopy(scene)
            report = renderer.render_scene(
                scene,
                path / "motion.mp4",
                output_width=640,
                output_height=360,
                output_fps=12,
            )
            self.assertEqual(scene, original)
            self.assertEqual(
                (report["width"], report["height"], report["frame_count"]),
                (640, 360, 12),
            )
            source = json.loads(Path(report["source"]).read_text())
            self.assertEqual(
                (source["width"], source["height"], source["fps"]), (320, 180, 10)
            )
            manifest = json.loads(Path(report["manifest"]).read_text())
            self.assertTrue(
                all(
                    item["backwardSeekMatches"]
                    for item in manifest["deterministicChecks"]
                )
            )
            for time, electron_x, wave_y in ((0, 80, 260), (0.25, 120, 280)):
                image_path = path / f"frame{time}.png"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-ss",
                        str(time),
                        "-i",
                        report["output"],
                        "-frames:v",
                        "1",
                        str(image_path),
                    ],
                    check=True,
                )
                with Image.open(image_path).convert("RGB") as image:
                    self.assertGreater(image.getpixel((electron_x, 120))[0], 220)
                    self.assertGreater(image.getpixel((22, wave_y))[1], 180)
                    self.assertLess(
                        image.getpixel((40, 60))[0], 20
                    )  # author coords were scaled

    def test_encoded_motion_opacity_audio_and_backward_seeks(self):
        with tempfile.TemporaryDirectory(prefix="video-use-scene-") as tmp:
            path = Path(tmp)
            # The second half has sound; --audio-start must trim away first-half silence.
            audio = path / "audio.wav"
            rate = 16000
            with wave.open(str(audio), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(rate)
                values = [
                    0
                    if n < rate
                    else int(math.sin(2 * math.pi * 440 * n / rate) * 12000)
                    for n in range(rate * 3)
                ]
                out.writeframes(struct.pack(f"<{len(values)}h", *values))
            scene = sample()
            scene["marks"].append(
                {
                    "id": "crowded",
                    "kind": "text",
                    "x": 20,
                    "y": 130,
                    "w": 30,
                    "h": 20,
                    "text": "An intentionally long label",
                    "size": 40,
                }
            )
            report = renderer.render_scene(
                scene, path / "motion.mp4", audio=audio, audio_start=1, chrome=CHROME
            )
            manifest = json.loads(Path(report["manifest"]).read_text())
            self.assertEqual(manifest["frameCount"], 12)
            self.assertTrue(
                all(
                    check["backwardSeekMatches"]
                    for check in manifest["deterministicChecks"]
                )
            )
            self.assertFalse(manifest["remoteAssetsAllowed"])
            self.assertTrue(
                any("crowded fits at only" in warning for warning in report["warnings"])
            )
            for time, expected_x in ((0, 20), (0.9, 155)):
                frame = path / f"frame-{time}.png"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-ss",
                        str(time),
                        "-i",
                        report["output"],
                        "-frames:v",
                        "1",
                        str(frame),
                    ],
                    check=True,
                )
                with Image.open(frame).convert("RGB") as image:
                    self.assertTrue(110 < image.getpixel((expected_x, 60))[0] < 145)
                    self.assertLess(image.getpixel((250, 60))[0], 10)
                    self.assertLess(
                        max(
                            value[1]
                            for value in image.crop((302, 0, 320, 48)).getextrema()
                        ),
                        15,
                    )
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    report["output"],
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    str(rate),
                    "-f",
                    "s16le",
                    "-",
                ],
                capture_output=True,
                check=True,
            )
            samples = struct.unpack(f"<{len(proc.stdout)//2}h", proc.stdout)
            self.assertGreater(
                sum(abs(value) for value in samples[: rate // 2]) / (rate // 2), 5000
            )
            self.assertAlmostEqual(len(samples) / rate, 1.2, delta=0.05)
            with self.assertRaisesRegex(ValueError, "Output exists"):
                renderer.render_scene(sample(), path / "motion.mp4")


if __name__ == "__main__":
    unittest.main()
