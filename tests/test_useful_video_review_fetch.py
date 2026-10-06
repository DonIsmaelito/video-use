"""Offline download boundaries: forbidden artifacts must never reach read_file."""

import json
import sys
from types import SimpleNamespace

import pytest

from experiments import useful_video_library as runner


BASE = "batch/demo"


class FakeVolume:
    def __init__(self, files):
        self.files = files
        self.reads = []
        self.sizes = {}

    def iterdir(self, path, recursive=False):
        prefix = path.strip("/") + "/"
        for name, data in self.files.items():
            if name.startswith(prefix) and (recursive or "/" not in name[len(prefix):]):
                yield SimpleNamespace(path="/" + name, size=self.sizes.get(name, len(data)),
                                      type=SimpleNamespace(name="FILE"))

    def read_file(self, path):
        name = path.lstrip("/")
        self.reads.append(name)
        data = self.files[name]
        # Multiple chunks exercise actual-byte accounting, not just stat checks.
        for offset in range(0, len(data), 7):
            yield data[offset:offset + 7]


def install_volume(monkeypatch, files):
    volume = FakeVolume({BASE + "/" + name: data for name, data in files.items()})
    monkeypatch.setitem(sys.modules, "modal", SimpleNamespace(
        Volume=SimpleNamespace(from_name=lambda name: volume)))
    return volume


def test_review_fetch_exact_allowlist_never_reads_media_archives_or_private_files(tmp_path, monkeypatch):
    allowed = ["run.json", "brief.json", "framework.json", "qa/qa.json", "qa/contact-sheet.jpg",
               "qa/poster.png", "project/edit/README.md", "project/edit/edl.json",
               "project/edit/creative-prompt.txt", "project/edit/video-use-framework.json",
               "project/edit/tool-proposals/score/score.py", "project/edit/tool-proposals/score/README.md",
               "project/edit/tool-proposals/score/tests/test_score.py"]
    forbidden = ["source.zip", "project/edit/final.mp4", "qa/preview.mp4", "project/edit/audio.wav",
                 "agent-final.txt", "agent-events.jsonl", "audit.log", "private.json", "technical-input.txt",
                 "qa/private.json", "qa/arbitrary.png", "project/edit/input.json", "project/edit/scene.html",
                 "project/edit/tool-proposals/score/voice.mp3", "project/edit/tool-proposals/score/archive.zip",
                 "project/edit/tool-proposals/score/texture.png", "project/edit/tool-proposals/score/reasoning.txt",
                 "project/edit/tool-proposals/score/traces/README.md", "project/edit/tool-proposals/.cache/run.py",
                 "project/edit/tool-proposals/score/private/blob.bin", "project/edit/tool-proposals/score/private/run.py",
                 "project/edit/tool-proposals/score/node_modules/lib/index.js", "audit-history/old/run.json"]
    volume = install_volume(monkeypatch, {name: b"content" for name in allowed + forbidden})
    destination = runner.fetch_attempt("batch", "demo", tmp_path, "original", review_only=True)
    assert set(volume.reads) == {BASE + "/" + name for name in allowed}
    assert all((destination / name).read_bytes() == b"content" for name in allowed)
    assert all(not (destination / name).exists() for name in forbidden)
    report = json.loads((destination / "fetch.json").read_text())
    assert report["review_only"] is True
    assert report["downloaded_bytes_including_lookup"] == 7 * len(allowed)


def test_review_fetch_skips_oversized_and_unknown_sizes_before_reading(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {"run.json": b"{}", "qa/poster.png": b"tiny",
                                         "qa/contact-sheet.jpg": b"tiny", "brief.json": b"{}"})
    volume.sizes[BASE + "/qa/poster.png"] = runner.REVIEW_FILE_LIMIT + 1
    volume.sizes[BASE + "/qa/contact-sheet.jpg"] = None
    volume.sizes[BASE + "/brief.json"] = -1
    destination = runner.fetch_attempt("batch", "demo", tmp_path, "original", review_only=True)
    assert volume.reads == [BASE + "/run.json"]
    assert len(json.loads((destination / "fetch.json").read_text())["skipped"]) == 3


