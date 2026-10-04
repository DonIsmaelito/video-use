"""Offline boundaries for the paid showcase runner; no Modal imports or jobs."""

import json
import zipfile
from pathlib import Path

import pytest

from experiments.useful_video_library import (
    archive_source, attempt_root, load_briefs, normalize_brief, snapshot,
    public_framework, technical_instructions, updated_audit_record, verify_snapshot,
)


def brief(**extra):
    return {"id": "demo-one", "prompt": "Create a useful product demonstration", "duration": 12, **extra}


def test_delivery_orientation_and_bad_frames():
    assert normalize_brief(brief(orientation="square"))["width"] == 1080
    assert normalize_brief(brief(orientation="portrait"))["height"] == 1920
    for changes in ({"duration": float("nan")}, {"duration": 1.01}, {"width": 1081}, {"id": "../escape"}, {"fps": 24}):
        with pytest.raises(ValueError):
            normalize_brief(brief(**changes))


def test_explicit_aspect_controls_defaults_and_rejects_conflicting_dimensions():
    value = normalize_brief(brief(orientation="portrait", aspect="4:5"))
    assert (value["width"], value["height"]) == (1080, 1350)
    value = normalize_brief(brief(orientation="portrait", aspect="4:5", width=720))
    assert (value["width"], value["height"]) == (720, 900)
    value = normalize_brief(brief(aspect="4:3", height=720))
    assert (value["width"], value["height"]) == (960, 720)
    for changes in ({"aspect": "4:5", "width": 1080, "height": 1920}, {"aspect": "0:5"},
                    {"aspect": "4/5"}, {"aspect": "1:9999"}, {"aspect": "4:5", "width": True}):
        with pytest.raises(ValueError):
            normalize_brief(brief(**changes))


def test_only_four_distinct_explicit_briefs(tmp_path):
    path = tmp_path / "briefs.json"
    for values in ([], [brief()] * 2, [brief(id=f"demo-{i}") for i in range(5)]):
        path.write_text(json.dumps(values))
        with pytest.raises(ValueError):
            load_briefs(path)
    path.write_text(json.dumps([brief(id=f"demo-{i}") for i in range(4)]))
    assert len(load_briefs(path)) == 4


def test_snapshot_excludes_secrets_caches_and_concurrent_website(tmp_path):
    (tmp_path / "helpers").mkdir()
    (tmp_path / "helpers/tool.py").write_text("print('new tool')\n")
    (tmp_path / "helpers/.env").write_text("NEVER_UPLOAD=private")
    (tmp_path / "helpers/__pycache__").mkdir()
    (tmp_path / "helpers/__pycache__/tool.pyc").write_bytes(b"cache")
    (tmp_path / "website").mkdir()
    (tmp_path / "website/page.tsx").write_text("old UI")
    first = snapshot(tmp_path)
    assert set(first["files"]) == {"helpers/tool.py"}
    (tmp_path / "website/page.tsx").write_text("concurrent new UI")
    assert snapshot(tmp_path)["runtime_sha256"] == first["runtime_sha256"]
    verify_snapshot(first, tmp_path)
    (tmp_path / "helpers/tool.py").write_text("changed tool")
    with pytest.raises(ValueError, match="framework differs"):
        verify_snapshot(first, tmp_path)


def test_repairs_never_target_original_project(tmp_path):
    original = attempt_root("batch-1", "demo-one", root=tmp_path)
    repaired = attempt_root("batch-1", "demo-one", "repair-1", root=tmp_path)
    assert repaired == original / "repairs/repair-1"
    assert repaired != original
    with pytest.raises(ValueError):
        attempt_root("batch-1", "demo-one", "../../escape", root=tmp_path)


def test_only_explicit_brand_files_join_the_runtime_snapshot(tmp_path):
    (tmp_path / "website/public").mkdir(parents=True)
    (tmp_path / "website/public/favicon.svg").write_text("<svg/>")
    (tmp_path / "website/public/unrelated.png").write_bytes(b"not a runtime asset")
    expected = snapshot(tmp_path)
    assert set(expected["files"]) == {"brand/favicon.svg"}
    assert expected["repository_paths"] == {"brand/favicon.svg": "website/public/favicon.svg"}
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand/favicon.svg").write_text("<svg/>")
    verify_snapshot(expected, tmp_path)


