import { clamp, lerp, ease, clip, keyframes, seededRandom, withTransform, fitText } from './lib/motion.mjs';

const canvas = document.querySelector('#film');
// CPU-backed text avoids Chrome's history-sensitive accelerated text raster cache.
const ctx = canvas.getContext('2d', { alpha:false, willReadFrequently:true });
const W=1920, H=1080;
const out=ease('outCubic'), smooth=ease('inOutCubic');
let config, ribbons, openingLayouts, resolutionLayouts;

const fit=(text,width,maxSize,family='ThoughtSans',weight=600) => fitText(ctx,text,{width,maxSize,family,weight,lineHeight:1});
const color=(value)=>config.palette[value] ?? value;
function fill(value){ctx.fillStyle=color(value);ctx.fillRect(0,0,W,H);}
function text(value,x,y,size,{family='ThoughtSans',weight=600,fill='ink',align='center'}={}){
  ctx.font=`${weight} ${size}px ${family}`;ctx.textAlign=align;ctx.textBaseline='alphabetic';ctx.fillStyle=color(fill);ctx.fillText(value,x,y);
}
const phase=(time,start,end,curve=out)=>curve(clamp((time-start)/(end-start)));
const line=(x,y,width,height,fillColor)=>{ctx.fillStyle=color(fillColor);ctx.fillRect(x,y,width,height);};

function opening(time){
  fill('paper');
  const starts=[-.7,.66,1.35];
  const bases=[325,612,899];
  config.opening.forEach((word,index)=>{
    const p=phase(time,starts[index],starts[index]+.68);
    if(time<starts[index])return;
    const layout=openingLayouts[index];
    // Each thought pushes into its own typographic line; the accent is an interruption.
    ctx.save();ctx.beginPath();ctx.rect(100,bases[index]-255,1720,283);ctx.clip();
    const drift=phase(time,2.72,3.2,smooth);
    withTransform(ctx,{x:960+drift*(index%2?-240:240),y:bases[index]+(1-p)*290},()=>{
      text(word,0,0,layout.size,{fill:index===1?'accent':'ink'});
    });
    ctx.restore();
  });
  // A thin thought becomes a large strip at the first editorial cut.
  const slash=phase(time,2.66,3.2,smooth);
  if(slash>0)withTransform(ctx,{x:960,y:540,rotation:-.055},()=>line(-W*.6,-slash*84,W*1.2,slash*168,'ink'));
}

function drawRibbon(ribbon,time,compression=0){
  const enter=phase(time,ribbon.start,ribbon.start+.65);
  if(time<ribbon.start)return;
  const direction=ribbon.index%2?1:-1;
  const longDrift=Math.sin(time*.8+ribbon.index)*12;
  const x=lerp(960+direction*(1-enter)*2450+longDrift,960,compression);
  const y=lerp(ribbon.y,540,compression);
  const angle=ribbon.rotation*(1-compression);
  withTransform(ctx,{x,y,rotation:angle,scaleY:Math.max(.01,1-compression)},()=>{
    line(-ribbon.width/2,-ribbon.height/2,ribbon.width,ribbon.height,ribbon.fill);
    ctx.save();ctx.beginPath();ctx.rect(-ribbon.width/2,-ribbon.height/2,ribbon.width,ribbon.height);ctx.clip();
    const breathing=1+Math.sin(time*1.6+ribbon.index)*.015;
    withTransform(ctx,{scaleX:breathing,scaleY:breathing},()=>text(ribbon.word,0,ribbon.size*.34,ribbon.size,{fill:ribbon.textFill}));
    ctx.restore();
  });
}

function interruption(time){
  fill('ink');
  ribbons.forEach(ribbon=>drawRibbon(ribbon,time));
  // One large question cuts across the smaller competing thoughts.
  const punctuation=phase(time,6.2,6.7);
  if(punctuation>0)withTransform(ctx,{x:W-210,y:185,scaleX:punctuation,scaleY:punctuation,rotation:.12},()=>{
    ctx.fillStyle=color('accent');ctx.beginPath();ctx.arc(0,0,128,0,Math.PI*2);ctx.fill();
    text('?',0,68,204,{fill:'ink'});
  });
}

const squeeze=keyframes([{time:7.4,value:0},{time:8.1,value:.08,ease:'inCubic'},{time:9.45,value:1}]);
function pressure(time){
  fill('accent');
  const squeezeAmount=squeeze(time);
  const collapse=phase(time,8.75,9.65,smooth);
  // Existing ribbons keep their identity as the composition loses vertical space.
  withTransform(ctx,{y:540*(1-(1-squeezeAmount*.85)),scaleY:1-squeezeAmount*.85},()=>{
    ribbons.forEach(ribbon=>drawRibbon(ribbon,7.4,collapse));
  });
  const impact=phase(time,7.4,7.7);
  const layout=fit(config.pressure,1640,305);
  const visible=1-phase(time,8.9,9.45,smooth);
  ctx.save();ctx.globalAlpha=visible;
  withTransform(ctx,{x:960,y:540,scaleX:lerp(1.18,1,impact),scaleY:lerp(.7,1,impact)},()=>{
    line(-W/2,-175,W,350,'accent');
    text(config.pressure,0,layout.size*.34,layout.size,{fill:'ink'});
  });ctx.restore();
  const finalLine=phase(time,9.25,9.65,smooth);
  if(finalLine>0)line(120,536,1680,8*finalLine,'ink');
  // The field empties through an expanding paper plane, preserving the line.
  const paper=phase(time,9.55,9.8,smooth);
  if(paper>0){line(0,0,W,540*paper,'paper');line(0,H-540*paper,W,540*paper,'paper');line(120,536,1680,8,'ink');}
}

