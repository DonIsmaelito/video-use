"""Known-rectangle coverage through real cuts and a clipped scrolling viewport."""

import io
import json
import subprocess

import numpy as np
import pytest

from helpers import tracked_mask as masking


def config(**changes):
    return {"version": 1, "source": "edited.mkv", "source_sha256": "0" * 64,
            "width": 192, "height": 96, "fps": 12, "audio": "none", "color": [24, 24, 24],
            "ranges": [[0, .5], [2, 2.5], [.5, 1]],
            "tracks": [{"name": "Known scrolling text", "intervals": [[0, .5], [2, 2.5]],
                        "keyframes": [[0, 12, 8, 40, 28], [3, 36, 44, 40, 28]],
                        "clip": [20, 20, 100, 50]}], **changes}


@pytest.mark.parametrize("changes", [
    {"version": True}, {"source": ""}, {"source_sha256": "bad"}, {"fps": 12.5},
    {"fps": True}, {"width": 191}, {"height": 0}, {"width": 4096, "height": 4096},
    {"audio": "preserve"}, {"color": [0, 256, 0]}, {"color": [True, 0, 0]},
    {"ranges": []}, {"ranges": [[1, 0]]}, {"ranges": [[0, .12]]},
    {"ranges": [[0, float("inf")]]}, {"ranges": [[0, 301]]},
    {"tracks": []}, {"automatic_face_detection": True},
])
def test_invalid_contracts_fail_before_decode(changes):
    with pytest.raises(ValueError):
        masking.validate_config(config(**changes))


@pytest.mark.parametrize("changes", [
    {"intervals": [[1, 0]]}, {"intervals": [[0, 2], [1, 3]]},
    {"intervals": [[0, float("nan")]]}, {"intervals": [[0, 4]]},
    {"keyframes": [[0, 1, 1, 10, 10]]},
    {"keyframes": [[0, 1, 1, 10, 10], [0, 2, 2, 10, 10]]},
    {"keyframes": [[0, 1, 1, -1, 10], [3, 2, 2, 10, 10]]},
    {"keyframes": [[0, 1, 1, 10, 10], [3, 2, float("inf"), 10, 10]]},
    {"clip": [190, 0, 10, 10]}, {"clip": [-1, 0, 10, 10]},
    {"blur": 20},
])
def test_ambiguous_track_geometry_is_rejected(changes):
    spec = config()
    spec["tracks"][0].update(changes)
    with pytest.raises(ValueError):
        masking.validate_config(spec)


def test_cut_clock_boundary_and_rectangular_half_open_intervals():
    spec = masking.validate_config(config())
    assert [masking.source_time(spec, i) for i in (0, 5, 6, 11, 12, 17)] == [
        0, 5/12, 2, 2+5/12, .5, .5+5/12]
    assert list(masking.mask_boxes(spec, .5)) == []
    assert list(masking.mask_boxes(spec, 2.5)) == []
    # Partial viewport overlap rounds mask outward while respecting its clip.
    assert list(masking.mask_boxes(spec, 0)) == [(20, 20, 52, 36)]
    with pytest.raises(ValueError):
        masking.source_time(spec, spec["frames"])


def make_source(tmp_path, fps):
    times = [i/fps for i in range(fps//2)] + [2+i/fps for i in range(fps//2)] + [.5+i/fps for i in range(fps//2)]
    frames = []
    for index, at in enumerate(times):
        frame = np.full((96, 192, 3), 96 + index, np.uint8)
        # Simulated private glyphs are inside the authored rectangle; some
        # pixels lie outside the scroll viewport and must remain unaffected.
        x, y = round(12 + 8*at), round(8 + 12*at)
        frame[y+4:y+24, x+4:x+36] = 238
        frame[76:88, 152:180] = 200 - index  # public frame-identity marker
        frames.append(frame)
    media = tmp_path / "edited.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "192x96",
                    "-r", str(fps), "-i", "-", "-c:v", "ffv1", str(media)],
                   input=np.stack(frames).tobytes(), check=True)
    path = tmp_path / "masks.json"
    path.write_text(json.dumps(config(fps=fps, source_sha256=masking.sha256(media))))
    return path, np.stack(frames), times


def decode(path):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return np.frombuffer(data, np.uint8).reshape(-1, 96, 192, 3)


