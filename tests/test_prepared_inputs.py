import hashlib
from copy import deepcopy

import pytest

from experiments.prepared_inputs import stage_inputs, validate_inputs


def fixture(tmp_path):
    volume = tmp_path / "volume"
    source = volume / "prepared-assets/campaign/interview/clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"reviewed source bytes")
    project = tmp_path / "project"
    project.mkdir()
    item = {"source": str(source.relative_to(volume)), "target": "edit/downloads/interview.mp4",
            "bytes": source.stat().st_size, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    return volume, source, project, item


def test_copies_independent_bytes(tmp_path):
    volume, source, project, item = fixture(tmp_path)
    assert stage_inputs([item], project, volume) == [item]
    target = project / item["target"]
    assert target.read_bytes() == source.read_bytes()
    target.write_bytes(b"worker change")
    assert source.read_bytes() == b"reviewed source bytes"


@pytest.mark.parametrize("field,value", [("source", "campaign/other.mp4"), ("source", "prepared-assets/../private/auth.json"),
    ("source", "/prepared-assets/video.mp4"), ("source", "prepared-assets/.env.txt"),
    ("target", "edit/final.mp4"), ("target", "edit/downloads/../final.mp4"),
    ("target", "edit/downloads/.secret.json"), ("target", "edit/downloads/code.py"),
    ("sha256", "unknown"), ("bytes", True), ("bytes", 0)])
def test_invalid_specs_rejected_before_copy(tmp_path, field, value):
    volume, source, project, item = fixture(tmp_path)
    item[field] = value
    with pytest.raises(ValueError):
        stage_inputs([item], project, volume)
    assert list(project.iterdir()) == []


def test_changed_source_and_existing_target_preserved(tmp_path):
    volume, source, project, item = fixture(tmp_path)
    source.write_bytes(b"changed source bytes!")
    with pytest.raises(ValueError, match="approved input"):
        stage_inputs([item], project, volume)
    source.write_bytes(b"reviewed source bytes")
    target = project / item["target"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"prior work")
    with pytest.raises(ValueError, match="overwrite"):
        stage_inputs([item], project, volume)
    assert target.read_bytes() == b"prior work"


def test_source_and_destination_links_rejected(tmp_path):
    volume, source, project, item = fixture(tmp_path)
    other = source.with_name("other.mp4")
    source.rename(other)
    source.symlink_to(other)
    with pytest.raises(ValueError, match="symlink"):
        stage_inputs([item], project, volume)
    source.unlink()
    other.rename(source)
    (project / "edit").symlink_to(volume)
    with pytest.raises(ValueError, match="symlink"):
        stage_inputs([item], project, volume)


def test_duplicate_targets_and_total_budget_rejected(tmp_path):
    _, _, _, item = fixture(tmp_path)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_inputs([item, deepcopy(item)])
    many = [{**item, "target": f"edit/downloads/{n}.mp4", "bytes": 4 * 1024**3} for n in range(3)]
    with pytest.raises(ValueError, match="per-job"):
        validate_inputs(many)
