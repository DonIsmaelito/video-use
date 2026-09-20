/** Media geometry and readiness, independent of a film's subject, palette or timeline. */
const positive = (n, label) => { if (!Number.isFinite(n) || n <= 0) throw new RangeError(`${label} must be positive`); return n; };
const unit = (n, label) => { if (!Number.isFinite(n) || n < 0 || n > 1) throw new RangeError(`${label} must be in [0, 1]`); return n; };

/** Source crop for cover placement. Focus is normalized in the source image. */
export function coverRect(sourceWidth, sourceHeight, width, height, {focusX=.5, focusY=.5, zoom=1}={}) {
  [sourceWidth,sourceHeight,width,height,zoom].forEach(n => positive(n,'dimension/zoom'));
  unit(focusX,'focusX'); unit(focusY,'focusY');
  if (zoom < 1) throw new RangeError('cover zoom must be at least 1');
  const scale = Math.max(width/sourceWidth,height/sourceHeight)*zoom;
  const sw=width/scale, sh=height/scale;
  return {sx:Math.min(sourceWidth-sw,Math.max(0,sourceWidth*focusX-sw/2)),sy:Math.min(sourceHeight-sh,Math.max(0,sourceHeight*focusY-sh/2)),sw,sh};
}
export function drawCover(ctx, image, {x=0,y=0,width,height,...options}) {
  if (![x,y].every(Number.isFinite)) throw new TypeError('placement must be finite');
  const {sx,sy,sw,sh}=coverRect(image.naturalWidth || image.videoWidth || image.width,image.naturalHeight || image.videoHeight || image.height,width,height,options);
  ctx.drawImage(image,sx,sy,sw,sh,x,y,width,height);
}
export async function loadImage(url) {
  const image=new Image(); image.src=url;
  await image.decode();
  return image;
}

/** Any authored path can mask any drawing callback; no built-in transition catalogue. */
export function withMask(ctx, path, draw, fillRule='nonzero') {
  if (typeof draw !== 'function') throw new TypeError('draw must be a function');
  ctx.save();
  try { ctx.clip(path,fillRule); return draw(ctx); } finally { ctx.restore(); }
}

/** Sprite/cel timing has explicit holds; sample order never advances mutable state. */
export function celIndex(time, durations, {loop=false}={}) {
  if (!Number.isFinite(time)) throw new TypeError('time must be finite');
  if (!Array.isArray(durations) || !durations.length) throw new TypeError('durations must contain cel holds');
  durations.forEach(n=>positive(n,'cel hold'));
  const total=durations.reduce((a,b)=>a+b,0);
  let t=loop ? ((time%total)+total)%total : Math.min(total,Math.max(0,time));
  for(let i=0;i<durations.length;i++){ if(t<durations[i]) return i; t-=durations[i]; }
  return durations.length-1;
}
export function spriteRect(index, {columns,rows,width,height}) {
  [columns,rows,width,height].forEach(n=>positive(n,'sprite dimension'));
  if (![index,columns,rows].every(Number.isInteger) || index<0 || index>=columns*rows) throw new RangeError('sprite index/grid must be valid integers');
  return {sx:(index%columns)*width/columns,sy:Math.floor(index/columns)*height/rows,sw:width/columns,sh:height/rows};
}

/** Pause before seeking footage. Decode readiness is awaited; a failed seek is explicit. */
export async function seekMedia(media,time,{timeout=15000}={}) {
  if (!Number.isFinite(time) || time<0) throw new RangeError('media time must be finite and nonnegative');
  positive(timeout,'timeout');
  media.pause();
  const event=(name,action)=>new Promise((resolve,reject)=>{
    const cleanup=()=>{clearTimeout(timer);media.removeEventListener(name,done);media.removeEventListener('error',fail);};
    const done=()=>{cleanup();resolve();};
    const fail=()=>{cleanup();reject(new Error(`Media ${name} failed`));};
    const timer=setTimeout(()=>{cleanup();reject(new Error(`Media ${name} timeout`));},timeout);
    media.addEventListener(name,done,{once:true});media.addEventListener('error',fail,{once:true});
    try { action?.(); } catch(error){cleanup();reject(error);}
  });
  if(media.readyState<1) await event('loadedmetadata');
  if(!Number.isFinite(media.duration) || time>=media.duration) throw new RangeError('seek time must be before media duration');
  if(Math.abs(media.currentTime-time)>1e-7) await event('seeked',()=>{media.currentTime=time;});
  else if(media.seeking) await event('seeked');
  if(media.readyState<2) await event('loadeddata');
}
