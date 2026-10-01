from pathlib import Path
from unittest.mock import patch

from helpers.render_manim_cached import render


def test_unchanged_scenes_reused_but_source_and_dependencies_invalidate(tmp_path):
    source = tmp_path / "film.py"
    source.write_text("original source")
    dependency = tmp_path / "data.json"
    dependency.write_text("{}")

    def manim(args, **kwargs):
        assert (
            "--disable_caching" in args
        )  # imported helpers may attach stateful updaters
        root = Path(args[args.index("--media_dir") + 1])
        start = args.index(str(source))
        for scene in args[start + 1 :]:
            dest = root / "videos/film/540p15" / (scene + ".mp4")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"video")

    with patch("helpers.render_manim_cached.subprocess.run", side_effect=manim) as run:
        first = render(source, ["Intro", "Explain"], dependencies=[dependency])
        # Audio mixing changes do not invalidate animation files.
        (tmp_path / "mix.wav").write_bytes(b"new mix")
        second = render(source, ["Intro", "Explain"], dependencies=[dependency])
        assert second["videos"] == first["videos"] and not second["rendered"]
        assert run.call_count == 1
        source.write_text("changed source")
        assert render(source, ["Intro"], dependencies=[dependency])["rendered"] == [
            "Intro"
        ]
        dependency.write_text('{"changed":true}')
        assert render(source, ["Intro"], dependencies=[dependency])["rendered"] == [
            "Intro"
        ]
        assert run.call_count == 3


def test_source_edits_keep_manim_animation_cache_but_snapshot_outputs_are_immutable(
    tmp_path,
):
    source = tmp_path / "film.py"
    source.write_text("first source")
    dependency = tmp_path / "data.json"
    dependency.write_text("{}")
    roots = []

    def manim(args, **kwargs):
        assert (
            "--disable_caching" in args
        )  # imported helpers may attach stateful updaters
        root = Path(args[args.index("--media_dir") + 1])
        roots.append(root)
        for scene in args[args.index(str(source)) + 1 :]:
            dest = root / "videos/film/540p15" / (scene + ".mp4")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes() + dependency.read_bytes())

    with patch("helpers.render_manim_cached.subprocess.run", side_effect=manim):
        first = render(source, ["Intro", "Explain"], dependencies=[dependency])
        source.write_text("changed explanation")
        second = render(source, ["Intro", "Explain"], dependencies=[dependency])
        assert roots[0] == roots[1]  # whole-scene index survives source edits
        assert first["videos"] != second["videos"]
        assert Path(first["videos"][0]).read_bytes() == b"first source{}"
        assert Path(second["videos"][0]).read_bytes() == b"changed explanation{}"
        dependency.write_text('{"value": 2}')
        render(source, ["Intro"], dependencies=[dependency])
        assert roots[2] != roots[1]  # external data invalidates the internal cache too
        (tmp_path / "helpers.py").write_text("changed helper")
        render(source, ["Intro"], dependencies=[dependency])
        assert roots[3] != roots[2]


def test_source_changed_during_render_cannot_be_cached_as_previous_version(tmp_path):
    import pytest

    source = tmp_path / "film.py"
    source.write_text("first source")

    def manim(*args, **kwargs):
        source.write_text("concurrently edited source")

    with patch("helpers.render_manim_cached.subprocess.run", side_effect=manim):
        with pytest.raises(RuntimeError, match="changed during rendering"):
            render(source, ["Intro"])
    assert not list((tmp_path / "media/video-use-cache").glob("*/manifest.json"))


def test_parallel_scene_commands_preserve_shared_manifest_and_completed_outputs(
    tmp_path,
):
    import concurrent.futures
    import json
    import threading
    import time

    source = tmp_path / "film.py"
    source.write_text("source")
    active = 0
    peak = 0
    count_lock = threading.Lock()

    def manim(args, **kwargs):
        nonlocal active, peak
        with count_lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        root = Path(args[args.index("--media_dir") + 1])
        for scene in args[args.index(str(source)) + 1 :]:
            dest = root / "videos/film/540p15" / (scene + ".mp4")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(scene.encode())
        with count_lock:
            active -= 1

    with patch("helpers.render_manim_cached.subprocess.run", side_effect=manim):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(
                    lambda scene: render(source, [scene]),
                    ["SceneA", "SceneB", "SceneC"],
                )
            )
        all_scenes = render(source, ["SceneA", "SceneB", "SceneC"])
    assert peak == 1
    assert all_scenes["reused"] == ["SceneA", "SceneB", "SceneC"]
    assert [Path(r["videos"][0]).read_text() for r in results] == [
        "SceneA",
        "SceneB",
        "SceneC",
    ]
    manifests = list((tmp_path / "media/video-use-cache").glob("*/manifest.json"))
    manifest = json.loads(manifests[0].read_text())
    assert set(manifest) == {"SceneA", "SceneB", "SceneC"}


