import {clamp,lerp,ease,fitText,seededRandom,withTransform} from './lib/motion.mjs';
import {loadImage,drawCover,withMask} from './lib/media.mjs';
const canvas=document.getElementById('film'),ctx=canvas.getContext('2d');
const W=1920,H=1080;
let cfg,photos,paperMarks;
const smooth=ease('inOutCubic'),out=ease('outCubic');
const phase=(t,a,b)=>clamp((t-a)/(b-a));
const pathRect=(x,y,w,h)=>{const p=new Path2D();p.rect(x,y,w,h);return p;};
function fill(color){ctx.fillStyle=color;ctx.fillRect(0,0,W,H);}
function text(copy,x,y,width,size,color,{italic=false,align='left'}={}){
 const family=italic?'EditorialItalic':'Editorial';
 const layout=fitText(ctx,copy,{width,maxSize:size,family,lineHeight:.84});
 ctx.fillStyle=color;ctx.font=`${layout.size}px ${family}`;ctx.textAlign=align;ctx.textBaseline='alphabetic';
 layout.lines.forEach((line,i)=>ctx.fillText(line.text,x,y+i*layout.lineHeight));
}
function torn(x,y,w,h,seed){
 const p=new Path2D(),rand=seededRandom(seed);p.moveTo(x,y);
 for(let i=0;i<=30;i++)p.lineTo(x+w*i/30,y+(rand()-.5)*10);
 for(let i=0;i<=18;i++)p.lineTo(x+w+(rand()-.5)*8,y+h*i/18);
 for(let i=30;i>=0;i--)p.lineTo(x+w*i/30,y+h+(rand()-.5)*10);
 for(let i=18;i>=0;i--)p.lineTo(x+(rand()-.5)*8,y+h*i/18);
 p.closePath();return p;
}
function print(image,id,x,y,w,h,rotation,zoom=1){
 withTransform(ctx,{x,y,rotation},()=>{
  const p=torn(-w/2-16,-h/2-16,w+32,h+32,`${cfg.seed}:${id}:edge`);
  ctx.shadowColor='#081b2430';ctx.shadowBlur=40;ctx.shadowOffsetY=24;ctx.fillStyle=cfg.colors.paper;ctx.fill(p);ctx.shadowColor='transparent';
  withMask(ctx,torn(-w/2,-h/2,w,h,`${cfg.seed}:${id}:mask`),()=>drawCover(ctx,image,{x:-w/2,y:-h/2,width:w,height:h,zoom}));
 });
}
function route(t,color,points,width=6){
 ctx.save();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';
 ctx.beginPath();const n=Math.floor(clamp(t)*(points.length-1));
 points.slice(0,n+1).forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
 if(n<points.length-1){const f=clamp(t)*(points.length-1)-n;ctx.lineTo(lerp(points[n][0],points[n+1][0],f),lerp(points[n][1],points[n+1][1],f));}
 ctx.stroke();ctx.restore();
}
const curve=Array.from({length:181},(_,i)=>{const p=i/180;return [80+p*1730,720-Math.sin(p*Math.PI*2.3)*180-p*70];});
function city(t,d){
 fill(cfg.colors.ink);
 const open=smooth(phase(t,d-1.1,d));
 for(let i=0;i<5;i++){
  const w=280, x=240+i*286+(i-2)*open*155;
  const y=105+Math.sin(i*2.3+t*.7)*18+(i%2?1:-1)*open*420;
  withMask(ctx,pathRect(x,y,w,820),()=>drawCover(ctx,photos.city,{x:240-open*80,y:60,width:1440+open*160,height:960,zoom:1.05+t*.012}));
 }
 ctx.fillStyle=cfg.colors.ink;ctx.fillRect(0,780,W,300);
 text(cfg.copy[0],100,972,1600,210,cfg.colors.paper);
 route(phase(t,.2,2.6),cfg.colors.orange,curve,5);
}
function detour(t,d){
 fill(cfg.colors.paper);const enter=out(phase(t,0,1.2));
 const disc=new Path2D();disc.ellipse(1350,515,420*enter,420*enter,0,0,Math.PI*2);
 withMask(ctx,disc,()=>drawCover(ctx,photos.coast,{x:930,y:85,width:850,height:870,focusX:.32,zoom:1+t*.014}));
 text(cfg.copy[1],110,390,820,235,cfg.colors.blue,{italic:true});
 const ring=new Path2D();ring.ellipse(1350,515,450,450,0,-Math.PI*.9,-Math.PI*.9+Math.PI*1.75*phase(t,.4,2.5));
 ctx.strokeStyle=cfg.colors.orange;ctx.lineWidth=4;ctx.stroke(ring);
 ctx.save();ctx.translate(1130,824+(1-enter)*420);ctx.rotate(-.12);
 ctx.fillStyle=cfg.colors.blue;ctx.fillRect(-140,-100,280,200);
 drawCover(ctx,photos.water,{x:-125,y:-85,width:250,height:170});ctx.restore();
 route(phase(t,1,3),cfg.colors.orange,curve.map(([x,y])=>[x,y+120]),5);
}
function collage(t,d){
 fill(cfg.colors.blue);const settle=out(phase(t,0,1));
 const drift=Math.sin(t*.45)*10;
 print(photos.city,'city',400,540+(1-settle)*700,510,660,-.14+Math.sin(t*.7)*.01,1.06);
 print(photos.coast,'coast',965,515-(1-settle)*900+drift,780,570,.07+Math.sin(t*.5)*.012,1.02);
 print(photos.water,'water',1515,580+(1-settle)*850,570,720,.15-Math.sin(t*.65)*.016,1.03);
 route(phase(t,.5,2.8),cfg.colors.orange,curve,9);
 text(cfg.copy[2],960,1020,1700,130,cfg.colors.paper,{italic:true,align:'center'});
}
function shore(t,d){
 const reveal=out(phase(t,0,1.05));fill(cfg.colors.paper);
 const mask=new Path2D();mask.rect(0,0,W*reveal,H);
 withMask(ctx,mask,()=>drawCover(ctx,photos.water,{x:0,y:0,width:W,height:H,zoom:lerp(1.19,1.085,clamp(t/d)),focusX:.52,focusY:.5}));
 const shade=ctx.createLinearGradient(0,0,1520,0);shade.addColorStop(0,'#073c4170');shade.addColorStop(.66,'#073c4138');shade.addColorStop(1,'#073c4100');ctx.fillStyle=shade;ctx.fillRect(0,0,W,H);
 const arrival=out(phase(t,.65,1.5));
 ctx.save();ctx.globalAlpha=arrival;
 text(cfg.copy[3],125,480+(1-arrival)*65,1450,280,cfg.colors.paper,{italic:true});ctx.restore();
 route(phase(t,1.4,3.2),cfg.colors.paper,curve.map(([x,y])=>[x,y+230]),3);
}
function seek(seconds){
 if(!cfg)throw new Error('await motionReady');
 ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;
 let start=0;let shot=cfg.shots.length-1;
 for(let i=0;i<cfg.shots.length;i++){if(seconds<start+cfg.shots[i]){shot=i;break;}start+=cfg.shots[i];}
 if(shot===cfg.shots.length-1)start=cfg.shots.slice(0,-1).reduce((a,b)=>a+b,0);
 [city,detour,collage,shore][shot](clamp(seconds-start,0,cfg.shots[shot]),cfg.shots[shot]);
 ctx.save();ctx.globalAlpha=.12;ctx.fillStyle='#f8f4e8';for(const p of paperMarks)ctx.fillRect(p.x,p.y,p.s,p.s);ctx.restore();
}
window.motionReady=(async()=>{
 cfg=await (await fetch('./content.json')).json();
 if(!Array.isArray(cfg.shots)||cfg.shots.length!==4||!cfg.shots.every(n=>Number.isFinite(n)&&n>0))throw new Error('This authored film requires four positive shot durations; update manifest duration to their sum.');
 const manifest=await (await fetch('./motion-project.json')).json();
 if(Math.abs(cfg.shots.reduce((a,b)=>a+b,0)-manifest.render.duration)>1e-6)throw new Error('Sum of content.shots must equal the project render duration');
 for(const [family,file] of [['Editorial','instrument-serif.ttf'],['EditorialItalic','instrument-serif-italic.ttf']]){const f=new FontFace(family,`url(assets/${file})`);document.fonts.add(await f.load());}
 photos=Object.fromEntries(await Promise.all(Object.entries(cfg.images).map(async([key,url])=>[key,await loadImage(url)])));
 const rand=seededRandom(cfg.seed);paperMarks=Array.from({length:1900},()=>({x:rand()*W,y:rand()*H,s:rand()*1.5+.4}));seek(0);
})();
window.seek=seek;
