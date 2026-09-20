"""Delivery errors that can remain invisible in a visually convincing export."""
import struct

from helpers.motion_qa import mp4_faststart, sample_indices, spans, validate_video


def test_delivery_validation_catches_wrong_rate_and_truncated_frames():
    video = {"width": 1920, "height": 1080, "avg_frame_rate": "24/1", "duration": "11.0", "codec_name": "h264", "pix_fmt": "yuv420p", "color_space": "bt709"}
    errors = validate_video(video, {"fps": 30, "duration": 12, "frameCount": 360}, 264)
    assert len(errors) == 3
    assert any("frame count" in error for error in errors)
    video.update(avg_frame_rate="30/1", duration="12.0")
    assert validate_video(video, {"fps": 30, "duration": 12, "frameCount": 360}, 360) == []


def test_contact_sheet_includes_the_actual_final_frame():
    indices = sample_indices(360, 12)
    assert indices[0] == 0
    assert indices[-1] == 359
    assert len(set(indices)) == 12
    assert sample_indices(2, 12) == [0, 1]


def test_review_cues_preserve_one_frame_boundaries_and_ignore_short_holds():
    assert spans([0, 1, 3], 30) == [
        {"start": 0.0, "end": 0.0667, "duration": 0.0667},
        {"start": 0.1, "end": 0.1333, "duration": 0.0333},
    ]
    assert spans([0, 1, 3], 30, minimum_seconds=.75) == []


def test_faststart_reads_atom_structure_instead_of_searching_payload(tmp_path):
    atom = lambda kind, content=b"": struct.pack(">I4s", 8 + len(content), kind) + content
    video = tmp_path / "video.mp4"
    video.write_bytes(atom(b"ftyp") + atom(b"moov") + atom(b"mdat", b"payload"))
    assert mp4_faststart(video)
    video.write_bytes(atom(b"ftyp") + atom(b"mdat", b"fake moov bytes") + atom(b"moov"))
    assert not mp4_faststart(video)
    video.write_bytes(struct.pack(">I4s", 2, b"moov"))
    assert not mp4_faststart(video)
