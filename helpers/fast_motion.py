#!/usr/bin/env python3
"""Jev-only motion design: prompt -> closed-set design choices -> parametrized scene -> short render.

No language model writes anything. Jev (a 0.2 s text classifier) answers a handful of typed questions
about the prompt: which instant scene fits, which palette, what pace, which motion style and ending.
The words on screen, when a scene needs them, come from the prompt itself by rule (a quoted phrase,
else the prompt's own emphasised words). The scene is a parametrized template, rendered with the
repository's deterministic browser renderer, then checked by the motion gate.

  python helpers/fast_motion.py "Make the word MELT drop in and bounce, warm and playful" --out edit/fast_motion

Prints per-stage seconds and writes <out>/<slug>/{decisions.json,index.html,render.mp4,report.json}.
Budget target: under 20 s for a 4-8 s piece at 1280x720 30 fps on this machine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from jev import Jev, choice, noul  # noqa: E402

RECIPES = REPO / "skills" / "motion-design" / "library" / "recipes"
EXAMPLES = REPO / "skills" / "motion-design" / "examples"
RUNTIME = REPO / "skills" / "motion-design" / "runtime"
CHROME = os.environ.get("CHROME_PATH") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCENES = {
    "word-pop": "One or two words as the hero: they drop or slide into an empty field, land with a squash or a decisive stop, hold, and an accent line underlines them. Best for a named word, a slogan, a title, a mood word.",
    "kinetic-type": "A typographic film: several short thoughts crowd the frame as ribbons, build pressure, then resolve into one clear phrase. Best for feelings, mental states, lists of competing ideas, 'too many' themes.",
    "ink-octopus": "A single ink droplet on paper grows into an eight-arm octopus that curls and jets. Best for ink, sea creatures, organic growth, blue-on-paper illustration.",
    "checker-zebra": "A checkerboard peels itself into a striped galloping zebra on a flat colour field. Best for pattern-to-animal transformations, stripes, playful flat graphics.",
    "paper-koi": "A scored red paper square unfolds into a koi that swims through ink ripples. Best for origami, fish, paper craft, calm Japanese-inspired motion.",
}
PALETTES = {
    "ivory-ink-acid": {"paper": "#f1f0e6", "ink": "#171815", "accent": "#dfff00", "desc": "warm ivory field, near-black type, one acid yellow accent (editorial, graphic)"},
    "midnight-neon": {"paper": "#0b0f1f", "ink": "#f4f6ff", "accent": "#5cf2c3", "desc": "deep midnight blue field, white type, mint neon accent (tech, night, energetic)"},
    "paper-cobalt": {"paper": "#f5edda", "ink": "#172994", "accent": "#e8542f", "desc": "aged paper field, cobalt ink, a coral accent (illustration, ink, craft)"},
    "cream-vermilion": {"paper": "#fff0d4", "ink": "#a82221", "accent": "#ef5136", "desc": "cream field, deep red and vermilion (warm, bold, Japanese paper)"},
    "forest-lime": {"paper": "#0f2a1f", "ink": "#eaf5ea", "accent": "#d9ed48", "desc": "dark forest green field, pale type, lime accent (natural, fresh, playful)"},
    "charcoal-coral": {"paper": "#2a2623", "ink": "#f6efe6", "accent": "#ff6f59", "desc": "charcoal field, warm off-white type, coral accent (cinematic, warm, confident)"},
}
PACE = {"calm": "slow, spacious, long holds (about 8 s)", "brisk": "lively and clear, medium holds (about 6 s)", "explosive": "fast, punchy, short (about 4.5 s)"}
PACE_S = {"calm": 8.0, "brisk": 6.0, "explosive": 4.5}
MOTION = {"spring": "elastic overshoot and squash on arrival", "decisive": "fast ease-out stop with no bounce", "drift": "soft fade and slow drift, atmospheric"}
ENDING = {"hold": "settle and hold the final frame", "exit": "leave the frame at the end", "loop": "return to the starting state so it loops"}


def extract_words(prompt: str, limit: int = 2) -> list[str]:
    q = re.findall(r"[\"“']([^\"”']{1,40})[\"”']", prompt)
    if q:
        return [w.strip() for w in q[0].split() if w.strip()][:max(limit, 3)]
    caps = re.findall(r"\b([A-Z][A-Z]{1,14})\b", prompt)
    if caps:
        return caps[:2]
    words = [w for w in re.findall(r"[A-Za-z']+", prompt) if len(w) > 3 and w.lower() not in {"make", "create", "video", "motion", "design", "animation", "short", "with", "that", "into", "from", "then", "this", "about", "word", "words"}]
    return [w.upper() for w in words[:limit]] or ["HELLO"]


def word_pop_html(words: list[str], pal: dict, motion: str, ending: str, duration: float) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{' '.join(words)}</title>
<style>html,body{{margin:0;overflow:hidden;background:{pal['paper']};width:100vw;height:100vh}}canvas{{display:block;width:100vw;height:100vh}}</style></head><body>
<canvas id="film" width="1920" height="1080"></canvas>
<script>
const CFG={json.dumps({"words": words, "paper": pal["paper"], "ink": pal["ink"], "accent": pal["accent"], "motion": motion, "ending": ending, "duration": duration})};
const c=document.getElementById('film'),ctx=c.getContext('2d',{{alpha:false,willReadFrequently:true}});const W=1920,H=1080,D=CFG.duration;
const clamp=v=>Math.max(0,Math.min(1,v));
const outCubic=x=>1-Math.pow(1-clamp(x),3);const inCubic=x=>Math.pow(clamp(x),3);
const spring=x=>{{x=clamp(x);return 1-Math.exp(-6.5*x)*Math.cos(9*x)}};
const smooth=x=>{{x=clamp(x);return x*x*(3-2*x)}};
function fit(text,maxW,maxS){{let s=maxS;ctx.font=`800 ${{s}}px Helvetica, Arial, sans-serif`;while(ctx.measureText(text).width>maxW&&s>40){{s-=8;ctx.font=`800 ${{s}}px Helvetica, Arial, sans-serif`}}return s}}
function pose(t){{t=Math.max(0,Math.min(D,t));ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle=CFG.paper;ctx.fillRect(0,0,W,H);
  const n=CFG.words.length,enterDur=CFG.motion==='drift'?1.4:0.9,exitStart=D-1.1;
  CFG.words.forEach((word,i)=>{{
    const start=0.15+i*0.35,p=clamp((t-start)/enterDur);
    const size=fit(word,W*0.82,n>1?260:380);let y=H/2+(n>1?(i-(n-1)/2)*size*1.18:0),x=W/2,sx=1,sy=1,alpha=1;
    if(CFG.motion==='spring'){{const e=spring(p);y+= (1-e)*-700;const sq=Math.max(0,1-Math.abs(e-1)*4);sx=1+0.12*sq*Math.sin(Math.PI*clamp((p-0.55)/0.45));sy=1-0.12*sq*Math.sin(Math.PI*clamp((p-0.55)/0.45));}}
    else if(CFG.motion==='decisive'){{const e=outCubic(p);x+=(1-e)*-1400;}}
    else{{alpha=smooth(p);y+=(1-smooth(p))*60;}}
    if(t>exitStart){{const q=clamp((t-exitStart)/1.0);
      if(CFG.ending==='exit'){{y-=inCubic(q)*900;}}
      else if(CFG.ending==='loop'){{if(CFG.motion==='drift')alpha*=1-smooth(q);else y+=inCubic(q)*(CFG.motion==='spring'?-700:0),x+=inCubic(q)*(CFG.motion==='decisive'?-1400:0);}}
    }}
    ctx.save();ctx.translate(x,y);ctx.scale(sx,sy);ctx.globalAlpha=alpha;ctx.fillStyle=CFG.ink;ctx.font=`800 ${{size}}px Helvetica, Arial, sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(word,0,0);ctx.restore();
  }});
  const lineStart=0.15+(n-1)*0.35+enterDur*0.7,lp=outCubic((t-lineStart)/0.6);
  if(lp>0){{let hide=0;if(t>exitStart&&CFG.ending!=='hold')hide=clamp((t-exitStart)/0.6);ctx.fillStyle=CFG.accent;const w=W*0.42*lp*(1-hide);ctx.fillRect(W/2-w/2,H/2+(n>1?(n-1)/2*260*1.18:0)+230,w,22);}}
}}
window.motionReady=Promise.resolve();window.seek=async t=>pose(t);pose(0);
</script></body></html>"""


