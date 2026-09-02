from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


pytest.importorskip("manim")


def test_each_domain_family_renders_a_low_quality_gallery(tmp_path: Path) -> None:
    manim = shutil.which("manim")
    if manim is None:
        pytest.skip("Manim executable is not installed")
    script = Path(__file__).parent / "fixtures" / "manim_domain_gallery.py"
    scenes = [
        "MathGallery",
        "ComputingGallery",
        "SystemsGallery",
        "PhysicsGallery",
        "BiologyGallery",
        "FinanceGallery",
        "TeachingAPIGallery",
        "TeachingThreeDGallery",
    ]
    result = subprocess.run(
        [manim, "render", "-ql", "--media_dir", str(tmp_path), str(script), *scenes],
        capture_output=True,
        text=True,
        timeout=240,
    )

    assert result.returncode == 0, result.stderr
    for scene in scenes:
        assert any(
            "partial_movie_files" not in path.parts
            for path in tmp_path.rglob(f"{scene}.mp4")
        )
