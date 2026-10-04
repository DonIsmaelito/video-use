"""Advisory caption checks use actual pathological cues and font metrics."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from helpers import caption_readability as report
from helpers.captions import FONT_CANDIDATES


def write(tmp_path, text, suffix='.srt'):
    path=tmp_path/('captions'+suffix);path.write_text(text);return path


def srt(text, start='00:00:13,040', end='00:00:13,660'):
    return f'1\n{start} --> {end}\n{text}\n'


def ass(dialogues, *, format='Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'):
    return ('[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n'
            '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, ScaleX\nStyle: Cap,Inter SemiBold,68,100\n'
            f'[Events]\nFormat: {format}\n'+dialogues+'\n')


@pytest.mark.parametrize('text,start,end', [
    ('Yeah. / And get all\nthe YouTube comments.','00:00:13,040','00:00:13,660'),
    ('You can do that—\nWhich you can do—','00:00:21,720','00:00:22,300'),
])
def test_actual_short_multiword_failures_are_flagged_without_altering_source(tmp_path,text,start,end):
    path=write(tmp_path,srt(text,start,end));original=path.read_bytes()
    value=report.analyze(path);cue=value['cues'][0]
    assert value['status']=='review_needed' and cue['whitespace_words']==8
    assert {'high_text_density','short_multiword_cue'}<=set(cue['flags'])
    assert cue['characters_per_second']>50 and cue['duration']<.7
    assert cue['text']==text and path.read_bytes()==original
    assert value['source']['sha256']==hashlib.sha256(original).hexdigest()
    assert cue['capacity']['status']=='not_measured'


def test_short_single_word_emphasis_is_not_a_blanket_failure(tmp_path):
    value=report.analyze(write(tmp_path,srt('STOP!',end='00:00:13,160')))
    assert value['cues'][0]['duration']==.12
    assert value['cues'][0]['characters_per_second']>24
    assert value['status']=='no_automatic_flags'


def test_long_single_token_still_gets_density_review(tmp_path):
    value=report.analyze(write(tmp_path,srt('pneumonoultramicroscopicsilicovolcanoconiosis')))
    assert 'high_text_density' in value['cues'][0]['flags']


def test_ass_centiseconds_commas_lines_tags_and_layers_are_read(tmp_path):
    body=r'Dialogue: 2,0:00:21.72,0:00:22.30,Cap,,0,0,0,,{\b1}You can do that—\NWhich you can do—'
    value=report.analyze(write(tmp_path,ass(body),'.ass'));cue=value['cues'][0]
    assert (cue['start'],cue['end'],cue['duration'])==(21.72,22.3,.58)
    assert cue['text']=='You can do that—\nWhich you can do—'
    assert cue['layer']=='2' and cue['style']=='Cap'
    assert 'short_multiword_cue' in cue['flags']
    body=r'Dialogue: 0,0:00:00.10,0:00:02.50,Cap,,0,0,0,,Hello, world\hagain.'
    value=report.analyze(write(tmp_path,ass(body),'.ass'))
    assert value['cues'][0]['text']=='Hello, world again.'
    assert value['cues'][0]['start']==.1


def test_ass_format_order_is_respected_and_comments_are_not_dialogue(tmp_path):
    data=ass('Comment: 0,0:00:00.00,0:00:00.20,not dialogue\nDialogue: 0:00:02.00,0:00:00.20,Hi',format='End, Start, Text')
    value=report.analyze(write(tmp_path,data,'.ass'))
    assert value['cue_count']==1 and value['cues'][0]['duration']==1.8


def test_nested_and_unsorted_temporal_overlaps_count_but_touching_endpoints_do_not(tmp_path):
    text='1\n00:00:01,000 --> 00:00:03,000\nMiddle\n\n2\n00:00:00,000 --> 00:00:04,000\nLong\n\n3\n00:00:03,000 --> 00:00:04,000\nTail\n\n4\n00:00:04,000 --> 00:00:05,000\nNext\n'
    value=report.analyze(write(tmp_path,text))
    assert value['overlap_count']==2
    assert {tuple(x['ids']) for x in value['overlaps']}=={(2,1),(2,3)}
    assert value['cues'][3]['flags']==[]


def test_intentional_ass_layers_are_reported_without_deletion(tmp_path):
    data=ass('Dialogue: 0,0:00:00.00,0:00:02.00,Cap,,0,0,0,,First speaker\nDialogue: 1,0:00:01.00,0:00:03.00,Cap,,0,0,0,,Second speaker')
    value=report.analyze(write(tmp_path,data,'.ass'))
    assert value['cue_count']==2 and value['overlap_count']==1
    assert value['overlaps'][0]['layers']==['0','1']


@pytest.fixture
def font_path():
    paths=[Path(__file__).resolve().parents[1]/'website/public/fonts/inter-semibold.ttf',*[Path(p) for p in FONT_CANDIDATES]]
    found=next((p for p in paths if p.is_file()),None)
    if found is None:pytest.skip('No installed test font')
    return found


def test_measured_font_capacity_and_explicit_line_breaks(tmp_path,font_path):
    value=report.analyze(write(tmp_path,srt('One\nTwo\nThree',end='00:00:16,660')),
                         font_path=font_path,font_size=64,max_width=800,max_lines=2)
    cue=value['cues'][0]
    assert cue['capacity']['lines']==['One','Two','Three']
    assert cue['capacity']['exceeds']
    assert 'estimated_line_capacity_exceeded' in cue['flags']
    assert value['layout']['font_sha256']==hashlib.sha256(font_path.read_bytes()).hexdigest()
    value=report.analyze(write(tmp_path,srt('WIDE',end='00:00:16,660')),
                         font_path=font_path,font_size=64,max_width=32,max_lines=2)
    assert value['cues'][0]['capacity']['line_widths_px'][0]>32


def test_plain_text_can_fit_but_ass_inline_formatting_remains_explicit(tmp_path,font_path):
    data=ass(r'Dialogue: 0,0:00:00.00,0:00:02.00,Cap,,0,0,0,,{\fs100\pos(0,0)}Hi')
    value=report.analyze(write(tmp_path,data,'.ass'),font_path=font_path,font_size=64,max_width=800,max_lines=2)
    cue=value['cues'][0]
    assert not cue['capacity']['exceeds']
    assert cue['capacity']['inline_formatting_ignored']
    assert 'inline_formatting_needs_visual_review' in cue['flags']
    assert cue['capacity']['source_ass_style']['fontname']=='Inter SemiBold'


def test_ass_drawing_is_not_counted_as_spoken_text(tmp_path):
    data=ass(r'Dialogue: 0,0:00:00.00,0:00:00.20,Cap,,0,0,0,,{\p1}m 0 0 l 50 50')
    cue=report.analyze(write(tmp_path,data,'.ass'))['cues'][0]
    assert cue['characters_per_second'] is None
    assert cue['characters'] is None and cue['whitespace_words'] is None and cue['kind']=='drawing'
    assert cue['flags']==['drawing_event_needs_manual_review']


def test_bom_crlf_srt_markup_and_actual_line_number(tmp_path):
    text='\ufeff\r\n\r\n1\r\n00:00:00,000 --> 00:00:02,000\r\n<i>A &amp; B</i>\r\n'
    cue=report.analyze(write(tmp_path,text))['cues'][0]
    assert cue['text']=='A & B' and cue['source_line']==3


@pytest.mark.parametrize('text,suffix',[
    ('nonsense','.srt'),('1\n00:00:00,000 --> 00:00:00,000\nZero','.srt'),
    ('1\n00:00:02,000 --> 00:00:01,000\nBackwards','.srt'),
    ('1\n00:60:00,000 --> 01:00:01,000\nBad minute','.srt'),
    ('1\n00:00:00,1 --> 00:00:01,200\nBad fraction','.srt'),
    ('1\n00:00:00,000 --> 00:00:01,000\n','.srt'),
    ('[Events]\nDialogue: 0,0:00:00.00,0:00:01.00,Text','.ass'),
    (ass('Dialogue: 0:00:00.00,Text',format='Start, Text'),'.ass'),
    (ass('Dialogue: x',format='Start, End, Text, Layer'),'.ass'),
    (ass('Dialogue: 0:00:00.00,0:00:01.000,Text',format='Start, End, Text'),'.ass'),
])
def test_malformed_cues_are_never_silently_skipped(tmp_path,text,suffix):
    with pytest.raises(ValueError):report.analyze(write(tmp_path,text,suffix))


@pytest.mark.parametrize('options',[{'max_cps':float('nan')},{'max_cps':0},{'short_seconds':True},
                                    {'long_words':1},{'font_size':64},{'font_size':True,'font_path':'x','max_width':800,'max_lines':2}])
def test_invalid_threshold_or_partial_layout_is_rejected(tmp_path,options):
    with pytest.raises(ValueError):report.analyze(write(tmp_path,srt('Fine')),**options)


def test_overlap_detail_output_is_bounded(tmp_path):
    text='\n'.join(f'{i}\n00:00:00,000 --> 00:00:02,000\nHi\n' for i in range(1,52))
    value=report.analyze(write(tmp_path,text))
    assert value['overlap_count']==51*50//2
    assert len(value['overlaps'])==1000 and value['overlap_details_truncated']


def test_flagged_cli_report_is_successful_and_keeps_all_text(tmp_path):
    path=write(tmp_path,srt('Yeah. / And get all\nthe YouTube comments.'))
    run=subprocess.run([sys.executable,str(Path(report.__file__)),str(path)],capture_output=True,text=True)
    assert run.returncode==0
    value=json.loads(run.stdout)
    assert value['status']=='review_needed' and 'YouTube comments.' in value['cues'][0]['text']
