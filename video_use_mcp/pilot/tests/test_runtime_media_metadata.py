"""Regressions from the first solar explainer: timing, previews, and retries."""

import asyncio
import json
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from video_use_mcp.pilot.runtime import Manager


class LocalMedia:
    def __init__(self, root):
        self.root = root

    async def safe_path(self, path, write=False):
        target = self.root / path
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
        return str(target)

    async def run(self, command, timeout=180):
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.root,
        )
        return dict(
            exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr
        )

    async def download(self, path, target, max_bytes=None):
        shutil.copyfile(self.root / path, target)

    async def upload(self, path, local):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, target)

    async def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def read(self, path):
        return (self.root / path).read_bytes()


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def manager_fixture(tmp_path):
    store = Mock()
    store.get.return_value = None
    manager = Manager(
        store, SimpleNamespace(speech_key="mock-speech", voice="mock-voice")
    )

    async def save(uid, pid, kind, name, local):
        shutil.copyfile(local, tmp_path / ("saved-" + name))
        return dict(id="object", key="object-key", name=name)

    manager.save_object = AsyncMock(side_effect=save)
    return manager, store


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("duration,truncated", [(31, False), (121, True)])
def test_preview_keeps_complete_short_film_and_labels_long_excerpt(
    tmp_path, duration, truncated
):
    source = tmp_path / "draft.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=s=160x90:r=3:d={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )
    manager, _ = manager_fixture(tmp_path)
    result = asyncio.run(
        manager.publish_preview("u", "p", LocalMedia(tmp_path), "draft.mp4")
    )
    data = probe(tmp_path / "saved-preview.mp4")
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert video["avg_frame_rate"] == "3/1"  # no conversion from 3 fps to 24 fps
    assert video["width"] == 160 and video["height"] == 90  # no enlargement
    assert float(data["format"]["duration"]) == pytest.approx(
        min(duration, 120), abs=0.1
    )
    assert result["source_duration"] == duration
    assert result["duration"] == min(duration, 120)
    assert result["truncated"] is truncated
    assert ("preview_range" in result) is truncated
    if truncated:
        assert result["preview_range"] == {"start": 0, "end": 120}
        assert "excerpt" in result["notice"]
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(tmp_path / "saved-preview.mp4"),
            "-f",
            "null",
            "-",
        ],
        check=True,
    )


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("cached", [False, True])
def test_narration_has_measured_duration_and_sentence_timings_without_second_tool(
    tmp_path, cached
):
    source = tmp_path / "voice.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            str(source),
        ],
        check=True,
    )
    timings = json.dumps(
        {
            "text": "Sunlight arrives. Electrons move.",
            "words": [
                {"text": "Sunlight", "start": 0.1, "end": 0.4},
                {"text": "arrives.", "start": 0.5, "end": 0.8},
                {"text": "Electrons", "start": 1, "end": 1.4},
                {"text": "move.", "start": 1.5, "end": 1.8},
            ],
        }
    )
    manager, store = manager_fixture(tmp_path)
    store.get.side_effect = (
        lambda kind, key: {"key": "audio-key", "timings": timings}
        if cached and kind == "narration"
        else None
    )
    store.download.side_effect = lambda key, path: shutil.copyfile(source, path)
    sb = LocalMedia(tmp_path)

    async def narrate(text, output):
        await sb.upload(output, source)
        await sb.write(output + ".json", timings.encode())
        return {"text": "Old instruction asking the host to probe audio"}

    task = {
        "owner": "u",
        "project": "p",
        "id": "t",
        "operation": "narrate",
        "payload": {
            "text": "Sunlight arrives. Electrons move.",
            "output": "edit/voice.mp3",
        },
    }
    with patch(
        "video_use_mcp.pilot.runtime.ProductionAgent.narrate",
        AsyncMock(side_effect=narrate),
    ) as service:
        result = asyncio.run(manager.perform(task, sb))
    assert service.await_count == (0 if cached else 1)
    assert result["duration"] == pytest.approx(2, abs=0.1)
    assert result["speech_end"] == 1.8
    assert result["word_count"] == 4
    assert result["audio_path"] == "edit/voice.mp3"
    assert result["timing_path"] == "edit/voice.mp3.json"
    assert result["sentence_timings"] == [
        {"text": "Sunlight arrives.", "start": 0.1, "end": 0.8},
        {"text": "Electrons move.", "start": 1, "end": 1.8},
    ]
    assert "No timing probe is needed" in result["text"]


@pytest.mark.parametrize("legacy_key", ["first", "project:first", "project:step:first"])
def test_request_ids_reuse_legacy_exact_retries_and_allow_other_operations(legacy_key):
    async def scenario():
        store = Mock()
        store.get.return_value = None
        tasks = [
            {
                "id": "old",
                "project": "project",
                "operation": "step",
                "request_id": legacy_key,
                "payload": {"command": "render"},
            }
        ]

        def sql(query, *args):
            if query.startswith("SELECT * FROM public.vp_tasks"):
                return [t for t in tasks if t["request_id"] in args[1:]]
            if query.startswith("INSERT INTO public.vp_tasks"):
                task = dict(
                    id=args[0],
                    owner=args[1],
                    project=args[2],
                    operation=args[3],
                    request_id=args[4],
                    payload=json.loads(args[5]),
                )
                tasks.append(task)
                return [task]
            return []

        store.sql.side_effect = sql
        manager = Manager(store, SimpleNamespace())
        manager.execute = AsyncMock()
        assert (
            manager.submit("u", "project", "step", {"command": "render"}, "first")["id"]
            == "old"
        )
        with pytest.raises(ValueError, match="new request_id"):
            manager.submit("u", "project", "step", {"command": "changed"}, "first")
        new = manager.submit("u", "project", "narrate", {"text": "Hello"}, "first")
        assert new["request_id"] == "project:narrate:first"
        assert (
            manager.submit("u", "project", "narrate", {"text": "Hello"}, "first")["id"]
            == new["id"]
        )
        store.reserve.assert_called_once()
        await asyncio.gather(*manager.running.values())

    asyncio.run(scenario())
