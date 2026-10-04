"""Measured face detections and conservative spatial association, not recognition.

Detect every decoded frame in an explicitly bounded shot. Selection is a second
step requiring a reviewed seed. Missing/ambiguous evidence stops association;
only another explicit shot/seed can restart it. No active-speaker inference.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np

MODEL_COMMIT = "f12e12798e8314f7c074a6656816c048dcc95b7a"
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_NAME = "face_detection_yunet_2023mar.onnx"
MODEL_PATH = Path(__file__).resolve().parents[1] / "assets" / "models" / "yunet" / MODEL_NAME
MAX_FRAMES = 14400
MAX_SHOT_SECONDS = 120
MAX_JSON_BYTES = 64 * 1024 * 1024
OBSERVATION_SCHEMA = "video-use.face-observations.v1"
TRACK_SCHEMA = "video-use.face-track.v1"


def finite(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside its supported range")
    return float(value)


def integer(value, name, minimum=0, maximum=MAX_FRAMES):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Face evidence JSON exceeds 64 MiB")
    return json.loads(path.read_text())


def write_new_json(path, value):
    """Never overwrite footage, prior evidence or an existing authored file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(serialized)


def probe_source(path):
    """Read display-order PTS on FFmpeg's input seek clock, including A/V offsets."""
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024**3:
        raise ValueError("Source must be a nonempty local video of at most 2 GiB")
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-show_format",
               "-show_frames", "-show_entries",
               "stream:format=start_time,duration:frame=best_effort_timestamp,best_effort_timestamp_time",
               "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, check=True, timeout=180)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if len(streams) != 1:
        raise ValueError("Source needs one primary decodable video stream")
    stream = streams[0]
    width, height = (integer(stream.get(k), k, 2, 8192) for k in ("width", "height"))
    if stream.get("sample_aspect_ratio", "1:1") not in {"1:1", "0:1", "N/A"}:
        raise ValueError("Face coordinates require square-pixel footage")
    rotations = [float(item.get("rotation", 0)) for item in stream.get("side_data_list", [])]
    rotations.append(float(stream.get("tags", {}).get("rotate", 0)))
    if any(not math.isfinite(rotation) or rotation % 360 != 0 for rotation in rotations):
        raise ValueError("Normalize metadata rotation before detecting faces")
    time_base = Fraction(stream["time_base"])
    origin = Fraction(data.get("format", {}).get("start_time", "0"))
    duration = float(data.get("format", {}).get("duration", 0))
    finite(duration, "source duration", .001, 3600)
    frames = []
    for index, frame in enumerate(data.get("frames", [])):
        if type(frame.get("best_effort_timestamp")) is not int:
            raise ValueError("Face tracking requires actual integer frame PTS")
        pts = frame["best_effort_timestamp"]
        frames.append({"index": index, "pts": pts, "time": float(pts * time_base - origin)})
    if not frames or len(frames) > 432000 or any(b["time"] <= a["time"] for a, b in zip(frames, frames[1:])):
        raise ValueError("Source needs strictly increasing display timestamps and at most 432000 frames")
    if "duration_ts" in stream:
        stream_end = (Fraction(stream.get("start_pts", frames[0]["pts"])) + stream["duration_ts"]) * time_base - origin
    elif stream.get("duration") not in (None, "N/A"):
        stream_end = Fraction(str(stream.get("start_time", 0))) + Fraction(stream["duration"]) - origin
    else:
        rate = Fraction(stream.get("avg_frame_rate", "0/1"))
        if rate <= 0:
            raise ValueError("Cannot establish the final video frame duration")
        stream_end = Fraction(frames[-1]["pts"]) * time_base - origin + 1 / rate
    for index, frame in enumerate(frames):
        frame["end"] = frames[index + 1]["time"] if index + 1 < len(frames) else float(stream_end)
        if frame["end"] <= frame["time"]:
            raise ValueError("Invalid frame duration")
    source = {"file": path.name, "sha256": sha256(path), "bytes": path.stat().st_size,
              "width": width, "height": height, "frame_count": len(frames),
              "time_base": str(time_base), "format_start_time": str(origin),
              "clock": "decoded PTS minus format.start_time in seconds; same clock as input -ss",
              "first_frame_time": frames[0]["time"], "video_end": frames[-1]["end"],
              "sample_aspect_ratio": "1:1", "rotation": 0}
    return source, frames


