"""Portable authored projects preserve intent without selecting fixed outputs."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from helpers import motion_project as project


def ready_project(tmp_path):
    prompt = tmp_path / "request.txt"
    prompt.write_text("Make a poem feel impatient using only typography.\n", encoding="utf-8")
    root = tmp_path / "a project"
    manifest = project.init_project(prompt, root)
    data = json.loads(manifest.read_text())
    data["authoringStatus"] = "ready"
    data["entry"] = "scene/index.html"
    (root / "scene").mkdir()
    (root / "scene/index.html").write_text("<!doctype html><script>window.seek = t => document.body.dataset.time = t;</script>")
    (root / "index.html").unlink()
    manifest.write_text(json.dumps(data))
    runtime = root / "runtime"
    runtime.mkdir()
    dependencies = {"puppeteer-core": "25.10.0"}
    (runtime / "package.json").write_text(json.dumps({"dependencies": dependencies}))
    (runtime / "package-lock.json").write_text(json.dumps({"lockfileVersion": 3, "packages": {"": {"dependencies": dependencies}, "node_modules/puppeteer-core": {"version": "25.10.0"}}}))
    return root


def change(root, fn):
    path = root / project.MANIFEST
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def test_init_preserves_exact_prompt_and_cannot_render_a_fake_default(tmp_path):
    source = tmp_path / "prompt.txt"
    text = "  Make something strange.\nKeep this exact sentence.\n"
    source.write_text(text)
    manifest = project.init_project(source, tmp_path / "scene")
    assert (manifest.parent / "prompt.txt").read_text() == text
    project.check_project(manifest, allow_draft=True)
    with pytest.raises(project.ProjectError, match="draft"):
        project.check_project(manifest)
    change(manifest.parent, lambda data: data.update(authoringStatus="ready"))
    with pytest.raises(project.ProjectError, match="scaffold"):
        project.check_project(manifest)
    with pytest.raises(project.ProjectError, match="exists"):
        project.init_project(source, manifest.parent)


@pytest.mark.parametrize("entry", ["../outside.html", "/tmp/outside.html", "scene/../index.html", "C:/file.html", "scene\\index.html"])
def test_paths_reject_traversal_and_machine_specific_names(tmp_path, entry):
    root = ready_project(tmp_path)
    change(root, lambda data: data.update(entry=entry))
    with pytest.raises(project.ProjectError, match="path|Path"):
        project.check_project(root)


def test_symlink_assets_are_rejected_before_packaging(tmp_path):
    root = ready_project(tmp_path)
    (root / "scene/linked.txt").symlink_to(tmp_path / "request.txt")
    with pytest.raises(project.ProjectError, match="Symlinks"):
        project.pack_project(root, tmp_path / "result.zip")
    assert not (tmp_path / "result.zip").exists()


def test_duplicate_keys_and_non_frame_aligned_contract_fail(tmp_path):
    root = ready_project(tmp_path)
    change(root, lambda data: data["render"].update(duration=1.234))
    with pytest.raises(project.ProjectError, match="frame count"):
        project.check_project(root)
    (root / project.MANIFEST).write_text('{"schemaVersion":1,"schemaVersion":1}')
    with pytest.raises(project.ProjectError, match="Duplicate JSON key"):
        project.check_project(root)


def test_render_resolves_nested_inputs_from_foreign_cwd_and_allows_external_output(tmp_path, monkeypatch):
    root = ready_project(tmp_path)
    external = tmp_path / "exports" / "clip.mp4"
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(project.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    project.render_project(root, output=external, deps=tmp_path / "existing deps", qa=True)
    command, options = calls[0]
    assert str(root / "scene/index.html") in command
    assert command[command.index("--root") + 1] == str(root)
    assert command[command.index("-o") + 1] == str(external)
    assert options == {"cwd": root, "check": True}
    assert "--expect-duration" in calls[1][0]


def test_package_relocation_integrity_and_generated_exclusions(tmp_path):
    root = ready_project(tmp_path)
    for relative in ("renders/final.mp4", "renders/final.render/poster.png", "runtime/node_modules/pkg/large.dat", ".cache/scratch"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("do not distribute")
    archive = project.pack_project(root, tmp_path / "portable.zip")
    relocated = tmp_path / "elsewhere"
    with zipfile.ZipFile(archive) as contents:
        names = contents.namelist()
        assert "scene/index.html" in names
        assert "_video_use/motion_render.mjs" in names
        assert "runtime/package-lock.json" in names
        assert not any("node_modules" in name or "final.mp4" in name or "poster.png" in name for name in names)
        contents.extractall(relocated)
    shutil.rmtree(root)
    subprocess.run([sys.executable, str(relocated / "_video_use/motion_project.py"), "check", str(relocated)], cwd=tmp_path, check=True, capture_output=True)
    project.check_project(relocated)
    (relocated / "scene/index.html").write_text("tampered")
    with pytest.raises(project.ProjectError, match="Integrity mismatch"):
        project.check_project(relocated)


def test_integrity_detects_added_inputs(tmp_path):
    root = ready_project(tmp_path)
    archive = project.pack_project(root, tmp_path / "portable.zip")
    relocated = tmp_path / "relocated"
    with zipfile.ZipFile(archive) as contents:
        contents.extractall(relocated)
    (relocated / "new-asset.svg").write_text("<svg/>")
    with pytest.raises(project.ProjectError, match="Unrecorded"):
        project.check_project(relocated)


def test_archive_never_overwrites_and_does_not_leave_partial_results(tmp_path, monkeypatch):
    root = ready_project(tmp_path)
    destination = tmp_path / "portable.zip"
    destination.write_bytes(b"keep this")
    with pytest.raises(project.ProjectError, match="exists"):
        project.pack_project(root, destination)
    assert destination.read_bytes() == b"keep this"
    destination.unlink()
    monkeypatch.setattr(project.zipfile.ZipFile, "writestr", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        project.pack_project(root, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".portable.*.zip"))


def test_unpinned_dependencies_and_oversized_assets_require_a_fix(tmp_path):
    root = ready_project(tmp_path)
    package = root / "runtime/package.json"
    original = package.read_text()
    package.write_text(original.replace("25.10.0", "^25.10.0"))
    with pytest.raises(project.ProjectError, match="exact registry version"):
        project.pack_project(root, tmp_path / "bad.zip")
    package.write_text(original)
    (root / "source-footage.mp4").write_bytes(b"0" * 2048)
    with pytest.raises(project.ProjectError, match="exceeds"):
        project.pack_project(root, tmp_path / "large.zip", max_file_mb=.001)
    assert not (tmp_path / "large.zip").exists()