def test_public_brand_aliases_resolve_to_real_repository_files(tmp_path):
    public = tmp_path / "website/public"
    for relative, content in (("fonts/inter-regular.ttf", b"font"),
                              ("clients/cursor.svg", b"<svg/>"), ("favicon.svg", b"mark")):
        path = public / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    record = snapshot(tmp_path)
    record["repository_paths"].update({"brand/private": "../private", "brand/unused.ttf": "website/public/fonts/unused.ttf"})
    metadata = public_framework(record)
    assert metadata["repository_paths"] == {
        "brand/inter-regular.ttf": "website/public/fonts/inter-regular.ttf",
        "brand/cursor.svg": "website/public/clients/cursor.svg",
        "brand/favicon.svg": "website/public/favicon.svg",
    }
    import hashlib
    for alias, path in metadata["repository_paths"].items():
        assert hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() == metadata["files"][alias]
    assert "repository_paths maps runtime brand/* aliases" in technical_instructions(normalize_brief(brief()))


def test_source_archive_retains_helpers_not_traces_outputs_or_symlinks(tmp_path):
    project = tmp_path / "project"
    (project / "edit/tool-proposals").mkdir(parents=True)
    (project / "edit/tool-proposals/tool.py").write_text("print('reusable')")
    (project / "edit/README.md").write_text("render instructions")
    (project / "edit/render.sh").write_text("#!/bin/sh\npython edit/render.py\n")
    for name in ("LICENSE", "COPYING", "NOTICE", "dependency-LICENSE", "asset_NOTICE", "library_COPYING"):
        (project / "edit" / name).write_text("Required legal notice")
    (project / "edit/final.mp4").write_bytes(b"large-video")
    (project / "edit/original-sound.wav").write_bytes(b"audio")
    (project / "edit/other.zip").write_bytes(b"nested archive")
    (project / "edit/cache.bin").write_bytes(b"arbitrary bytes")
    (project / "edit/codex.jsonl").write_text("private trace")
    (project / "edit/.env").write_text("private")
    (project / "edit/.codex-home").mkdir()
    (project / "edit/.codex-home/auth.json").write_text("private")
    for directory in ("base.render", "draft2-base.render", "draft-verify", "draft2-verify", "draft-media", "final-media", "partial_movie_files",
                      "media/texts", "media-draft/texts", "media-final/Tex", "research", "build", "build-preview"):
        generated = project / "edit" / directory
        generated.mkdir(parents=True)
        (generated / "render.json").write_text("Generated render cache")
        (generated / "frame.svg").write_text("<svg/>")
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    (project / "edit/linked.txt").symlink_to(outside)
    target = tmp_path / "source.zip"
    archive_source(project, target)
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == {"edit/README.md", "edit/render.sh", "edit/tool-proposals/tool.py", "edit/LICENSE", "edit/COPYING", "edit/NOTICE", "edit/dependency-LICENSE", "edit/asset_NOTICE", "edit/library_COPYING"}


def test_declared_regenerated_assets_are_omitted_without_following_external_paths(tmp_path):
    project = tmp_path / "project"
    assets = project / "edit/assets"
    assets.mkdir(parents=True)
    (assets / "derived.png").write_bytes(b"regenerable frame")
    (assets / "authored.png").write_bytes(b"authored reusable asset")
    manifest = project / "edit/source-exclusions.json"
    manifest.write_text(json.dumps({"paths": ["edit/assets/derived.png"]}))
    archive_source(project, tmp_path / "source.zip")
    with zipfile.ZipFile(tmp_path / "source.zip") as archive:
        assert set(archive.namelist()) == {"edit/source-exclusions.json", "edit/assets/authored.png"}
    for path in ("/private", "../outside", "edit/../assets", "."):
        manifest.write_text(json.dumps({"paths": [path]}))
        with pytest.raises(ValueError, match="inside the project"):
            archive_source(project, tmp_path / "source.zip")


