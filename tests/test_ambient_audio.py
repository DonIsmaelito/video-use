"""Actual PCM checks for the original tonal-bed helper and its bounded input."""
import hashlib
import json
import wave

import numpy as np
import pytest

from helpers import ambient_audio


def score():
    return {"version": 1, "duration": 2, "sample_rate": 16000, "seed": 4,
            "fade_in": .1, "fade_out": .2, "headroom_db": 3,
            "tones": [{"frequency": 220, "gain": .1, "pan": -.25}],
            "pulses": [{"start": .4, "duration": .8, "frequency": 73, "gain": .2, "pan": .5}]}


@pytest.mark.parametrize("rate,duration", [(8000,.03125),(44100,1.12345),(48000,2),(96000,.5)])
def test_exact_sample_count_and_silent_endpoints(rate, duration):
    value = score()
    value.update(sample_rate=rate, duration=duration, pulses=[], fade_in=duration/8, fade_out=duration/8)
    pcm = ambient_audio.synthesize(value)
    assert pcm.shape == (ambient_audio.sample_index(duration, rate), 2)
    assert pcm.dtype == np.float64 and np.isfinite(pcm).all()
    assert np.array_equal(pcm[[0,-1]], np.zeros((2,2)))
    assert 0 < np.max(np.abs(pcm)) < 10 ** (-value['headroom_db']/20)


def test_seed_is_deterministic_and_changes_phase():
    a = ambient_audio.synthesize(score())
    assert np.array_equal(a, ambient_audio.synthesize(score()))
    changed = score();changed['seed'] += 1
    assert not np.array_equal(a, ambient_audio.synthesize(changed))


@pytest.mark.parametrize("pan,active", [(-1,0),(1,1)])
def test_pan_and_actual_oscillator_frequency(pan, active):
    value = score();value['pulses']=[];value['tones']=[{'frequency':220,'gain':.1,'pan':pan}]
    pcm = ambient_audio.synthesize(value)
    assert not np.any(pcm[:,1-active])
    section = pcm[4000:28000,active]
    frequency = np.fft.rfftfreq(len(section),1/value['sample_rate'])[np.argmax(np.abs(np.fft.rfft(section)))]
    assert frequency == pytest.approx(220,abs=.7)


def test_pulses_do_not_leak_outside_their_authored_intervals():
    value = score();value['tones']=[]
    pcm = ambient_audio.synthesize(value)
    first,last=6400,19200
    assert not np.any(pcm[:first+1]) and not np.any(pcm[last-1:])
    assert np.max(np.abs(pcm[first:last])) > .05


def test_full_overlap_is_rejected_instead_of_clipped_or_normalized():
    value = score();value['tones']=[]
    value['pulses']=[{'start':.2,'duration':1.5,'frequency':220,'gain':1,'pan':-1}]*16
    with pytest.raises(ValueError,match='headroom'):
        ambient_audio.synthesize(value)


@pytest.mark.parametrize('field,value', [
    ('version',True),('version',2),('duration',float('nan')),('duration',121),('duration',0),
    ('sample_rate',True),('sample_rate',7999),('sample_rate',96001),('sample_rate',48000.5),
    ('seed',-1),('seed',2**64),('seed',True),('headroom_db',float('inf')),
    ('fade_in',0),('fade_out',2),('fade_in',float('nan')),('unknown',0),
    ('tones',{}),('pulses',{}),('tones',[{'frequency':220,'gain':.1}]*17),
    ('pulses',[{'start':0,'duration':1,'frequency':220,'gain':.1}]*513),
])
def test_invalid_score_is_rejected_before_allocation(field, value, monkeypatch):
    config = score();config[field]=value
    monkeypatch.setattr(ambient_audio.np,'zeros',lambda *a,**k:pytest.fail('Allocated before validation'))
    with pytest.raises(ValueError):ambient_audio.synthesize(config)


@pytest.mark.parametrize('kind,change', [
    ('tones',{'frequency':19}),('tones',{'frequency':7201}),('tones',{'frequency':True}),
    ('tones',{'gain':-1}),('tones',{'gain':2}),('tones',{'gain':float('nan')}),
    ('tones',{'pan':1.1}),('tones',{'path':'sample.wav'}),
    ('pulses',{'start':-.1}),('pulses',{'start':1.5}),('pulses',{'duration':0}),
    ('pulses',{'duration':1/16000}),('pulses',{'duration':float('inf')}),
])
def test_invalid_event_is_rejected(kind, change):
    config=score();config[kind][0].update(change)
    with pytest.raises(ValueError):ambient_audio.synthesize(config)


