// Authored visual composition, kept outside the reusable sound analysis helper.
// No tempo grid or score cue data is imported: motion reads measured audio only.
const canvas = document.querySelector('#film');
const ctx = canvas.getContext('2d', { alpha: false, willReadFrequently: true });
const C = { paper: '#f1ebdf', ink: '#202820', blue: '#253ecc', coral: '#f05743', lemon: '#e7df63', lilac: '#a592ca', green: '#839769' };
const TAU = Math.PI * 2;
const clamp = (v, a=0, b=1) => Math.max(a, Math.min(b,v));
const smooth = t => (t=clamp(t), t*t*(3-2*t));

// Compile absolute-time controls once. Audio analysis has its own cadence; the
// renderer may sample in any order and at any frame rate without changing motion.
function compileAudio(data) {
  if (data.schemaVersion !== 1 || !data.frames?.length) throw Error('Unsupported or empty audio analysis');
  const frames = data.frames;
  let energy=0, bassTravel=0, envelope=0;
  const compiled = frames.map((frame,i) => {
    const dt = i ? frame.time-frames[i-1].time : 1/data.frameRate;
    energy += frame.envelope * dt;
    bassTravel += frame.bands.bass * dt;
    envelope += (frame.envelope-envelope)*(1-Math.exp(-dt/.36));
    return { time:frame.time, bass:frame.bands.bass, mid:frame.bands.mid, treble:frame.bands.treble,
      onset:frame.onset, envelope:frame.envelope, slow:envelope, energy, bassTravel };
  });
  const total = energy || 1;
  for (const f of compiled) f.growth = f.energy / total;
  const keys = ['bass','mid','treble','onset','envelope','slow','energy','bassTravel','growth'];
  return time => {
    let lo=0, hi=compiled.length-1;
    if(time<=compiled[0].time) return compiled[0];
    if(time>=compiled[hi].time) return compiled[hi];
    while(hi-lo>1){ const mid=(lo+hi)>>1; if(compiled[mid].time<=time)lo=mid;else hi=mid; }
    const a=compiled[lo],b=compiled[hi],p=(time-a.time)/(b.time-a.time);
    return Object.fromEntries(keys.map(k=>[k,a[k]+(b[k]-a[k])*p]));
  };
}

function ellipse(x,y,rx,ry,color,rotation=0){ctx.fillStyle=color;ctx.beginPath();ctx.ellipse(x,y,rx,ry,rotation,0,TAU);ctx.fill();}
function stroke(path,color=C.ink,width=5){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke(path);}
function stem(x,y,h,bend,width=9,color=C.ink){const p=new Path2D();p.moveTo(x,y);p.bezierCurveTo(x-bend*.3,y-h*.36,x+bend*1.3,y-h*.66,x+bend,y-h);stroke(p,color,width);}

function leaf(x,y,length,width,angle,color,veins=true,curve=0) {
  ctx.save();ctx.translate(x,y);ctx.rotate(angle);
  const p=new Path2D();p.moveTo(0,0);p.bezierCurveTo(-width*1.1,-length*.2,-width*.8+curve,-length*.73,curve,-length);p.bezierCurveTo(width*.9+curve,-length*.79,width*1.08,-length*.25,0,0);ctx.fillStyle=color;ctx.fill(p);
  if(veins){ctx.save();ctx.clip(p);const v=new Path2D();v.moveTo(0,0);v.quadraticCurveTo(curve*.5,-length*.6,curve,-length);for(let i=1;i<9;i++){const f=i/10;v.moveTo(curve*f,-length*f);v.quadraticCurveTo(-width*.58,-length*(f+.09),-width*.95,-length*(f+.22));v.moveTo(curve*f,-length*f);v.quadraticCurveTo(width*.6,-length*(f+.09),width*.95,-length*(f+.22));}stroke(v,C.paper,2.8);ctx.restore();}
  ctx.restore();
}

function rosette(x,y,r,petals,opening,turn,color,inkCenter=true) {
  ctx.save();ctx.translate(x,y);ctx.rotate(turn);
  for(let i=0;i<petals;i++){
    const a=i/petals*TAU;
    ctx.save();ctx.rotate(a);
    const distance=r*(.27+.19*opening),length=r*(.59+.12*opening);
    ellipse(0,-distance,r*(.16+.055*opening),length,color);
    ctx.restore();
  }
  ellipse(0,0,r*.235,r*.235,inkCenter?C.ink:C.paper);
  if(inkCenter){
    for(let i=0;i<24;i++){const a=i*2.39996;const distance=Math.sqrt(i/24)*r*.178;ellipse(Math.cos(a)*distance,Math.sin(a)*distance,2.7,2.7,C.paper);}
  }
  ctx.restore();
}

function fan(x,y,r,opening,turn,color) {
  ctx.save();ctx.translate(x,y);ctx.rotate(turn);
  for(let i=0;i<17;i++){
    const a=(i/16-.5)*Math.PI*(.42+.44*opening);
    ctx.save();ctx.rotate(a);
    const p=new Path2D();p.moveTo(0,0);p.bezierCurveTo(-r*.085,-r*.28,-r*.09,-r*.85,0,-r);p.bezierCurveTo(r*.09,-r*.86,r*.085,-r*.28,0,0);ctx.fillStyle=color;ctx.fill(p);ctx.restore();
  }
  ctx.restore();
}

