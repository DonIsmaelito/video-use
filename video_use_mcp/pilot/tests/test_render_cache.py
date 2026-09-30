from pathlib import Path
from unittest.mock import patch

from helpers.render_manim_cached import render


def test_unchanged_scenes_reused_but_source_and_dependencies_invalidate(tmp_path):
    source = tmp_path / "film.py"
    source.write_text("original source")
    dependency = tmp_path / "data.json"
    dependency.write_text("{}")

    def manim(args, **kwargs):
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