@pytest.mark.parametrize("fps", [12, 24])
def test_every_encoded_frame_covers_known_text_across_cuts_without_moving_public_pixels(tmp_path, fps):
    path, original, times = make_source(tmp_path, fps)
    source_hash = masking.sha256(tmp_path / "edited.mkv")
    result = masking.render(path, tmp_path / "masked.mp4")
    encoded = decode(tmp_path / "masked.mp4")
    assert len(encoded) == len(times) == result["frames"]
    # Expected source clocks come from the independent fixture sequence,
    # including a forward jump and backward cut; no helper clock is reused.
    for index, at in enumerate(times):
        frame = encoded[index]
        if at < .5 or 2 <= at < 2.5:
            x0, y0 = max(20, round(12 + 8*at)+5), max(20, round(8 + 12*at)+5)
            x1, y1 = round(12 + 8*at)+35, min(70, round(8 + 12*at)+23)
            assert np.max(np.abs(frame[y0:y1, x0:x1].astype(int) - 24)) <= 6, (index, at)
        else:
            # The half-open mask is disabled exactly when the third cut
            # starts at source .5, preserving its unmasked fixture pixels.
            x, y = round(12 + 8*at), round(8 + 12*at)
            assert frame[y+7:y+21, x+7:x+33].mean() > 230
        assert np.abs(frame[78:86, 156:176].astype(float) - original[index,78:86,156:176]).mean() < 3
        # Clip protects the header, including moving white test glyphs.
        assert np.abs(frame[4:16, 24:44].astype(float) - original[index,4:16,24:44]).mean() < 4
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(tmp_path / "masked.mp4")]))
    assert len(probe["streams"]) == 1 and probe["streams"][0]["codec_type"] == "video"
    assert int(probe["streams"][0]["nb_frames"]) == len(times)
    assert masking.sha256(tmp_path / "edited.mkv") == source_hash
    assert not list(tmp_path.glob(".tracked-mask-*"))


def test_existing_source_config_and_hardlinks_are_protected(tmp_path):
    path, _, _ = make_source(tmp_path, 12)
    output = tmp_path / "previous.mp4"
    output.write_bytes(b"previous approved video")
    with pytest.raises(FileExistsError):
        masking.render(path, output)
    for protected in (path, tmp_path / "edited.mkv"):
        with pytest.raises(ValueError, match="overwrite"):
            masking.render(path, protected, overwrite=True)
    alias = tmp_path / "alias.mp4"
    alias.hardlink_to(tmp_path / "edited.mkv")
    with pytest.raises(ValueError, match="overwrite"):
        masking.render(path, alias, overwrite=True)
    assert output.read_bytes() == b"previous approved video"


@pytest.mark.parametrize("change, message", [
    ({"source_sha256": "0"*64}, "SHA-256"),
    ({"width": 194}, "dimensions"),
    ({"fps": 24}, "frame rate"),
])
def test_mismatched_media_contract_preserves_old_output(tmp_path, change, message):
    path, _, _ = make_source(tmp_path, 12)
    spec = json.loads(path.read_text())
    spec.update(change)
    path.write_text(json.dumps(spec))
    output = tmp_path / "previous.mp4"
    output.write_bytes(b"approved")
    with pytest.raises(ValueError, match=message):
        masking.render(path, output, overwrite=True)
    assert output.read_bytes() == b"approved"


def test_audio_is_rejected_without_being_silently_discarded(tmp_path):
    path, _, _ = make_source(tmp_path, 12)
    audible = tmp_path / "audible.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp_path / "edited.mkv"), "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1.5", "-c:v", "copy", "-c:a", "pcm_s16le", str(audible)], check=True)
    spec = json.loads(path.read_text())
    spec.update(source=audible.name, source_sha256=masking.sha256(audible))
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="no audio"):
        masking.render(path, tmp_path / "masked.mp4")
    assert not (tmp_path / "masked.mp4").exists()


def test_real_variable_frame_times_are_rejected(tmp_path):
    path, _, _ = make_source(tmp_path, 12)
    variable = tmp_path / "variable.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp_path / "edited.mkv"),
                    "-vf", "setpts=PTS+if(gte(N\\,6)\\,2/(12*TB)\\,0)", "-vsync", "vfr", "-c:v", "ffv1", str(variable)], check=True)
    spec = json.loads(path.read_text())
    spec.update(source=variable.name, source_sha256=masking.sha256(variable))
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="frame rate|timestamps"):
        masking.render(path, tmp_path / "masked.mp4")
    assert not (tmp_path / "masked.mp4").exists()


def test_truncated_input_and_failure_clean_up_both_children(tmp_path, monkeypatch):
    path, _, _ = make_source(tmp_path, 12)
    output = tmp_path / "previous.mp4"
    output.write_bytes(b"approved")
    actual = subprocess.Popen
    children = []

    def track(command, *args, **kwargs):
        process = actual(command, *args, **kwargs)
        if command[0] == "ffmpeg":
            children.append(process)
        return process

    def fail(*_):
        raise RuntimeError("intentional truncated input")

    monkeypatch.setattr(masking.subprocess, "Popen", track)
    monkeypatch.setattr(masking, "read_exact", fail)
    with pytest.raises(RuntimeError, match="truncated"):
        masking.render(path, output, overwrite=True)
    assert len(children) == 2 and all(child.poll() is not None for child in children)
    assert output.read_bytes() == b"approved"
    assert not list(tmp_path.glob(".tracked-mask-*"))


def test_read_exact_handles_partial_reads_and_rejects_early_eof():
    class Fragmented(io.BytesIO):
        def read(self, count):
            return super().read(min(count, 3))
    assert masking.read_exact(Fragmented(b"abcdefgh"), 8) == b"abcdefgh"
    with pytest.raises(RuntimeError, match="ended"):
        masking.read_exact(Fragmented(b"short"), 8)
