from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest

from gui.modal_app import _run_command


def test_run_command_preserves_unfiltered_output_on_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class Process:
        stdout = io.StringIO(
            "configuration: hidden from the GUI pane\n"
            "Stream #0:0 -> #0:0 (libx264)\n"
            "render failed\n"
        )

        @staticmethod
        def wait() -> int:
            return 7

    monkeypatch.setattr("gui.modal_app.subprocess.Popen", lambda *_args, **_kwargs: Process())
    log_path = tmp_path / "render.log"

    with pytest.raises(subprocess.CalledProcessError):
        list(_run_command(["python", "render.py"], log_path))

    log = log_path.read_text()
    assert "$ python render.py" in log
    assert "configuration: hidden from the GUI pane" in log
    assert "Stream #0:0 -> #0:0 (libx264)" in log
    assert "[process exited 7]" in log