def _box(value, width, height):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("Face bbox must be [x,y,width,height] in source pixels")
    x, y, w, h = [finite(number, "face bbox coordinate", 0, 8192) for number in value]
    if w < 2 or h < 2 or x + w > width + 1e-5 or y + h > height + 1e-5:
        raise ValueError("Face bbox lies outside source geometry")
    return x, y, w, h


def validate_observations(data):
    if not isinstance(data, dict) or data.get("schema") != OBSERVATION_SCHEMA:
        raise ValueError("Expected measured face-observations v1")
    source = data.get("source", {})
    if not isinstance(source, dict):
        raise ValueError("Face observations need source metadata")
    if not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
        raise ValueError("Source SHA256 is required")
    width, height = (integer(source.get(k), k, 2, 8192) for k in ("width", "height"))
    if not isinstance(data.get("model"), dict) or data["model"].get("sha256") != MODEL_SHA256 or data.get("method") != "per-frame YuNet face detection":
        raise ValueError("Observations must identify the pinned YuNet detector")
    shot = data.get("shot", {})
    if not isinstance(shot, dict):
        raise ValueError("Face observations need explicit shot bounds")
    start = finite(shot.get("start"), "shot start", 0, 3600)
    end = finite(shot.get("end"), "shot end", start + 1e-6, 3600)
    if end - start > MAX_SHOT_SECONDS:
        raise ValueError("Each explicit shot must be at most 120 seconds")
    frames = data.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError("Shot needs 1–14400 measured frames")
    previous = None
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError("Each observation frame must be an object")
        integer(frame.get("index"), "source frame index", 0, 432000)
        if type(frame.get("pts")) is not int:
            raise ValueError("Observation needs integer source frame PTS")
        time = finite(frame.get("time"), "frame time", -1, 3600)
        stop = finite(frame.get("end"), "frame end", time + 1e-9, 3601)
        if time >= end or stop <= start:
            raise ValueError("Observation is outside explicit shot bounds")
        if previous and (frame["index"] != previous["index"] + 1 or abs(time - previous["end"]) > 1e-7):
            raise ValueError("Observations must cover every decoded frame without gaps")
        faces = frame.get("detections")
        if not isinstance(faces, list) or len(faces) > 32:
            raise ValueError("Each frame supports at most 32 measured faces")
        for face in faces:
            if not isinstance(face, dict):
                raise ValueError("Each face detection must be an object")
            _box(face.get("bbox"), width, height)
            finite(face.get("confidence"), "face confidence", .5, 1)
        previous = frame
    if frames[0]["time"] > start + 1e-7 or frames[-1]["end"] < end - 1e-7:
        raise ValueError("Observations do not cover the entire shot")
    return data


def _decoded_frames(path, source, frames, max_width):
    """Stream bounded BGR frames, with display order unchanged and no pre-encode."""
    width = min(source["width"], max_width)
    height = max(2, round(source["height"] * width / source["width"]))
    first, last = frames[0]["index"], frames[-1]["index"]
    filters = f"select='between(n,{first},{last})',scale={width}:{height},format=bgr24"
    command = ["ffmpeg", "-v", "error", "-xerror", "-noautorotate", "-i", str(path), "-map", "0:v:0",
               "-an", "-sn", "-vf", filters, "-fps_mode", "passthrough", "-frames:v", str(len(frames)),
               "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"]
    # stderr goes to a temporary file so a decoder error cannot deadlock a pipe.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            for _ in frames:
                raw = process.stdout.read(width * height * 3)
                if len(raw) != width * height * 3:
                    raise ValueError("Decoder returned fewer pixels than the probed frame timeline")
                yield np.frombuffer(raw, np.uint8).reshape(height, width, 3)
            if process.stdout.read(1) or process.wait(timeout=30):
                raise ValueError("Decoder frame count or exit status differs from probe")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()