def test_prompt_is_preserved_and_proposals_stay_project_local():
    value = normalize_brief(brief(prompt="Exact original creative words"))
    prompt = technical_instructions(value)
    assert prompt.endswith("Exact original creative words\n")
    assert "edit/tool-proposals/" in prompt
    assert "never change it" in prompt
    assert "actual encoded frames with view_image" in prompt


def test_verified_source_assets_reach_the_production_agent_without_substitution():
    asset = {"url": "https://assets.example.org/4029/4029-1080.mp4", "width": 1920,
             "height": 1080, "sha256": "b" * 64, "licenseUrl": "https://example.org/license",
             "credit": "Licensed source credit"}
    value = normalize_brief(brief(sourceAssets=[asset], assetEvidence=[{"sha256": "b" * 64, "width": 1920}],
                                  factualSources=[{"url": "https://example.org/official-captions.vtt"}],
                                  sourceCommit="verified-source-revision", productFacts=["Fictional example product"]))
    prompt = technical_instructions(value)
    evidence = prompt.split("\nORIGINAL CREATIVE PROMPT:")[0]
    assert json.dumps([asset], ensure_ascii=False) in evidence
    assert '"productFacts": ["Fictional example product"]' in evidence
    assert '"assetEvidence": [{"sha256": "' + "b" * 64 + '", "width": 1920}]' in evidence
    assert "https://example.org/official-captions.vtt" in evidence
    assert '"sourceCommit": "verified-source-revision"' in evidence
    assert "Do not silently substitute a lower-resolution preview" in evidence


def test_source_replay_manifest_contains_only_public_producer_identity(tmp_path):
    project = tmp_path / "project"
    (project / "edit").mkdir(parents=True)
    (project / "edit/README.md").write_text("Original project instructions remain unchanged")
    guide = tmp_path / "REPLAY.md"
    guide.write_text("Clone the framework and follow the project README")
    framework = {"commit": "original-commit", "branch": "feature/examples", "runtime_sha256": "a" * 64,
                 "files": {"helpers/tool.py": "b" * 64, ".codex/auth.json": "c" * 64, "../outside": "d" * 64},
                 "credentials": "MUST_NOT_BE_INCLUDED", "trace": "PRIVATE"}
    target = tmp_path / "source.zip"
    archive_source(project, target, framework=framework, replay=guide)
    first = target.read_bytes()
    archive_source(project, target, framework=framework, replay=guide)
    assert target.read_bytes() == first
    with zipfile.ZipFile(target) as archive:
        metadata = json.loads(archive.read("video-use-framework.json"))
        assert set(metadata) == {"commit", "branch", "runtime_sha256", "files", "source_repository"}
        assert metadata["source_repository"] == "https://github.com/DonIsmaelito/video-use"
        assert metadata["commit"] == "original-commit"
        assert metadata["files"] == {"helpers/tool.py": "b" * 64}
        assert archive.read("REPLAY.md") == guide.read_bytes()
        assert archive.read("edit/README.md") == b"Original project instructions remain unchanged"


def test_reaudit_preserves_producer_identity_and_rejects_running_attempt():
    producer = {"status": "needs_repair", "exit_code": 0, "finished_at": 100,
                "framework_commit": "original-commit", "runtime_sha256": "original-runtime"}
    updated = updated_audit_record(producer, {"technical_pass": True}, {"runtime_sha256": "audit-runtime"}, 200)
    assert updated["status"] == "awaiting_review"
    assert updated["framework_commit"] == "original-commit"
    assert updated["runtime_sha256"] == "original-runtime"
    assert updated["exit_code"] == 0
    assert updated["audit_framework_sha256"] == "audit-runtime"
    assert updated["audited_at"] == 200
    assert "audited_at" not in producer
    with pytest.raises(ValueError, match="still running"):
        updated_audit_record({**producer, "status": "running"}, {"technical_pass": True}, {"runtime_sha256": "next"}, 200)
