"""Assembly validates the whole batch and preserves actual frame/audio timing."""

import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from helpers import assemble_scenes as assembly

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def scene(duration=1, color="#1a6541", **kwargs):
    return {
        "duration": duration,
        "width": 320,
        "height": 180,
        "fps": 30,
        "marks": [
            {
                "id": "dot",
                "kind": "ellipse",
                "x": 160,
                "y": 90,
                "w": 50,
                "h": 50,
                "fill": color,
            }
        ],
        **kwargs,
    }


def save(root, name, data):
    target = root / "edit" / "scenes" / (name + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data))


def test_all_invalid_sources_reported_before_any_render_or_output(
    tmp_path, monkeypatch
):
    save(tmp_path, "one", scene())
    for name in ("two", "three"):
        invalid = scene()
        invalid["marks"][0]["keyframes"] = [{"time": -0.1}, {"time": 2}]
        save(tmp_path, name, invalid)
    render = Mock()
    monkeypatch.setattr(assembly, "render_scene", render)
    with pytest.raises(ValueError) as error:
        assembly.assemble_scenes(
            {"scene_ids": ["one", "two", "three"]}, "out.mp4", root=tmp_path
        )
    for name in ("two", "three"):
        assert f"{name}:" in str(error.value)
    assert str(error.value).count("time=-0.1") == 2
    render.assert_not_called()
    assert not (tmp_path / "edit/.assembly-cache").exists()
    assert not (tmp_path / "out.mp4").exists()


@pytest.mark.parametrize(
    "options",
    [
        {"scene_ids": ["../escape"]},
        {"scene_ids": []},
        {"scene_ids": ["one"], "fps": 31},
        {"scene_ids": ["one"], "width": 1920},
        {"scene_ids": ["one"], "narration_offset": float("nan")},
        {"scene_ids": ["one"], "narration_offset": 2},
    ],
)
def test_bad_options_rejected_without_tools(options):
    with pytest.raises(ValueError):
        assembly.validate_spec(options)


def test_preflight_preserves_aspect_and_uses_actual_output_frame_grid(tmp_path):
    save(tmp_path, "first", scene(0.11))
    save(tmp_path, "second", scene(0.21))
    draft = assembly.preflight({"scene_ids": ["first", "second"]}, tmp_path)
    assert (draft["width"], draft["height"], draft["fps"]) == (960, 540, 15)
    assert [s["frame_count"] for s in draft["scenes"]] == [2, 4]
    assert draft["duration"] == 0.4
    final = assembly.preflight(
        {"scene_ids": ["first", "second"], "quality": "final"}, tmp_path
    )
    assert (final["width"], final["height"], final["fps"]) == (1920, 1080, 30)
    assert [s["frame_count"] for s in final["scenes"]] == [4, 7]
    assert final["duration"] == 11 / 30
    save(tmp_path, "portrait", scene(width=180, height=320))
    portrait = assembly.preflight(
        {"scene_ids": ["portrait"], "quality": "final"}, tmp_path
    )
    assert (portrait["width"], portrait["height"]) == (1080, 1920)
    with pytest.raises(ValueError, match="aspect ratio"):
        assembly.preflight({"scene_ids": ["first", "portrait"]}, tmp_path)