let sample;
function draw(time) {
  const f=sample(time);
  const growth=.58+.42*smooth(f.growth*2.15);
  const breath=.72+.28*f.slow;
  const sway=Math.sin(f.bassTravel*1.7)*(.017+.043*f.bass);
  ctx.resetTransform();ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.fillStyle=C.paper;ctx.fillRect(0,0,1920,1080);
  // The garden grows from one continuous ground plane, leaving generous sky.
  ctx.save();ctx.translate(960,949);ctx.scale(growth,growth);ctx.translate(-960,-949);
  ctx.save();ctx.translate(820,935);ctx.rotate(sway);ctx.translate(-820,-935);
  // Broad sculptural blue foliage gives the composition its counterweight.
  stem(789,935,610,-115,12);
  leaf(766,819,473,108,-.43-.12*f.bass,C.blue,true,-10);
  leaf(787,865,380,92,.59+.10*f.bass,C.blue,true,20);
  leaf(741,690,320,79,-.8-.12*f.bass,C.blue,true,-18);
  leaf(735,721,302,82,.43+.07*f.bass,C.blue,true,5);
  leaf(678,465,224,68,-.18-.1*f.bass,C.blue,true,9);
  ctx.restore();
  // A fine black stem leads into a coral flower, opening on measured low energy.
  const flowerX=1154+Math.sin(f.bassTravel*.8)*22, flowerY=394+34*(1-f.slow);
  stem(1090,936,936-flowerY,flowerX-1090,10);
  leaf(1107,808,287,56,-.88-.14*f.mid,C.ink,false);
  leaf(1115,705,244,50,.89+.12*f.mid,C.green,true);
  rosette(flowerX,flowerY,(175+39*f.bass)*breath,12,f.bass,Math.sin(f.bassTravel*.65)*.14,C.coral);
  // Percussion unfolds thin fan blades and makes the small satellite petals twitch.
  const fanX=453+18*Math.sin(f.bassTravel*.9),fanY=570;
  stem(462,933,363,fanX-462,7);
  fan(fanX,fanY,245+30*f.treble,.4+.6*f.treble,-.12+.08*f.onset,C.lilac);
  leaf(461,771,208,51,-.88,C.green,true);
  leaf(461,824,186,42,.81,C.ink,false);
  // Dense yellow florets make brightness legible as shape, rather than spectrum bars.
  stem(1433,939,336,28,8);
  const yellowX=1461,yellowY=603;
  rosette(yellowX,yellowY,122+20*f.treble,19,f.treble,-f.bassTravel*.09,C.lemon,false);
  ellipse(yellowX,yellowY,24,24,C.ink);
  leaf(1444,828,245,58,.8+.1*f.bass,C.ink,false);
  leaf(1438,808,228,46,-.64,C.green,true);
  // Repeated but unequal stems create an illustrated understory, not a bar chart.
  const shoots=[{x:296,h:210,r:30,a:-.2},{x:580,h:151,r:34,a:.27},{x:982,h:252,r:39,a:.4},{x:1634,h:287,r:30,a:-.3}];
  for(let i=0;i<shoots.length;i++){
    const q=shoots[i], bend=Math.sin(f.energy+i*1.8)*18;
    stem(q.x,941,q.h,bend,5);
    rosette(q.x+bend,941-q.h,q.r*(.75+.32*f.treble),8,f.treble,q.a+f.onset*.11,i%2?C.coral:C.blue);
    leaf(q.x,921-q.h*.33,80,22,i%2?.9:-.9,C.green,false);
  }
  // Measured onsets create short-lived pollen marks; no playback-state particles.
  ctx.fillStyle=C.ink;
  for(let i=0;i<18;i++){
    const delay=i*.021;
    const past=sample(Math.max(0,time-delay));
    const pulse=past.onset;
    if(pulse<.18)continue;
    const a=i*2.39996+f.bassTravel*.06;
    const distance=235+i*4+20*pulse;
    const x=flowerX+Math.cos(a)*distance,y=flowerY+Math.sin(a)*distance*.77;
    ctx.globalAlpha=clamp(pulse*.63);
    ellipse(x,y,2.5+pulse*2,2.5+pulse*2,C.ink);
  }
  ctx.globalAlpha=1;
  ctx.restore();
  // Sparse roots at a shared baseline visually anchor the arrangement.
  const line=new Path2D();line.moveTo(207,951);line.bezierCurveTo(667,940,1220,960,1713,948);stroke(line,C.ink,3);
  for(const [x,w] of [[445,44],[781,58],[1090,46],[1433,43]])ellipse(960+(x-960)*growth,950,w*growth,5,C.ink);
}

window.motionReady = fetch('./analysis.json').then(response=>{
  if(!response.ok)throw Error(`Audio analysis could not load (${response.status})`);
  return response.json();
}).then(data=>{sample=compileAudio(data);draw(0);});
window.seek = async seconds => {
  if(!Number.isFinite(seconds))throw Error('seek(seconds) requires a finite time');
  await window.motionReady;
  draw(clamp(seconds,0,16));
};