def test_scene_fingerprint_preserves_transitive_bases_helpers_and_scene_dependencies(
    tmp_path,
):
    from helpers.render_manim_cached import _scene_source

    source = tmp_path / "film.py"
    original = """from manim import *
COLOR = GREEN
class Base(Scene):
 def setup(self):
  self.camera.background_color = COLOR
class SceneA(Base):
 def construct(self):
  self.add(Dot())
class SceneB(Base):
 def construct(self):
  self.add(Square())
"""
    source.write_text(original)
    first = _scene_source(source, "SceneA")
    source.write_text(original.replace("Square()", "Circle()"))
    assert _scene_source(source, "SceneA") == first
    source.write_text(original.replace("COLOR = GREEN", "COLOR = BLUE"))
    assert _scene_source(source, "SceneA") != first
    source.write_text(
        original.replace(
            "self.camera.background_color = COLOR", "self.camera.background_color = RED"
        )
    )
    assert _scene_source(source, "SceneA") != first
    dependent = original.replace("self.add(Dot())", "SceneB().construct()")
    source.write_text(dependent)
    dependency = _scene_source(source, "SceneA")
    source.write_text(dependent.replace("Square()", "Circle()"))
    assert _scene_source(source, "SceneA") != dependency


def test_dynamic_python_and_class_side_effects_fall_back_to_complete_source(tmp_path):
    from helpers.render_manim_cached import _scene_source

    source = tmp_path / "film.py"
    for content in [
        'class SceneA(Scene):\n def construct(self):\n  globals()["SceneB"]()\nclass SceneB(Scene):\n def construct(self):\n  pass\n',
        "class SceneA(Scene):\n side_effect = register()\n def construct(self):\n  pass\n",
        "class SceneA(Scene):\n def construct(self):\n  global VALUE\n  VALUE = 1\n",
        "class SceneA(Scene):\n def construct(self):\n  pass\nregister_scenes()\n",
    ]:
        source.write_text(content)
        assert _scene_source(source, "SceneA") == content


def test_opaque_bases_import_side_effects_and_mutable_globals_use_whole_source(
    tmp_path,
):
    from helpers.render_manim_cached import _scene_source

    source = tmp_path / "film.py"
    for content in [
        "from opaque import CustomScene\nclass SceneA(CustomScene):\n def construct(self):\n  pass\n",
        "from manim import *\nVALUE=register()\nclass SceneA(Scene):\n def construct(self):\n  pass\n",
        "from manim import *\nSTATE=[]\nclass SceneA(Scene):\n def construct(self):\n  STATE.append(1)\n",
        'from manim import *\nSTATE={}\nclass SceneA(Scene):\n def construct(self):\n  STATE["value"] = 1\n',
        "from manim import *\nclass SceneA(Scene):\n def construct(self):\n  print(Scene.__subclasses__())\n",
    ]:
        source.write_text(content)
        assert _scene_source(source, "SceneA") == content


def test_imported_config_writes_and_manim_class_defaults_use_whole_source(tmp_path):
    from helpers.render_manim_cached import _scene_source

    source = tmp_path / "film.py"
    for mutation in [
        "config.background_color = RED",
        "Dot.set_default(color=RED)",
        "cfg = config\n  cfg.background_color = RED",
    ]:
        content = (
            "from manim import *\nclass SceneA(Scene):\n def construct(self):\n  "
            + mutation
            + "\nclass SceneB(Scene):\n def construct(self):\n  self.add(Dot())\n"
        )
        source.write_text(content)
        assert _scene_source(source, "SceneB") == content