function breathing(time){
  fill('paper');
  const t=clip(time,{start:9.8,duration:2.1}).time;
  const length=lerp(1680,150,phase(t,0,.75,smooth));
  const y=lerp(540,690,phase(t,.15,1,smooth));
  line((W-length)/2,y,length,5,'ink');
  const appear=phase(t,.2,.95);
  const layout=fit(config.release,1500,210,'ThoughtSerif',400);
  ctx.save();ctx.globalAlpha=appear*(1-phase(t,1.6,2.1));
  text(config.release,960,595+(1-appear)*30,layout.size,{family:'ThoughtSerif',weight:400});
  ctx.restore();
  const dot=phase(t,1.2,1.7);
  ctx.fillStyle=color('accent');ctx.beginPath();ctx.arc(960,690,6+5*dot,0,Math.PI*2);ctx.fill();
}

function resolution(time){
  fill('paper');
  const local=time-11.9;
  const a=phase(local,0,.9), b=phase(local,.28,1.28);
  const positions=[440,740];
  config.resolution.forEach((word,index)=>{
    const p=index===0?a:b;
    ctx.save();ctx.globalAlpha=p;ctx.beginPath();ctx.rect(90,positions[index]-300,W-180,410);ctx.clip();
    text(word,960,positions[index]+(1-p)*10,resolutionLayouts[index].size,{family:'ThoughtSerif',weight:400});
    ctx.restore();
  });
  const settle=phase(local,.45,1.6,smooth);
  const width=lerp(150,1050,settle);
  const y=lerp(690,860,phase(local,0,.35,smooth));
  line((W-width)/2,y,width,4,'ink');
  const dotX=lerp(960,(W+width)/2,settle);
  ctx.fillStyle=color('accent');ctx.beginPath();ctx.arc(dotX,y,11,0,Math.PI*2);ctx.fill();
}

function draw(time){
  ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
  const t=clamp(time,0,16);
  if(t<3.2)opening(t);
  else if(t<7.4)interruption(t);
  else if(t<9.8)pressure(t);
  else if(t<11.9)breathing(t);
  else resolution(t);
}

function prepare(){
  const rng=seededRandom(config.seed);
  openingLayouts=config.opening.map(word=>fit(word,1710,330));
  resolutionLayouts=config.resolution.map(word=>fit(word,1540,310,'ThoughtSerif',400));
  const arrangement=[
    {y:152,rotation:-.065,width:1720,height:210,start:2.85,fill:'paper',textFill:'ink'},
    {y:834,rotation:.038,width:1850,height:235,start:3.52,fill:'accent',textFill:'ink'},
    {y:378,rotation:.045,width:1590,height:225,start:3.88,fill:'accent',textFill:'ink'},
    {y:657,rotation:-.085,width:2050,height:205,start:4.23,fill:'paper',textFill:'ink'},
    {y:992,rotation:-.04,width:1600,height:190,start:4.54,fill:'paper',textFill:'ink'},
    {y:80,rotation:.08,width:1180,height:180,start:4.87,fill:'ink',textFill:'paper'},
    {y:452,rotation:-.035,width:1900,height:230,start:5.3,fill:'paper',textFill:'ink'},
    {y:690,rotation:.11,width:1200,height:180,start:5.72,fill:'ink',textFill:'paper'},
  ];
  ribbons=config.interruptions.map((word,index)=>{
    const shape=arrangement[index%arrangement.length];
    return {...shape,index,word,rotation:shape.rotation+(rng()-.5)*.006,size:fit(word,shape.width-110,shape.height*.85).size};
  });
}

window.motionReady=(async()=>{
  config=await (await fetch('./content.json')).json();
  if(!Array.isArray(config.opening)||config.opening.length!==3||!Array.isArray(config.resolution)||config.resolution.length!==2||!Array.isArray(config.interruptions)||config.interruptions.length<1)throw Error('Expected three opening lines, two resolution lines, and at least one interruption');
  await Promise.all([document.fonts.load('600 100px ThoughtSans'),document.fonts.load('400 100px ThoughtSerif')]);
  await document.fonts.ready;
  prepare();draw(0);
})();
window.seek=async seconds=>{await window.motionReady;draw(seconds);};
// Optional preview only. Renderer always calls seek; no animation starts by default.
window.playPreview=async()=>{
  await window.motionReady;
  const start=performance.now();
  const frame=now=>{const t=(now-start)/1000;draw(Math.min(t,16));if(t<16)requestAnimationFrame(frame);};
  requestAnimationFrame(frame);
};