def fake_renderer(value, output, **options):
    fps = options["output_fps"]
    duration = assembly.math.ceil(value["duration"] * fps - 1e-9) / fps
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=red:s={options['output_width']}x{options['output_height']}:r={fps}:d={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        check=True,
    )
    return {"warnings": ["Text fitted at reduced size"]}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_encoded_assembly_frame_grid_cache_invalidation_and_audio_loudness(
    tmp_path, monkeypatch
):
    render = Mock(side_effect=fake_renderer)
    monkeypatch.setattr(assembly, "render_scene", render)
    save(tmp_path, "one", scene(3.11))
    save(tmp_path, "two", scene(3.21))
    audio = tmp_path / "audio/narration.wav"
    audio.parent.mkdir()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=5.5",
            "-af",
            "volume=0.2",
            str(audio),
        ],
        check=True,
    )
    spec = {
        "scene_ids": ["one", "two"],
        "width": 320,
        "height": 180,
        "narration_path": "audio/narration.wav",
        "narration_offset": 0.5,
    }
    report = assembly.assemble_scenes(spec, "out.mp4", root=tmp_path)
    assert report["frame_count"] == 96
    assert [s["seconds"] for s in report["scenes"]] == [47 / 15, 49 / 15]
    assert report["production_timing"]["narration_offset"] == 0.5
    data = assembly.probe(tmp_path / "out.mp4")
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert float(video["duration"]) == pytest.approx(6.4, abs=0.002)
    assert int(video["nb_frames"]) == 96
    measured = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(tmp_path / "out.mp4"),
            "-af",
            "loudnorm=I=-16:TP=-1.5:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    levels = json.loads(
        measured.stderr[measured.stderr.rfind("{") : measured.stderr.rfind("}") + 1]
    )
    assert float(levels["input_i"]) == pytest.approx(-16, abs=1)
    assert float(levels["input_tp"]) <= -1
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(tmp_path / "out.mp4"),
            "-t",
            "0.35",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-",
        ]
    )
    # AAC may leave very quiet transform/priming noise in padded silence.
    assert (
        max(
            abs(int.from_bytes(raw[i : i + 2], "little", signed=True))
            for i in range(0, len(raw), 2)
        )
        <= 100
    )
    repeated = assembly.assemble_scenes(spec, "repeat.mp4", root=tmp_path)
    assert all(s["reused"] for s in repeated["scenes"])
    assert all(
        s["warnings"] == ["Text fitted at reduced size"] for s in repeated["scenes"]
    )
    assert render.call_count == 2
    save(tmp_path, "two", scene(3.21, color="#ffffff"))
    changed = assembly.assemble_scenes(spec, "changed.mp4", root=tmp_path)
    assert [s["reused"] for s in changed["scenes"]] == [True, False]
    assert render.call_count == 3
    with pytest.raises(ValueError, match="instead of truncating"):
        assembly.assemble_scenes(
            spec | {"narration_offset": 1.5}, "bad.mp4", root=tmp_path
        )
    assert render.call_count == 3
    receipt = Path(changed["scenes"][0]["video_path"]).parent / "complete.json"
    receipt.write_text('{"interrupted')
    recovered = assembly.assemble_scenes(spec, "recovered.mp4", root=tmp_path)
    assert [s["reused"] for s in recovered["scenes"]] == [False, True]
    assert render.call_count == 4


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_preflight_rejects_even_short_audible_narration_overrun(tmp_path, monkeypatch):
    save(tmp_path, "one", scene(1))
    audio = tmp_path / "voice.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1.05",
            str(audio),
        ],
        check=True,
    )
    render = Mock()
    monkeypatch.setattr(assembly, "render_scene", render)
    with pytest.raises(ValueError, match="instead of truncating"):
        assembly.assemble_scenes(
            {"scene_ids": ["one"], "narration_path": "voice.wav"},
            "bad.mp4",
            root=tmp_path,
        )
    render.assert_not_called()


@pytest.mark.skipif(
    not CHROME.exists() or not shutil.which("ffmpeg"), reason="Chrome/FFmpeg required"
)
def test_actual_vector_assembly_renders_native_final_canvas_and_decodes(tmp_path):
    save(tmp_path, "first", scene(0.11))
    save(tmp_path, "second", scene(0.21, color="#813fc6"))
    report = assembly.assemble_scenes(
        {"scene_ids": ["first", "second"], "quality": "final"},
        "final.mp4",
        root=tmp_path,
        chrome=CHROME,
    )
    assert (report["width"], report["height"], report["fps"]) == (1920, 1080, 30)
    assert report["frame_count"] == 11
    video = next(
        s
        for s in assembly.probe(tmp_path / "final.mp4")["streams"]
        if s["codec_type"] == "video"
    )
    assert (video["width"], video["height"], int(video["nb_frames"])) == (
        1920,
        1080,
        11,
    )
    for item in report["scenes"]:
        source = json.loads(
            Path(item["video_path"])
            .with_suffix(".scene")
            .joinpath("scene.json")
            .read_text()
        )
        assert (source["width"], source["height"]) == (320, 180)