def build_scene(scene: str, dest: Path, words: list[str], pal: dict, motion: str, ending: str, duration: float) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    if scene == "word-pop":
        (dest / "index.html").write_text(word_pop_html(words, pal, motion, ending, duration))
        return dest / "index.html"
    if scene == "kinetic-type":
        src = EXAMPLES / "kinetic-type"
        for item in ("scene.mjs", "lib", "assets", "index.html"):
            s = src / item
            (shutil.copytree(s, dest / item, dirs_exist_ok=True) if s.is_dir() else shutil.copy2(s, dest / item))
        content = json.loads((src / "content.json").read_text())
        w = [x.upper() for x in words]
        content["opening"] = (w + ["THING", "MORE"])[:3]
        if len(w) > 3:
            content["interruptions"] = (w[3:] + content["interruptions"])[:8]
        content["pressure"] = " ".join(w[:2]) if w else content["pressure"]
        content["resolution"] = [words[0].lower(), (words[1].lower() if len(words) > 1 else "clear.")]
        content["palette"] = {"paper": pal["paper"], "ink": pal["ink"], "accent": pal["accent"]}
        (dest / "content.json").write_text(json.dumps(content))
        html = (dest / "index.html").read_text()
        html = html.replace("</html>", f"<script type=\"module\">const D={duration};const wait=()=>new Promise(r=>{{const i=setInterval(()=>{{if(window.seek&&!window.__wrapped){{clearInterval(i);r()}}}},5)}});await wait();const orig=window.seek;window.__wrapped=1;window.seek=t=>orig(t*16/D);</script></html>")
        (dest / "index.html").write_text(html)
        return dest / "index.html"
    # canvas recipes: copy the module and the demo caller, then re-time the demo's 8 s pose and recolour it
    name = scene
    shutil.copy2(RECIPES / f"{name}.mjs", dest / f"{name}.mjs")
    html = (RECIPES / f"{name}-demo.html").read_text()
    scale = 8.0 / duration
    html = html.replace("window.seek=async t=>pose(t)", f"window.seek=async t=>pose(t*{scale:.4f})").replace("window.seek=pose", f"window.seek=t=>pose(t*{scale:.4f})")
    html = html.replace("window.seek=async t=>{await window.motionReady;pose(t)}", f"window.seek=async t=>{{await window.motionReady;pose(t*{scale:.4f})}}")
    if name == "ink-octopus":
        html = html.replace("createInkOctopus()", f"createInkOctopus({{ink:'{pal['ink']}',paper:'{pal['paper']}'}})").replace("#f5edda", pal["paper"])
    elif name == "checker-zebra":
        html = html.replace("createCheckerZebra()", f"createCheckerZebra({{ink:'{pal['ink']}',ivory:'{pal['paper']}'}})").replace("#d9ed48", pal["accent"])
    elif name == "paper-koi":
        html = html.replace("createPaperKoi()", f"createPaperKoi({{red:'{pal['ink']}',vermilion:'{pal['accent']}'}})").replace("#f4eddf", pal["paper"]).replace("#f3ecdc", pal["paper"])
    html = html.replace("width:1920px;height:1080px;", "width:100vw;height:100vh;")
    html = html.replace("</head>", "<style>canvas{width:100vw!important;height:100vh!important;display:block}</style></head>", 1)
    (dest / "index.html").write_text(html)
    return dest / "index.html"


