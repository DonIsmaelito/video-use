/** Trusted renderer for validated scene data; no expressions, HTML, or remote assets. */
import {keyframes, fitText, matrix2D, compose2D} from './motion.mjs';

const NUMBERS = ['x','y','w','h','size','stroke_width','radius','opacity','rotation','scale','start','end','cycles','phase'];
const radians = degrees => degrees * Math.PI / 180;
const families = {sans: '"DejaVu Sans", "Noto Sans", sans-serif', bold: '"DejaVu Sans", "Noto Sans", sans-serif', serif: '"DejaVu Serif", serif'};

export function sampleMark(mark) {
  let pose = Object.fromEntries(NUMBERS.map(key => [key, mark[key]]));
  const keys = [{time:0, value:{...pose}, ease:'inOutCubic'}];
  for (const key of mark.keyframes) {
    for (const prop of NUMBERS) if (Object.hasOwn(key, prop)) pose[prop] = key[prop];
    const frame = {time:key.time, value:{...pose}, ease:key.ease};
    if (key.time === 0) keys[0] = frame;
    else keys.push(frame);
  }
  return keyframes(keys);
}

export function compileScene(scene) {
  const marks = new Map(scene.marks.map(mark => [mark.id, {...mark, sample:sampleMark(mark)}]));
  return time => {
    const resolved = new Map();
    const resolve = id => {
      if (resolved.has(id)) return resolved.get(id);
      const mark = marks.get(id), pose = mark.sample(Math.max(0, Math.min(scene.duration,time)));
      let matrix = matrix2D({x:pose.x,y:pose.y,rotation:radians(pose.rotation),scaleX:pose.scale,scaleY:pose.scale});
      let opacity = pose.opacity;
      if (mark.parent) {
        const parent = resolve(mark.parent);
        matrix = compose2D(parent.matrix,matrix);
        opacity *= parent.opacity;
      }
      const result = {mark,pose,matrix,opacity:Math.max(0,Math.min(1,opacity))};
      resolved.set(id,result);
      return result;
    };
    return scene.marks.map(mark => resolve(mark.id));
  };
}

function drawMark(ctx, mark, p, warn) {
  ctx.strokeStyle = mark.color;
  ctx.fillStyle = mark.fill ?? 'transparent';
  ctx.lineWidth = Math.max(0.01,p.stroke_width);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  if (mark.kind === 'text') {
    const family = families[mark.font], weight = mark.font === 'bold' ? 700 : 400;
    const layout = fitText(ctx,mark.text,{width:Math.max(1,p.w),height:Math.max(1,p.h),minSize:1,maxSize:Math.max(1,p.size),family,weight});
    if (mark.text && layout.size < 12) warn(mark.id,`Text ${mark.id} fits at only ${layout.size.toFixed(1)} pixels. Enlarge its bounds or shorten the label before final delivery.`);
    if (!layout.fits) warn(`${mark.id}:overflow`,`Text ${mark.id} does not fit even at the smallest font size.`);
    ctx.font = `${weight} ${layout.size}px ${family}`;
    ctx.textBaseline = 'top'; ctx.textAlign = mark.align;
    ctx.fillStyle = mark.color;
    const x = mark.align === 'left' ? 0 : mark.align === 'center' ? p.w/2 : p.w;
    layout.lines.forEach((line,index) => ctx.fillText(line.text,x,index*layout.lineHeight));
    return;
  }
  ctx.beginPath();
  if (mark.kind === 'rect') ctx.roundRect(0,0,Math.max(0,p.w),Math.max(0,p.h),Math.max(0,Math.min(p.radius,p.w/2,p.h/2)));
  else if (mark.kind === 'ellipse') ctx.ellipse(p.w/2,p.h/2,Math.max(0,p.w/2),Math.max(0,p.h/2),0,0,Math.PI*2);
  else if (mark.kind === 'arc') ctx.ellipse(p.w/2,p.h/2,Math.max(0,p.w/2),Math.max(0,p.h/2),0,radians(p.start),radians(p.end));
  else if (mark.kind === 'wave') {
    for (let i=0; i<=200; i++) {
      const x=p.w*i/200, y=p.h/2*Math.sin(Math.PI*2*p.cycles*i/200+radians(p.phase));
      if (!i) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
  } else {
    mark.points.forEach(([x,y],index) => index ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
    if (mark.kind === 'polygon') ctx.closePath();
  }
  if (mark.fill && !['line','wave'].includes(mark.kind)) ctx.fill();
  if (p.stroke_width > 0) ctx.stroke();
}

export function createPainter(canvas,scene,reportWarning=()=>{}) {
  canvas.width=scene.width; canvas.height=scene.height;
  const ctx=canvas.getContext('2d',{alpha:false}), sample=compileScene(scene);
  const warnings=new Set();
  const warn=(id,message)=>{if (!warnings.has(id)) {warnings.add(id);reportWarning(message);}};
  return time => {
    ctx.setTransform(1,0,0,1,0,0); ctx.globalAlpha=1;
    ctx.clearRect(0,0,scene.width,scene.height);
    ctx.fillStyle=scene.background; ctx.fillRect(0,0,scene.width,scene.height);
    for (const {mark,pose,matrix,opacity} of sample(time)) {
      if (opacity <= 0 || pose.scale <= 0) continue;
      ctx.save();
      ctx.transform(...matrix); ctx.globalAlpha=opacity;
      drawMark(ctx,mark,pose,warn);
      ctx.restore();
    }
  };
}

export function boot() {
  window.motionReady=(async()=>{
    const response=await fetch('./scene.json');
    if (!response.ok) throw new Error('Scene data unavailable');
    const scene=await response.json();
    await Promise.all(Object.values(families).map(family=>document.fonts.load(`42px ${family}`)));
    await document.fonts.ready;
    window.motionWarnings=[];
    const paint=createPainter(document.getElementById('scene'),scene,message=>window.motionWarnings.push(message));
    window.seek=async time=>paint(time);
    paint(0);
  })();
}
