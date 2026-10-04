"""Check actual retimed encodes, bounds, source protection and process cleanup."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from helpers import silent_retime


pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")


def fixture(path, origin=0, vfr=False):
    frames = np.zeros((72, 48, 64, 3), np.uint8)
    frames[:, :, :, 0] = np.arange(72)[:, None, None] * 3
    frames[:, :, :, 1] = 60
    frames[:, :, :, 2] = 180
    command = ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "64x48", "-r", "24", "-i", "pipe:0"]
    if vfr:
        command += ["-vf", "settb=1/1000,setpts='floor(N/2)*120+mod(N,2)*40'", "-enc_time_base", "1/1000"]
    command += ["-fps_mode", "passthrough", "-c:v", "ffv1", "-pix_fmt", "bgr0", "-output_ts_offset", str(origin), str(path)]
    subprocess.run(command, input=frames.tobytes(), capture_output=True, check=True)


def red_indices(path):
    pixels = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-an", "-fps_mode", "passthrough",
                                      "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    frames = np.frombuffer(pixels, np.uint8).reshape(-1, 48, 64, 3)
    return np.rint(frames[:, :, :, 0].mean(axis=(1, 2)) / 3).astype(int)


@pytest.mark.parametrize("speed,end", [(.5,1.4),(1.5,1.9),(2.,1.6)])
@pytest.mark.parametrize("origin,vfr", [(0,False),(2,False),(0,True)])
def test_real_encode_repeats_or_drops_original_frames_at_declared_speed(tmp_path, speed, end, origin, vfr):
    source, output = tmp_path / "source.mkv", tmp_path / "replay.mp4"
    fixture(source, origin, vfr)
    digest = silent_retime.sha256(source)
    result = silent_retime.retime(source, output, start=.4, end=end, speed=speed, source_sha256=digest)
    _, source_frames = silent_retime.probe_source(source)
    times = np.array([f["time"] for f in source_frames])
    actual = red_indices(output)
    expected = np.searchsorted(times, .4 + np.arange(len(actual)) / 30 * speed, side="right") - 1
    assert len(actual) == round((end-.4)/speed*30) == result["output"]["frames"]
    assert np.max(np.abs(actual-expected)) <= 1, (actual.tolist(),expected.tolist())
    assert np.all(np.diff(actual) >= 0)
    assert actual[0] >= result["source_first_frame"]["index"]-1
    assert actual[-1] <= result["source_last_frame"]["index"]+1
    assert result["output"]["audio_streams"] == 0
    assert silent_retime.sha256(source) == digest
    assert not list(tmp_path.glob('.silent-retime-*'))


@pytest.mark.parametrize("changes", [dict(speed=0),dict(speed=True),dict(speed=float('nan')),dict(end=.1),
                                     dict(end=121),dict(fps=2.5),dict(fps=True),dict(end=1.401)])
def test_bad_contract_is_rejected_before_reading_source(tmp_path, changes):
    options=dict(start=.4,end=1.4,speed=.5,fps=30);options.update(changes)
    with pytest.raises(ValueError):silent_retime.retime(tmp_path/'absent.mp4',tmp_path/'out.mp4',**options)
    assert not (tmp_path/'out.mp4').exists()


def test_hash_and_timeline_coverage_are_checked(tmp_path):
    source=tmp_path/'source.mkv';fixture(source)
    with pytest.raises(ValueError,match='SHA256'):
        silent_retime.retime(source,tmp_path/'bad.mp4',start=0,end=1,speed=1,source_sha256='0'*64)
    with pytest.raises(ValueError,match='outside'):
        silent_retime.retime(source,tmp_path/'long.mp4',start=0,end=4,speed=1)


def test_existing_outputs_and_source_aliases_are_never_overwritten(tmp_path):
    source=tmp_path/'source.mkv';fixture(source)
    output=tmp_path/'replay.mp4';output.write_bytes(b'previous reviewed output')
    with pytest.raises(FileExistsError):silent_retime.retime(source,output,start=0,end=1,speed=1)
    assert output.read_bytes()==b'previous reviewed output'
    alias=tmp_path/'alias.mp4';alias.symlink_to(source)
    digest=silent_retime.sha256(source)
    with pytest.raises(FileExistsError):silent_retime.retime(source,alias,start=0,end=1,speed=1)
    assert silent_retime.sha256(source)==digest


def test_real_audio_stream_is_rejected_instead_of_discarded(tmp_path):
    source=tmp_path/'with-audio.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=64x48:r=30:d=1',
                    '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac',str(source)],
                   check=True,capture_output=True)
    with pytest.raises(ValueError,match='silent'):
        silent_retime.retime(source,tmp_path/'out.mp4',start=0,end=.5,speed=.5)


def test_encoder_failure_removes_only_its_temporary_files(tmp_path,monkeypatch):
    source=tmp_path/'source.mkv';fixture(source);digest=silent_retime.sha256(source)
    original=subprocess.run
    def run(command,**kwargs):
        if command[0]=='ffmpeg':raise subprocess.TimeoutExpired(command,600)
        return original(command,**kwargs)
    monkeypatch.setattr(silent_retime.subprocess,'run',run)
    with pytest.raises(subprocess.TimeoutExpired):
        silent_retime.retime(source,tmp_path/'out.mp4',start=0,end=1,speed=1)
    assert not (tmp_path/'out.mp4').exists()
    assert not list(tmp_path.glob('.silent-retime-*'))
    assert silent_retime.sha256(source)==digest


def test_source_mutation_prevents_final_install(tmp_path,monkeypatch):
    source=tmp_path/'source.mkv';fixture(source)
    original=subprocess.run
    def run(command,**kwargs):
        result=original(command,**kwargs)
        if command[0]=='ffmpeg':
            with source.open('ab') as f:f.write(b'changed')
        return result
    monkeypatch.setattr(silent_retime.subprocess,'run',run)
    with pytest.raises(ValueError,match='changed'):
        silent_retime.retime(source,tmp_path/'out.mp4',start=0,end=1,speed=1)
    assert not (tmp_path/'out.mp4').exists()
    assert not list(tmp_path.glob('.silent-retime-*'))
