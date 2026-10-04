"""Measured association contracts and actual encoded source-clock crop behavior.

Synthetic boxes test the spatial/crop contracts; they are not detector-accuracy
claims. A separately reviewed real-footage smoke covers YuNet itself.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from helpers import face_track, render
from helpers.face_follow import command_text, compile_crop_plan, prepared_crop


def _observations(source=None, timeline=None, boxes=None):
    source = source or {"file": "fixture.mp4", "sha256": "a" * 64, "bytes": 123,
                        "width": 320, "height": 180, "frame_count": 3, "time_base": "1/24",
                        "format_start_time": "0", "sample_aspect_ratio": "1:1", "rotation": 0}
    timeline = timeline or [{"index": i, "pts": i, "time": i / 24, "end": (i + 1) / 24} for i in range(3)]
    frames = []
    for i, frame in enumerate(timeline):
        current = boxes[i] if boxes is not None else [[50 + i * 2, 40, 40, 40]]
        frames.append({**frame, "detections": [{"bbox": box, "confidence": .95, "clipped": False} for box in current]})
    return {"schema": face_track.OBSERVATION_SCHEMA, "method": "per-frame YuNet face detection",
            "model": {"sha256": face_track.MODEL_SHA256}, "source": source,
            "shot": {"start": frames[0]["time"], "end": frames[-1]["end"]}, "frames": frames}


def _selection(observations):
    return {"seed_frame": observations["frames"][0]["index"], "seed_detection": 0,
            "visually_verified": True, "continuous_shot_verified": True,
            "evidence": "Synthetic fixture target is explicitly designated for contract testing"}


def _track(observations):
    return face_track.select_track(observations, _selection(observations))


LAYOUT = {"width": 90, "height": 160}
SPEC = {"track": "track.json", "smoothing_seconds": 0, "deadzone": 0, "max_pan_speed": 20}


def test_model_bytes_and_license_are_pinned():
    assert face_track.MODEL_PATH.stat().st_size == 232589
    assert face_track.sha256(face_track.MODEL_PATH) == face_track.MODEL_SHA256
    assert face_track.sha256(face_track.MODEL_PATH.with_name("LICENSE")) == "c83b8120c50ccbd4c4f96edf53141bdd566ebb8f8e9227e415326aa1b1aba958"
    manifest = json.loads(face_track.MODEL_PATH.with_name("MODEL.json").read_text())
    assert manifest["sha256"] == face_track.MODEL_SHA256
    assert manifest["commit"] == face_track.MODEL_COMMIT


def test_spatial_association_uses_adjacent_boxes_not_face_order_or_size():
    observations = _observations(boxes=[[[40, 40, 40, 40], [210, 20, 80, 90]],
                                         [[208, 20, 80, 90], [44, 42, 40, 40]],
                                         [[48, 44, 40, 40], [206, 20, 80, 90]]])
    track = _track(observations)
    assert [row["detection"] for row in track["frames"]] == [0, 1, 0]
    assert all(row["state"] == "selected" for row in track["frames"])
    assert [row["bbox"][0] for row in track["frames"]] == [40, 44, 48]


@pytest.mark.parametrize("middle,reason", [([], "no_consistent_detection"),
    ([[50, 40, 40, 40], [52, 40, 40, 40]], "ambiguous_spatial_association"),
    ([[240, 40, 40, 40]], "no_consistent_detection")])
def test_loss_and_ambiguity_never_silently_reacquire(middle, reason):
    track = _track(_observations(boxes=[[[50, 40, 40, 40]], middle, [[52, 40, 40, 40]]]))
    assert track["frames"][1]["reason"] == reason
    assert track["frames"][2]["state"] == "lost"
    assert track["frames"][2]["bbox"] is None
    with pytest.raises(ValueError, match="evidence"):
        compile_crop_plan(track, track["observations"]["source"], track["observations"]["frames"], 0, 3 / 24, LAYOUT, SPEC)


@pytest.mark.parametrize("change", [
    {"visually_verified": False}, {"continuous_shot_verified": False}, {"evidence": ""},
    {"seed_frame": 1}, {"seed_frame": False}, {"seed_detection": 1}, {"seed_detection": True},
    {"speaker_mapping": {"speaker_id": "speaker_0", "method": "largest_face", "evidence": "size"}},
    {"recognize_person": True},
])
def test_unreviewed_or_invented_selection_is_rejected(change):
    observations = _observations()
    with pytest.raises(ValueError):
        face_track.select_track(observations, {**_selection(observations), **change})


def test_explicit_speaker_mapping_is_recorded_without_inference():
    observations = _observations()
    mapping = {"speaker_id": "speaker_1", "method": "explicit_source_review", "evidence": "Reviewed source speech and face at shot start"}
    track = face_track.select_track(observations, {**_selection(observations), "speaker_mapping": mapping})
    assert track["selection"]["speaker_mapping"] == mapping


@pytest.mark.parametrize("fault", ["hash", "geometry", "nan", "gap", "confidence", "model"])
def test_invalid_observation_evidence_fails(fault):
    observations = _observations()
    if fault == "hash": observations["source"]["sha256"] = "missing"
    if fault == "geometry": observations["frames"][1]["detections"][0]["bbox"][0] = 310
    if fault == "nan": observations["frames"][1]["time"] = float("nan")
    if fault == "gap": observations["frames"].pop(1)
    if fault == "confidence": observations["frames"][1]["detections"][0]["confidence"] = -1
    if fault == "model": observations["model"]["sha256"] = "b" * 64
    with pytest.raises(ValueError): face_track.validate_observations(observations)


def test_tampered_selection_cannot_hide_ambiguous_observation():
    track = _track(_observations())
    track["frames"][1]["bbox"][0] += 10
    with pytest.raises(ValueError, match="differs"):
        face_track.validate_track(track)


@pytest.mark.parametrize("fault", ["source_hash", "source_width", "pts", "shot", "crop", "padding", "speed", "nan", "unknown"])
def test_crop_rejects_wrong_source_clock_geometry_or_unbounded_settings(fault):
    observations = _observations(boxes=[[[50, 40, 40, 40]], [[66, 40, 40, 40]], [[82, 40, 40, 40]]])
    track = _track(observations)
    source = copy.deepcopy(observations["source"])
    timeline = copy.deepcopy(observations["frames"])
    layout, spec = copy.deepcopy(LAYOUT), copy.deepcopy(SPEC)
    duration = 3 / 24
    if fault == "source_hash": source["sha256"] = "b" * 64
    if fault == "source_width": source["width"] = 640
    if fault == "pts": timeline[1]["pts"] += 1
    if fault == "shot": duration = 1
    if fault == "crop": layout["crop"] = {"x": 0, "y": 0, "width": 100, "height": 100}
    if fault == "padding": spec["padding"] = {"horizontal": 1}
    if fault == "speed": spec["max_pan_speed"] = .1
    if fault == "nan": spec["smoothing_seconds"] = float("nan")
    if fault == "unknown": spec["detect_active_speaker"] = True
    with pytest.raises(ValueError): compile_crop_plan(track, source, timeline, 0, duration, layout, spec)


def test_smoothing_is_bounded_by_measured_head_clearance_and_preview_does_not_change_source_crop():
    observations = _observations(boxes=[[[50, 40, 40, 40]], [[66, 40, 40, 40]], [[82, 40, 40, 40]]])
    track = _track(observations)
    plan = compile_crop_plan(track, observations["source"], observations["frames"], 0, 3 / 24,
                             {"width": 1080, "height": 1920}, {"track": "track.json"})
    assert plan["crop_size"] == [90, 160]
    assert plan["frames"][1]["x"] < 66 + 20 - 45
    for row in plan["frames"]:
        l, t, r, b = row["required_bounds"]
        assert row["x"] <= l and r <= row["x"] + 90
        assert row["y"] <= t and b <= row["y"] + 160
    commands = command_text(plan)
    assert "crop@face_follow x" in commands
    assert len(commands.splitlines()) <= len(plan["frames"])


has_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="Requires FFmpeg")


def _run(*args, input=None):
    return subprocess.run(list(args), input=input, check=True, capture_output=True, timeout=120).stdout


def _source(path, sample_rate=44100, audio_delay=0., rate=24, silent=False, start_offset=0):
    yy, xx = np.indices((180, 320))
    images = []
    for i in range(36):
        images.append(np.stack([xx * .75, yy * 1.2, np.full_like(xx, 10 + i * 6)], axis=-1).astype(np.uint8))
    command = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "320x180",
               "-framerate", str(rate), "-i", "pipe:0"]
    if not silent:
        command += ["-itsoffset", str(audio_delay), "-f", "lavfi", "-i",
                    f"aevalsrc='0.5*sin(2*PI*1000*t)*(between(t,0.35,0.45)+between(t,0.95,1.05))':s={sample_rate}:d=1.5"]
    command += ["-c:v", "libx264", "-preset", "fast", "-crf", "12", "-bf", "3", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-output_ts_offset", str(start_offset), str(path)]
    _run(*command, input=np.stack(images).tobytes())
    source, timeline = face_track.probe_source(path)
    boxes = []
    for frame in timeline:
        i = frame["index"]
        phase = i % 24
        boxes.append([[45 + min(phase, 24 - phase) * 16, 30 + min(i, 28) * 2, 40, 40]])
    observations = _observations(source, timeline, boxes)
    track = _track(observations)
    track_path = path.with_suffix(".track.json")
    track_path.write_text(json.dumps(track))
    return track_path


def _rgb(path, width, height):
    raw = _run("ffmpeg", "-v", "error", "-i", str(path), "-an", "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 3).astype(float)


def _audio(path):
    return np.frombuffer(_run("ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "48000",
                             "-af", "aresample=async=1:first_pts=0", "-f", "f32le", "pipe:1"), dtype="<f4")


@has_ffmpeg
@pytest.mark.parametrize("start_offset", [0, 2.0])
def test_encoded_crop_positions_on_actual_source_clock_and_nonzero_container_origin(tmp_path, start_offset):
    source, output = tmp_path / "source.mp4", tmp_path / "follow.mp4"
    track_path = _source(source, start_offset=start_offset)
    render.extract_segment(source, .13, .6, "", output, rate="30", layout=LAYOUT,
                           face_follow={**SPEC, "track": str(track_path)})
    frames = _rgb(output, 90, 160)
    assert len(frames) == 18
    proof = json.loads(output.with_suffix(".face-follow.json").read_text())
    plans = {row["source_frame"]: row for row in proof["frames"]}
    for image in frames:
        center = np.median(image[75:85, 40:50], axis=(0, 1))
        source_index = round((center[2] - 10) / 6)
        row = plans[source_index]
        assert center[0] == pytest.approx((row["x"] + 44.5) * .75, abs=3.5)
        assert center[1] == pytest.approx((row["y"] + 79.5) * 1.2, abs=3.5)
    streams = json.loads(_run("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)))["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert float(video["start_time"]) == 0
    assert float(video["duration"]) == pytest.approx(.6)


@has_ffmpeg
@pytest.mark.parametrize("sample_rate,delay", [(44100, -.06), (48000, .08)])
def test_two_cuts_keep_original_audio_events_and_identical_untracked_audio(tmp_path, sample_rate, delay):
    source = tmp_path / "source.mp4"
    track_path = _source(source, sample_rate=sample_rate, audio_delay=delay)
    ranges = [{"source": "a", "start": start, "end": start + .6, "layout": LAYOUT,
               "face_follow": {**SPEC, "track": track_path.name}} for start in (.1, .8)]
    edl = {"sources": {"a": str(source)}, "ranges": ranges}
    clips = render.extract_all_segments(edl, tmp_path, False, fps="30")
    final = tmp_path / "follow.mp4"
    render.concat_segments(clips, final, tmp_path)
    baseline_clips = []
    for i, start in enumerate((.1, .8)):
        path = tmp_path / f"baseline-{i}.mp4"
        render.extract_segment(source, start, .6, "", path, rate="30", layout=LAYOUT)
        baseline_clips.append(path)
    baseline = tmp_path / "baseline.mp4"
    render.concat_segments(baseline_clips, baseline, tmp_path)
    actual, reference = _audio(final), _audio(baseline)
    assert np.array_equal(actual, reference)
    assert len(_rgb(final, 90, 160)) == 36
    for expected in (.4 + delay - .1, .6 + 1 + delay - .8):
        lo, hi = round((expected - .1) * 48000), round((expected + .1) * 48000)
        energy = actual[lo:hi].astype(float) ** 2
        center = np.sum(np.arange(lo, hi) / 48000 * energy) / energy.sum()
        assert center == pytest.approx(expected, abs=.008)


@has_ffmpeg
def test_silent_source_and_explicit_picture_window_keep_canvas_and_matte(tmp_path):
    source, output = tmp_path / "source.mp4", tmp_path / "follow.mp4"
    track_path = _source(source, silent=True)
    layout = {"width": 160, "height": 240, "background": "#102030",
              "window": {"x": 34, "y": 40, "width": 90, "height": 160, "fit": "contain"}}
    render.extract_segment(source, .25, .5, "", output, rate="24", layout=layout,
                           face_follow={**SPEC, "track": str(track_path)})
    image = _rgb(output, 160, 240)
    assert len(image) == 12
    assert np.max(np.abs(image[0, 10, 10] - [16, 32, 48])) <= 3
    streams = json.loads(_run("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)))["streams"]
    assert [stream["codec_type"] for stream in streams] == ["video"]


@has_ffmpeg
def test_temp_commands_clean_up_and_protected_inputs_cannot_be_outputs(tmp_path):
    source = tmp_path / "source.mp4"
    track_path = _source(source, silent=True)
    spec = {**SPEC, "track": str(track_path)}
    for output in (source, track_path):
        with pytest.raises(ValueError, match="overwrite"):
            with prepared_crop(spec, source, 0, .5, LAYOUT, output): pass
    command_path = None
    with pytest.raises(RuntimeError):
        with prepared_crop(spec, source, 0, .5, LAYOUT, tmp_path / "final.mp4") as (filters, _):
            command_path = Path(filters.split("filename=", 1)[1].split(",", 1)[0])
            assert command_path.is_file()
            raise RuntimeError("simulated encoder failure")
    assert command_path is not None and not command_path.exists()


@has_ffmpeg
def test_vfr_crop_commands_follow_measured_frames_instead_of_assumed_fps(tmp_path):
    original, source, output = (tmp_path / name for name in ("original.mp4", "vfr.mp4", "final.mp4"))
    _source(original, silent=True)
    _run("ffmpeg", "-y", "-v", "error", "-i", str(original), "-vf", "select='not(eq(mod(n,5),2))'",
         "-fps_mode", "vfr", "-c:v", "libx264", "-crf", "12", "-video_track_timescale", "90000", "-an", str(source))
    metadata, timeline = face_track.probe_source(source)
    assert len({round(frame["end"] - frame["time"], 4) for frame in timeline}) > 1
    boxes = [[[45 + min(i % 24, 24 - i % 24) * 16, 40, 40, 40]] for i in range(len(timeline))]
    track = _track(_observations(metadata, timeline, boxes))
    track_path = tmp_path / "vfr-track.json"
    track_path.write_text(json.dumps(track))
    render.extract_segment(source, .13, .6, "", output, rate="30", layout=LAYOUT,
                           face_follow={**SPEC, "track": str(track_path)})
    actual = _rgb(output, 90, 160)
    assert len(actual) == 18
    source_blue = np.median(_rgb(source, 320, 180)[:, 75:85, 40:50, 2], axis=(1, 2))
    plan = json.loads(output.with_suffix(".face-follow.json").read_text())
    rows = {row["source_frame"]: row for row in plan["frames"]}
    for image in actual:
        color = np.median(image[75:85, 40:50], axis=(0, 1))
        index = int(np.argmin(np.abs(source_blue - color[2])))
        assert color[0] == pytest.approx((rows[index]["x"] + 44.5) * .75, abs=3.5)


@has_ffmpeg
def test_preview_uses_same_original_crop_coordinates(tmp_path):
    source = tmp_path / "source.mp4"
    track_path = _source(source, silent=True)
    plans = []
    for preview in (False, True):
        output = tmp_path / f"preview-{preview}.mp4"
        render.extract_segment(source, .25, .1, "", output, rate="30", preview=preview,
                               layout={"width": 1080, "height": 1920},
                               face_follow={**SPEC, "track": str(track_path)})
        plan = json.loads(output.with_suffix(".face-follow.json").read_text())
        plans.append(plan["frames"])
        streams = json.loads(_run("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)))["streams"]
        assert (streams[0]["width"], streams[0]["height"]) == ((720, 1280) if preview else (1080, 1920))
    assert plans[0] == plans[1]


def test_second_canvas_transform_rejected_before_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "extract_segment", lambda *args, **kwargs: pytest.fail("must reject before encoding"))
    for treatment in ({"canvas": {"width": 1080, "height": 1920}}, {"reframe": {"zoom": 2}}):
        edl = {"sources": {"source": "source.mp4"}, "treatment": treatment,
               "ranges": [{"source": "source", "start": 0, "end": 1, "layout": LAYOUT, "face_follow": {"track": "track.json"}}]}
        with pytest.raises(ValueError): render.extract_all_segments(edl, tmp_path, False)
