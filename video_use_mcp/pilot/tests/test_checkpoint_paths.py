"""Generated audio and project scripts retain their actual paths after idle restore."""

import shutil
import zipfile

import pytest

from video_use_mcp.pilot.runtime import PACK, RESTORE


def run(script, workspace):
    exec(script.replace("/workspace", str(workspace)), {})


def test_generated_files_outside_edit_round_trip_and_sources_are_not_duplicated(
    tmp_path,
):
    workspace = tmp_path / "original"
    keep = {
        "audio/narration.mp3": b"narration bytes",
        "audio/narration.mp3.json": b'{"words":[]}',
        "edit/scene.py": b"author code",
        "motion.py": b"root author code",
        "edit/project.md": b"brief",
        "fonts/display.ttf": b"font data",
    }
    omitted = {
        "sources/reference.mp3": b"uploaded source hydrates separately",
        "sources/brief.txt": b"uploaded text",
        "edit/final.mp4": b"render cache",
        "final.webm": b"root render cache",
        "edit/verify/sheet.png": b"transient review",
        "node_modules/module/source.js": b"dependency tree",
        ".cache/renderer.bin": b"transient cache",
        "restore.zip": b"old restore archive",
    }
    for relative, data in (keep | omitted).items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    outside = tmp_path / "not-project.txt"
    outside.write_bytes(b"outside data")
    (workspace / "outside-link.txt").symlink_to(outside)
    run(PACK, workspace)
    with zipfile.ZipFile(workspace / "checkpoint.zip") as archive:
        assert set(archive.namelist()) == set(keep)
    restored = tmp_path / "restored"
    restored.mkdir()
    shutil.copyfile(workspace / "checkpoint.zip", restored / "restore.zip")
    run(RESTORE, restored)
    for relative, data in keep.items():
        assert (restored / relative).read_bytes() == data
    assert not (restored / "sources").exists()
    assert not (restored / "outside-link.txt").exists()


def test_old_edit_only_checkpoints_remain_compatible(tmp_path):
    with zipfile.ZipFile(tmp_path / "restore.zip", "w") as archive:
        archive.writestr("edit/audio/narration.mp3", b"old narration")
        archive.writestr("edit/project.md", b"old brief")
    run(RESTORE, tmp_path)
    assert (tmp_path / "edit/audio/narration.mp3").read_bytes() == b"old narration"


@pytest.mark.parametrize(
    "name",
    [
        "../escaped.txt",
        "/tmp/escaped.txt",
        "audio/../../escaped.txt",
        "sources/replace-original.mp3",
        "restore.zip",
        "checkpoint.zip",
        "audio\\..\\escaped.txt",
    ],
)
def test_restore_rejects_escaping_or_reserved_paths_before_extracting(tmp_path, name):
    with zipfile.ZipFile(tmp_path / "restore.zip", "w") as archive:
        archive.writestr("audio/okay.mp3", b"otherwise valid")
        archive.writestr(name, b"invalid")
    with pytest.raises(ValueError, match="Invalid archive path"):
        run(RESTORE, tmp_path)
    assert not (tmp_path / "audio/okay.mp3").exists()


def test_restore_rejects_symlink_entries(tmp_path):
    link = zipfile.ZipInfo("audio/link")
    link.create_system = 3
    link.external_attr = 0o120777 << 16
    with zipfile.ZipFile(tmp_path / "restore.zip", "w") as archive:
        archive.writestr(link, "/outside")
    with pytest.raises(ValueError, match="Invalid archive path"):
        run(RESTORE, tmp_path)
