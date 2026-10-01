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

/** Constant-speed local path offsets. A looped open path intentionally wraps. */
export function compilePath(path) {
  const points=path.points.map(point=>[...point]);
  if (path.closed && (points[0][0] !== points.at(-1)[0] || points[0][1] !== points.at(-1)[1])) points.push([...points[0]]);
  const segments=[];
  let length=0;
  for (let i=1;i<points.length;i++) {
    const from=points[i-1],to=points[i],distance=Math.hypot(to[0]-from[0],to[1]-from[1]);
    if (distance>0) {segments.push({from,to,start:length,distance});length+=distance;}
  }
  if (!length) throw new Error('Motion path must have positive length');
  return (time,index=0)=>{
    const age=time-path.start-index*path.stagger;
    const active=time>=path.start && (path.loop || age>=0);
    const progress=path.loop ? ((age/path.seconds)%1+1)%1 : Math.max(0,Math.min(1,age/path.seconds));
    const distance=progress*length;
    const segment=segments.find(item=>distance<item.start+item.distance)??segments.at(-1);
    const amount=Math.max(0,Math.min(1,(distance-segment.start)/segment.distance));
    return {x:segment.from[0]+(segment.to[0]-segment.from[0])*amount,
      y:segment.from[1]+(segment.to[1]-segment.from[1])*amount,
      rotation:path.orient ? Math.atan2(segment.to[1]-segment.from[1],segment.to[0]-segment.from[0])*180/Math.PI : 0,
      active};
  };
}

export function compileScene(scene) {
  const marks = new Map(scene.marks.map(mark => [mark.id, {...mark, sample:sampleMark(mark), path:mark.motion_path?compilePath(mark.motion_path):null}]));
  return time => {
    time=Math.max(0,Math.min(scene.duration,time));
    const resolved = new Map();
    const resolve = (id,instance=0) => {
      const key=`${id}:${instance}`;
      if (resolved.has(key)) return resolved.get(key);
      const mark = marks.get(id), pose = mark.sample(time);
      let opacity=pose.opacity;
      if (mark.path) {
        const path=mark.path(time,instance);
        pose.x+=path.x;pose.y+=path.y;pose.rotation+=path.rotation;
        if (!path.active) opacity=0;
      }
      let matrix = matrix2D({x:pose.x,y:pose.y,rotation:radians(pose.rotation),scaleX:pose.scale,scaleY:pose.scale});
      if (mark.parent) {
        const parent = resolve(mark.parent);
        matrix = compose2D(parent.matrix,matrix);
        opacity *= parent.opacity;
      }
      const result = {mark,pose,matrix,opacity:Math.max(0,Math.min(1,opacity)),instance};
      resolved.set(key,result);
      return result;
    };
    return scene.marks.flatMap(mark => Array.from({length:mark.motion_path?.count??1},(_,index)=>resolve(mark.id,index)));
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

export function createPainter(canvas,scene,reportWarning=()=>{},outputSize=scene) {
  canvas.width=outputSize.width; canvas.height=outputSize.height;
  const sx=outputSize.width/scene.width,sy=outputSize.height/scene.height;
  const ctx=canvas.getContext('2d',{alpha:false}), sample=compileScene(scene);
  const warnings=new Set();
  const warn=(id,message)=>{if (!warnings.has(id)) {warnings.add(id);reportWarning(message);}};
  return time => {
    ctx.setTransform(sx,0,0,sy,0,0); ctx.globalAlpha=1;
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
    const paint=createPainter(document.getElementById('scene'),scene,message=>window.motionWarnings.push(message),{width:window.innerWidth,height:window.innerHeight});
    window.seek=async time=>paint(time);
    paint(0);
  })();
}