def run_pipeline(prompt: str, out: str | Path, *, width: int = 1280, height: int = 720, fps: int = 30, duration: float | None = None, scene_override: str | None = None, gate: bool = True, on_event=None) -> dict:
    """Run the Jev-only path and report every stage through on_event(dict). Returns the report."""
    t0 = time.perf_counter()
    stages: dict = {}

    def emit(stage: str, msg: str, **data):
        ev = {"t": round(time.perf_counter() - t0, 2), "stage": stage, "msg": msg, **data}
        if on_event:
            on_event(ev)
        return ev

    emit("start", f"prompt: {prompt}")
    jev = Jev(log_path=Path(out) / "jev_decisions.jsonl")
    state = {"prompt": prompt, "task": "Choose how to realise this motion-design prompt with one of the instant scenes and a fixed set of design controls."}
    qs = {
        "scene": choice("Which instant scene best realises the prompt?", SCENES),
        "palette": choice("Which colour palette fits the prompt's mood and subject?", {k: v["desc"] for k, v in PALETTES.items()}),
        "pace": choice("What pace does the prompt call for?", PACE),
        "motion": choice("Which arrival motion fits the prompt's feeling?", MOTION),
        "ending": choice("How should the piece end?", ENDING),
        "dark": noul("The prompt calls for a dark background."),
    }
    emit("jev", f"asking Jev six questions in one request ({jev.route} route)", questions=list(qs))
    r = jev.ask(state, qs, tag="fast_motion")
    stages["jev_s"] = round(time.perf_counter() - t0, 2)
    for key in ("scene", "palette", "pace", "motion", "ending"):
        a = r.choice(key)
        top = sorted(a.probabilities.items(), key=lambda kv: -kv[1])[:3]
        emit("jev", f"{key}: {a.choice}  (p={a.p_choice:.2f}, margin={a.choice_margin:.2f})", question=key, choice=a.choice, p=round(a.p_choice, 2), margin=round(a.choice_margin, 2), top=[(k, round(v, 2)) for k, v in top])
    dark = r.noul("dark").noul
    emit("jev", f"dark background: p={dark:.2f}", question="dark", p=round(dark, 2))
    emit("jev", f"Jev answered in {r.latency_ms:.0f} ms ({r.input_tokens} input tokens)", latency_ms=round(r.latency_ms), model=r.model)
    sc = r.choice("scene")
    scene = scene_override or (sc.choice if sc.passes(0.35, 0.08) else "word-pop")
    if not scene_override and scene != sc.choice:
        emit("jev", f"scene gate not met (p={sc.p_choice:.2f}, margin={sc.choice_margin:.2f}); falling back to word-pop")
    palette = r.choice("palette").choice; pace = r.choice("pace").choice; motion = r.choice("motion").choice; ending = r.choice("ending").choice
    if dark >= 0.6 and palette in ("ivory-ink-acid", "paper-cobalt", "cream-vermilion"):
        emit("jev", f"dark background requested; swapping {palette} for midnight-neon")
        palette = "midnight-neon"
    dur = duration or PACE_S[pace]
    words = extract_words(prompt, limit=5 if scene == "kinetic-type" else 2)
    decisions = {"prompt": prompt, "scene": scene, "scene_p": round(sc.p_choice, 2), "scene_margin": round(sc.choice_margin, 2), "scene_probs": {k: round(v, 2) for k, v in sc.probabilities.items()},
                 "palette": palette, "pace": pace, "motion": motion, "ending": ending, "dark_p": round(dark, 2), "duration_s": dur, "words": words, "jev_latency_ms": round(r.latency_ms)}
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:40].strip("-") or "piece"
    dest = Path(out) / slug
    t1 = time.perf_counter()
    entry = build_scene(scene, dest, words, PALETTES[palette], motion, ending, dur)
    stages["build_s"] = round(time.perf_counter() - t1, 2)
    emit("build", f"scene {scene} written with words {words}, palette {palette}, {dur:g} s ({stages['build_s']} s)", path=str(entry), decisions=decisions)
    (dest / "decisions.json").write_text(json.dumps(decisions, indent=1))
    t2 = time.perf_counter()
    out_mp4 = dest / "render.mp4"
    total_frames = int(round(dur * fps))
    cmd = ["node", str(HERE / "motion_render.mjs"), str(entry), "-o", str(out_mp4), "--duration", str(dur), "--width", str(width), "--height", str(height), "--fps", str(fps), "--deps", str(RUNTIME), "--chrome", CHROME, "--crf", "22", "--preset", "veryfast", "--overwrite"]
    emit("render", f"rendering {total_frames} frames at {width}x{height} {fps} fps", frames=total_frames)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    last_line = ""
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.strip()
        if not line:
            continue
        last_line = line
        m = re.match(r"Frame (\d+)/(\d+)", line)
        if m:
            emit("render", line, frame=int(m.group(1)), frames=int(m.group(2)))
    proc.wait()
    stages["render_s"] = round(time.perf_counter() - t2, 2)
    if proc.returncode != 0:
        emit("error", f"render failed: {last_line[-300:]}")
        raise RuntimeError(f"render failed for scene {scene}: {last_line[-300:]}")
    emit("render", f"encoded {out_mp4.name} in {stages['render_s']} s", path=str(out_mp4))
    gate_result = None
    if gate:
        t3 = time.perf_counter()
        g = subprocess.run([sys.executable, str(HERE / "motion_gate.py"), str(out_mp4), "--width", str(width), "--height", str(height), "--fps", str(fps), "--min-s", str(dur - 0.2), "--max-s", str(dur + 0.5), "--silent", "--out", str(dest / "verify")], capture_output=True, text=True)
        stages["gate_s"] = round(time.perf_counter() - t3, 2)
        first = (g.stdout.strip().splitlines() or [""])[0]
        gate_result = {"verdict": "ship" if g.returncode == 0 else "fix", "line": first[:300]}
        try:
            gate_result["report"] = json.loads((dest / "verify" / "motion_gate.json").read_text())
        except Exception:  # noqa: BLE001
            pass
        emit("gate", f"motion gate: {gate_result['verdict'].upper()} ({stages['gate_s']} s) {first[:160]}", verdict=gate_result["verdict"], p_ready=(gate_result.get("report") or {}).get("jev_p_ready"))
    stages["total_s"] = round(time.perf_counter() - t0, 2)
    report = {"decisions": decisions, "stages": stages, "gate": gate_result, "output": str(out_mp4)}
    (dest / "report.json").write_text(json.dumps(report, indent=1))
    emit("done", f"{stages['total_s']} s total", report=report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt"); ap.add_argument("--out", default="edit/fast_motion"); ap.add_argument("--width", type=int, default=1280); ap.add_argument("--height", type=int, default=720); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=None, help="override the pace-derived duration"); ap.add_argument("--scene", default=None, help="override Jev's scene choice"); ap.add_argument("--no-gate", action="store_true"); ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    report = run_pipeline(a.prompt, a.out, width=a.width, height=a.height, fps=a.fps, duration=a.duration, scene_override=a.scene, gate=not a.no_gate, on_event=(lambda e: print(f"[{e['t']:6.2f}s] {e['stage']:6s} {e['msg']}")) if a.verbose else None)
    d, s = report["decisions"], report["stages"]
    g = report["gate"]
    print(f"{s['total_s']:5.1f}s total | jev {s['jev_s']}s build {s['build_s']}s render {s['render_s']}s gate {s.get('gate_s')}s | {d['scene']} {d['palette']} {d['pace']} {d['motion']} {d['ending']} {d['duration_s']}s words={d['words']} | gate={g['verdict'] if g else '-'} | {report['output']}")


if __name__ == "__main__":
    main()