def detect_video(path, start, end, *, model=MODEL_PATH, confidence=.8, max_width=960, sheet=None):
    """Detect every actual frame. Frame IDs in the review sheet are source IDs."""
    try:
        import cv2
    except ImportError as error:
        raise ValueError("Install the motion-tracking extra for OpenCV YuNet") from error
    path, model = Path(path), Path(model)
    if sha256(model) != MODEL_SHA256:
        raise ValueError("YuNet model hash does not match the reviewed pinned model")
    finite(confidence, "detector threshold", .5, .99)
    integer(max_width, "detector width", 320, 1920)
    source, timeline = probe_source(path)
    start, end = finite(start, "shot start", 0), finite(end, "shot end", 0)
    if not 0 < end - start <= MAX_SHOT_SECONDS or end > source["video_end"] + 1e-7:
        raise ValueError("Shot must be within video coverage and at most 120 seconds")
    frames = [frame for frame in timeline if frame["time"] < end and frame["end"] > start]
    if not frames or len(frames) > MAX_FRAMES or frames[0]["time"] > start + 1e-7:
        raise ValueError("Shot has missing video coverage or too many frames")
    detector = cv2.FaceDetectorYN.create(str(model), "", (max_width, max_width), confidence, .3, 5000)
    result = []
    pictures = []
    picture_indices = {0, len(frames) // 2, len(frames) - 1}
    decoder = _decoded_frames(path, source, frames, max_width)
    try:
        for position, image in enumerate(decoder):
            frame = frames[position]
            height, width = image.shape[:2]
            detector.setInputSize((width, height))
            _, detected = detector.detect(image)
            faces = []
            for row in [] if detected is None else detected:
                sx, sy = source["width"] / width, source["height"] / height
                x, y, w, h = float(row[0]) * sx, float(row[1]) * sy, float(row[2]) * sx, float(row[3]) * sy
                # Keep the observable face rectangle; margins outside the source
                # are later rejected by the crop planner, never invented.
                left, top = max(0., x), max(0., y)
                right, bottom = min(float(source["width"]), x + w), min(float(source["height"]), y + h)
                if right - left < 2 or bottom - top < 2:
                    continue
                faces.append({"bbox": [left, top, right - left, bottom - top],
                              "confidence": float(row[-1]), "clipped": x < 0 or y < 0 or x + w > source["width"] or y + h > source["height"]})
            faces.sort(key=lambda face: (face["bbox"][0], face["bbox"][1]))
            result.append({**frame, "detections": faces})
            if sheet is not None and position in picture_indices:
                from PIL import Image, ImageDraw
                picture = Image.fromarray(image[:, :, ::-1]).convert("RGB")
                draw = ImageDraw.Draw(picture)
                for number, face in enumerate(faces):
                    x, y, w, h = face["bbox"]
                    x, w, y, h = x / sx, w / sx, y / sy, h / sy
                    draw.rectangle((x, y, x + w, y + h), outline="#66ff66", width=2)
                    draw.text((x, max(0, y - 12)), f"face {number}", fill="#66ff66")
                draw.rectangle((0, 0, width, 22), fill="#151515")
                draw.text((6, 4), f"source frame {frame['index']} | {frame['time']:.6f}s | {len(faces)} detections", fill="white")
                pictures.append(picture)
    finally:
        decoder.close()
    payload = {"schema": OBSERVATION_SCHEMA, "method": "per-frame YuNet face detection", "source": source,
               "model": {"file": MODEL_NAME, "sha256": MODEL_SHA256, "repository_commit": MODEL_COMMIT, "license": "MIT"},
               "settings": {"threshold": confidence, "decode_width": max_width, "opencv_version": cv2.__version__},
               "shot": {"start": start, "end": end}, "frames": result}
    validate_observations(payload)
    if sha256(path) != source["sha256"]:
        raise ValueError("Source changed during detection")
    if sheet is not None:
        from PIL import Image
        sheet = Path(sheet)
        if sheet.exists() or sheet.resolve() in {path.resolve(), model.resolve()}:
            raise ValueError("Review sheet must use a new path")
        sheet.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (pictures[0].width, sum(p.height for p in pictures)), "black")
        offset = 0
        for picture in pictures:
            canvas.paste(picture, (0, offset))
            offset += picture.height
        canvas.save(sheet)
    return payload


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    area = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
    return area / (aw * ah + bw * bh - area)