def test_review_fetch_total_budget_counts_lookup_and_accepts_exact_boundary(tmp_path, monkeypatch):
    pointer = b'{"attempt":"original"}'
    volume = install_volume(monkeypatch, {"latest.json": pointer, "run.json": b"12345678",
                                         "qa/poster.png": b"12345678", "qa/contact-sheet.jpg": b"x"})
    monkeypatch.setattr(runner, "REVIEW_FILE_LIMIT", len(pointer))
    monkeypatch.setattr(runner, "REVIEW_TOTAL_LIMIT", len(pointer) + 16)
    destination = runner.fetch_attempt("batch", "demo", tmp_path, review_only=True)
    assert volume.reads == [BASE + "/latest.json", BASE + "/run.json", BASE + "/qa/poster.png"]
    report = json.loads((destination / "fetch.json").read_text())
    assert report["downloaded_bytes_including_lookup"] == len(pointer) + 16
    assert report["skipped"][0]["path"] == "qa/contact-sheet.jpg"


@pytest.mark.parametrize("actual,advertised", [(b"too large", 3), (b"short", 8)])
def test_review_fetch_changed_stream_size_never_writes_partial_file(tmp_path, monkeypatch, actual, advertised):
    volume = install_volume(monkeypatch, {"qa/poster.png": actual})
    volume.sizes[BASE + "/qa/poster.png"] = advertised
    with pytest.raises(ValueError, match="size|budget"):
        runner.fetch_attempt("batch", "demo", tmp_path, "original", review_only=True)
    assert not list(tmp_path.rglob("*.png"))


def test_review_fetch_latest_pointer_is_bounded_before_read(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {"latest.json": b'{"attempt":"original"}'})
    volume.sizes[BASE + "/latest.json"] = 64_001
    with pytest.raises(ValueError, match="lookup limit"):
        runner.fetch_attempt("batch", "demo", tmp_path, review_only=True)
    assert volume.reads == []


def test_review_fetch_selects_latest_repair_without_old_history(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {"latest.json": b'{"attempt":"repair-one"}', "run.json": b"old",
                                         "repairs/repair-one/run.json": b"new",
                                         "repairs/repair-one/source.zip": b"archive"})
    destination = runner.fetch_attempt("batch", "demo", tmp_path, review_only=True)
    assert destination.name == "repair-one"
    assert (destination / "run.json").read_bytes() == b"new"
    assert volume.reads == [BASE + "/latest.json", BASE + "/repairs/repair-one/run.json"]


def test_review_fetch_missing_latest_defaults_to_original(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {"run.json": b"{}"})
    destination = runner.fetch_attempt("batch", "demo", tmp_path, review_only=True)
    assert destination.name == "original"
    assert volume.reads == [BASE + "/run.json"]


def test_review_fetch_file_count_bounds_zero_byte_artifacts(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {f"project/edit/tool-proposals/test_{i}.py": b"" for i in range(301)})
    destination = runner.fetch_attempt("batch", "demo", tmp_path, "original", review_only=True)
    assert len(volume.reads) == 200
    report = json.loads((destination / "fetch.json").read_text())
    assert len(report["skipped"]) == 100
    assert report["additional_skipped"] == 1


def test_default_fetch_still_downloads_delivery_and_source_archive(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {"project/edit/final.mp4": b"video", "source.zip": b"archive",
                                         "project/edit/audio.wav": b"audio", "agent-events.jsonl": b"private"})
    destination = runner.fetch_attempt("batch", "demo", tmp_path, "original")
    assert volume.reads == [BASE + "/project/edit/final.mp4", BASE + "/source.zip"]
    assert "review_only" not in json.loads((destination / "fetch.json").read_text())


@pytest.mark.parametrize("arguments", [["fetch", "--review-only", "--include-logs"], ["status", "--review-only"]])
def test_cli_rejects_review_conflicts_before_importing_modal(monkeypatch, arguments):
    monkeypatch.setitem(sys.modules, "modal", None)
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments)
    assert exc.value.code == 2


def test_api_rejects_log_conflict_before_importing_modal(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "modal", None)
    with pytest.raises(ValueError, match="cannot be combined"):
        runner.fetch_attempt("batch", "demo", tmp_path, include_logs=True, review_only=True)


def test_cli_forwards_opt_in_flag(tmp_path, monkeypatch):
    volume = install_volume(monkeypatch, {"run.json": b"{}", "source.zip": b"archive"})
    assert runner.main(["fetch", "--batch", "batch", "--id", "demo", "--attempt", "original",
                        "--output", str(tmp_path), "--review-only"]) == 0
    assert volume.reads == [BASE + "/run.json"]
