"""Review binding and archive boundaries for public gallery publication."""
import io
import base64
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.publish_useful_video import check_archive, contains_secret, validate_approval
from experiments.useful_video_library import archive_source


def approval():
    return {"batch": "batch-01", "id": "useful-01", "attempt": "original", "sha256": "a" * 64, "sourceSha256": "b" * 64,
            "approved": True, "sourceReviewed": True, "posterTime": 4.5,
            "review": "Inspected the encoded opening, transition sequence, settled interface and ending. Text stays readable and nothing clips. Audio was measured only."}


@pytest.mark.parametrize("key,value", [("batch", "../other"), ("sha256", "a" * 63), ("sourceSha256", ""), ("approved", False),
                                      ("sourceReviewed", False), ("posterTime", float("nan")), ("posterTime", True)])
def test_approval_requires_exact_reviewed_output(key, value):
    record = deepcopy(approval())
    record[key] = value
    with pytest.raises(ValueError):
        validate_approval(record)


@pytest.mark.parametrize("name,data", [("edit/.codex/auth.json", "private"), ("../outside.txt", "private"),
                                     ("edit/input.mp4", "raw source"), ("edit/trace.jsonl", "trace"),
                                     ("edit/source.avi", "raw source"), ("edit/assets.zip", "nested archive"),
                                     ("edit\\..\\outside.txt", "portable traversal"), ("C:/outside.txt", "drive path"),
                                     ("edit/config.json", '"key":"sk-' + 'x' * 24 + '"'),
                                     ("edit/notes.txt", 'copied {"refresh_token":"secret-value"}')])
def test_private_and_raw_media_are_rejected(tmp_path, name, data):
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, data)
    with pytest.raises(ValueError):
        check_archive(path)


def test_editable_source_is_accepted(tmp_path):
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("edit/scene.html", "<html>original authored scene</html>")
        archive.writestr("edit/README.md", "Reproduction commands and source licenses")
        archive.writestr("edit/references/upstream-LICENSE", "MIT license notice")
    result = check_archive(path)
    assert result["files"] == 3
    assert len(result["sha256"]) == 64
    assert validate_approval(approval())["id"] == "useful-01"


def test_stream_scan_covers_large_files_and_chunk_boundaries():
    data = b" " * (11 * 1024 * 1024 - 5) + b"sk-proj-" + b"x" * 32
    assert contains_secret(io.BytesIO(data))


@pytest.mark.parametrize("secret", [
    b"AKIAIOSFODNN7EXAMPLE",
    b"sk-proj-" + b"x" * 24,
    b"sk-ant-api" + b"y" * 24,
    b"sk-" + b"z" * 24,
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b'{"access_token": "example-access-value"}',
    b'{"refresh_token": "example-refresh-value"}',
])
@pytest.mark.parametrize("cross_chunk", [False, True])
def test_supported_secrets_rejected_in_archives_and_across_chunks(tmp_path, secret, cross_chunk):
    prefix = b" " * (1024 * 1024 - 5) if cross_chunk else b'key="'
    content = prefix + secret + b'"'
    assert contains_secret(io.BytesIO(content))
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("edit/notes.txt", content)
    with pytest.raises(ValueError, match="Possible credential"):
        check_archive(archive)


@pytest.mark.parametrize("candidate", [
    b"AKIAabcDEFghiJKLmnoP",
    b"AKIA123456789012345",  # Too short.
    b"AKIA12345678901234567",  # Too long.
    b"xAKIAIOSFODNN7EXAMPLE",
    b"AKIAIOSFODNN7EXAMPLEx",
    b"_AKIAIOSFODNN7EXAMPLE",
    b"AKIAIOSFODNN7EXAMPLE_",
])
def test_aws_detector_requires_complete_exact_format(candidate):
    assert not contains_secret(io.BytesIO(candidate))


def test_aws_end_boundary_is_not_invented_at_a_chunk_edge():
    key = b"AKIAIOSFODNN7EXAMPLE"
    prefix = b" " * (1024 * 1024 - len(key))
    assert not contains_secret(io.BytesIO(prefix + key + b"x"))
    assert contains_secret(io.BytesIO(prefix + key + b'"'))
    assert contains_secret(io.BytesIO(prefix + key))


def test_embedded_inter_font_does_not_resemble_an_aws_key(tmp_path):
    font = Path(__file__).resolve().parents[1] / "website/public/fonts/inter-regular.ttf"
    encoded = base64.b64encode(font.read_bytes())
    assert b"AKIA" in encoded  # Actual ROUTE poster embeds these same font bytes.
    svg = b'<svg><style>@font-face{src:url(data:font/ttf;base64,' + encoded + b')}</style></svg>'
    assert not contains_secret(io.BytesIO(svg))
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("edit/assets/poster.svg", svg)
    assert check_archive(archive)["files"] == 1


def test_real_dependency_locks_survive_archive_and_publisher_with_exact_bytes(tmp_path):
    project = tmp_path / "project"
    edit = project / "edit"
    edit.mkdir(parents=True)
    locks = {"requirements.lock": b"numpy==2.5.3\nPillow==12.3.0\n",
             "uv.lock": b'version = 1\n', "poetry.lock": b'[[package]]\nname = "numpy"\n',
             "Pipfile.lock": b'{"default": {}}\n', "yarn.lock": b'# yarn lockfile v1\n'}
    for name, content in locks.items():
        (edit / name).write_bytes(content)
    for name in ("runtime.lock", "render.lock", "backup.requirements.lock"):
        (edit / name).write_bytes(b"arbitrary process/cache state")
    (edit / "node_modules").mkdir()
    (edit / "node_modules/requirements.lock").write_text("must remain excluded")
    archive = tmp_path / "source.zip"
    archive_source(project, archive)
    with zipfile.ZipFile(archive) as package:
        assert set(package.namelist()) == {"edit/" + name for name in locks}
        for name, content in locks.items():
            assert package.read("edit/" + name) == content
    assert check_archive(archive)["files"] == len(locks)


@pytest.mark.parametrize("name,content", [
    ("edit/runtime.lock", "arbitrary cache"), ("edit/requirements.lock.bak", "backup"),
    ("edit/unknown.lock", "private process state"),
    ("edit/requirements.lock", 'token="sk-' + 'x' * 24 + '"'),
])
def test_unknown_locks_and_credentials_in_recognized_locks_are_rejected(tmp_path, name, content):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(name, content)
    with pytest.raises(ValueError):
        check_archive(archive)