def select_track(observations, selection):
    """Associate adjacent measured boxes. Loss is sticky; never reacquire silently."""
    validate_observations(observations)
    allowed = {"seed_frame", "seed_detection", "visually_verified", "continuous_shot_verified", "evidence", "speaker_mapping"}
    if not isinstance(selection, dict) or set(selection) - allowed:
        raise ValueError("Selection contains unsupported fields")
    if selection.get("visually_verified") is not True or selection.get("continuous_shot_verified") is not True:
        raise ValueError("Selection requires visual seed review and explicit continuous-shot verification")
    if not isinstance(selection.get("evidence"), str) or not selection["evidence"].strip() or len(selection["evidence"]) > 2000:
        raise ValueError("Selection needs a concise record of the reviewed source view")
    frames = observations["frames"]
    if integer(selection.get("seed_frame"), "seed frame", 0, 432000) != frames[0]["index"]:
        raise ValueError("The reviewed seed must be the first observed frame of this shot")
    seed = integer(selection.get("seed_detection"), "seed detection", 0, 31)
    if seed >= len(frames[0]["detections"]):
        raise ValueError("Reviewed seed detection does not exist")
    mapping = selection.get("speaker_mapping")
    if mapping is not None:
        if not isinstance(mapping, dict) or set(mapping) != {"speaker_id", "method", "evidence"}:
            raise ValueError("Speaker mapping needs speaker_id method evidence")
        if mapping["method"] != "explicit_source_review" or not all(isinstance(mapping[k], str) and 0 < len(mapping[k]) <= 2000 for k in ("speaker_id", "evidence")):
            raise ValueError("Speaker-to-track mapping must come from explicit source review")
    selected = []
    previous = None
    stopped = None
    for frame in frames:
        row = {key: frame[key] for key in ("index", "pts", "time", "end")}
        row.update(state="lost", detection=None, bbox=None, confidence=0.)
        candidates = []
        if previous is None:
            candidates = [(1., seed)]
        elif stopped is None:
            for number, detection in enumerate(frame["detections"]):
                box = detection["bbox"]
                overlap = _overlap(previous, box)
                distance = math.hypot(box[0] + box[2] / 2 - previous[0] - previous[2] / 2,
                                      box[1] + box[3] / 2 - previous[1] - previous[3] / 2) / math.hypot(previous[2], previous[3])
                ratio = box[2] * box[3] / (previous[2] * previous[3])
                if overlap >= .15 and distance <= .65 and .5 <= ratio <= 2:
                    candidates.append((overlap - .15 * distance, number))
            candidates.sort(reverse=True)
        if stopped is None:
            if not candidates:
                stopped = "no_consistent_detection"
            elif len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .2:
                stopped = "ambiguous_spatial_association"
                row["state"] = "ambiguous"
            else:
                match, number = candidates[0]
                face = frame["detections"][number]
                if face.get("clipped"):
                    stopped = "face_detector_box_crosses_source_edge"
                else:
                    previous = face["bbox"]
                    row.update(state="selected", detection=number, bbox=previous,
                               confidence=face["confidence"], association_score=match)
        if stopped is not None:
            row["reason"] = stopped
        selected.append(row)
    return {"schema": TRACK_SCHEMA, "method": "reviewed seed plus adjacent-frame spatial association; no recognition or active-speaker inference",
            "observations": observations, "observations_sha256": canonical_hash(observations),
            "selection": selection, "frames": selected}


def validate_track(track):
    if not isinstance(track, dict) or track.get("schema") != TRACK_SCHEMA:
        raise ValueError("Expected selected face-track v1")
    expected = select_track(track.get("observations"), track.get("selection"))
    if track.get("observations_sha256") != expected["observations_sha256"] or track.get("frames") != expected["frames"]:
        raise ValueError("Selected track differs from its measured observations/selection")
    return track


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    detect = sub.add_parser("detect", help="Measure every frame in a bounded source shot")
    detect.add_argument("source", type=Path)
    detect.add_argument("--start", type=float, required=True)
    detect.add_argument("--end", type=float, required=True)
    detect.add_argument("--model", type=Path, default=MODEL_PATH)
    detect.add_argument("--confidence", type=float, default=.8)
    detect.add_argument("--max-width", type=int, default=960)
    detect.add_argument("--sheet", type=Path)
    detect.add_argument("-o", "--output", type=Path, required=True)
    select = sub.add_parser("select", help="Associate a visually reviewed seed within one verified shot")
    select.add_argument("observations", type=Path)
    select.add_argument("--selection", type=Path, required=True)
    select.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; use a new evidence file")
    if args.action == "detect":
        value = detect_video(args.source, args.start, args.end, model=args.model,
                             confidence=args.confidence, max_width=args.max_width, sheet=args.sheet)
    else:
        value = select_track(read_json(args.observations), read_json(args.selection))
    write_new_json(args.output, value)
    print(json.dumps({"output": str(args.output), "frames": len(value["frames"]),
                      "selected": sum(frame.get("state") == "selected" for frame in value["frames"])}))


if __name__ == "__main__":
    main()