def test_empty_score_and_excessive_work_fail_before_allocation(monkeypatch):
    empty=score();empty.update(tones=[],pulses=[])
    with pytest.raises(ValueError):ambient_audio.synthesize(empty)
    large=score();large.update(duration=120,sample_rate=96000,tones=[{'frequency':220,'gain':.01}]*9,pulses=[])
    monkeypatch.setattr(ambient_audio.np,'zeros',lambda *a,**k:pytest.fail('Allocated before work bound'))
    with pytest.raises(ValueError,match='work'):ambient_audio.synthesize(large)


def test_real_wav_is_exact_pcm_and_report_is_bound_to_inputs(tmp_path):
    config=score();source=tmp_path/'score.json';source.write_text(json.dumps(config))
    output=tmp_path/'bed.wav';report=ambient_audio.render(source,output)
    with wave.open(str(output),'rb') as stream:
        assert (stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes())==(2,2,16000,32000)
        actual=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').reshape(-1,2)
    expected=np.rint(ambient_audio.synthesize(config)*32767).astype('<i2')
    assert np.array_equal(actual,expected)
    assert not np.any(actual[[0,-1]])
    assert report['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert report['sha256']==hashlib.sha256(output.read_bytes()).hexdigest()
    assert 'not recorded' in report['method']
    assert not list(tmp_path.glob('.ambient-audio-*'))


def test_protect_existing_output_source_and_symlink(tmp_path):
    source=tmp_path/'score.json';source.write_text(json.dumps(score()));original=source.read_bytes()
    output=tmp_path/'bed.wav';output.write_bytes(b'previous')
    with pytest.raises(FileExistsError):ambient_audio.render(source,output)
    assert output.read_bytes()==b'previous'
    with pytest.raises(ValueError):ambient_audio.render(source,source)
    alias=tmp_path/'alias.wav';alias.symlink_to(source)
    with pytest.raises(ValueError):ambient_audio.render(source,alias)
    missing=tmp_path/'missing.wav';missing.symlink_to(tmp_path/'absent')
    with pytest.raises(FileExistsError):ambient_audio.render(source,missing)
    assert source.read_bytes()==original


def test_failed_writer_and_changed_score_leave_no_output(tmp_path,monkeypatch):
    source=tmp_path/'score.json';source.write_text(json.dumps(score()))
    output=tmp_path/'bed.wav'
    original=ambient_audio.write_pcm
    def interrupted(*a,**k):raise OSError('interrupted write')
    monkeypatch.setattr(ambient_audio,'write_pcm',interrupted)
    with pytest.raises(OSError):ambient_audio.render(source,output)
    assert not output.exists() and not list(tmp_path.glob('.ambient-audio-*'))
    def changed(*a,**k):
        report=original(*a,**k);source.write_text('{}');return report
    monkeypatch.setattr(ambient_audio,'write_pcm',changed)
    with pytest.raises(ValueError,match='changed'):ambient_audio.render(source,output)
    assert not output.exists() and not list(tmp_path.glob('.ambient-audio-*'))


def test_concurrent_output_is_preserved(tmp_path,monkeypatch):
    source=tmp_path/'score.json';source.write_text(json.dumps(score()))
    output=tmp_path/'bed.wav';original=ambient_audio._install_new
    def concurrent(path,complete):
        path.write_bytes(b'other producer');original(path,complete)
    monkeypatch.setattr(ambient_audio,'_install_new',concurrent)
    with pytest.raises(FileExistsError):ambient_audio.render(source,output)
    assert output.read_bytes()==b'other producer'
    assert not list(tmp_path.glob('.ambient-audio-*'))


def test_oversized_manifest_is_rejected(tmp_path):
    source=tmp_path/'score.json';source.write_bytes(b' ' * 1_048_577)
    with pytest.raises(ValueError,match='1 MiB'):ambient_audio.render(source,tmp_path/'out.wav')
