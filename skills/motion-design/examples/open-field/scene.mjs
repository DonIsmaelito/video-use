import {clamp, lerp, ease, keyframes, fitText, withTransform} from './lib/motion.mjs';

const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d', {alpha:false, willReadFrequently:true});
const W = 1920, H = 1080;
const smooth = ease('inOutCubic'), out = ease('outCubic');
const progress = (t,a,b) => clamp((t-a)/(b-a));
let content, p;
const fonts = [
  new FontFace('Field Sans', 'url(assets/inter-regular.ttf)', {weight:'400'}),
  new FontFace('Field Sans', 'url(assets/inter-semibold.ttf)', {weight:'600'}),
  new FontFace('Field Serif', 'url(assets/instrument-serif.ttf)'),
  new FontFace('Field Italic', 'url(assets/instrument-serif-italic.ttf)'),
];

function rect(x,y,w,h,r,fill,stroke) {
  ctx.beginPath(); ctx.roundRect(x,y,w,h,r);
  if(fill){ctx.fillStyle=fill;ctx.fill();}
  if(stroke){ctx.lineWidth=1.5;ctx.strokeStyle=stroke;ctx.stroke();}
}
function circle(x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
function text(value,x,y,size=32,color=p.ink,family='Field Sans',maxWidth=Infinity,weight=400) {
  const fitted = Number.isFinite(maxWidth) ? fitText(ctx,value,{width:maxWidth,maxSize:size,minSize:12,family:`"${family}"`,weight}) : {size};
  ctx.font=`${weight} ${fitted.size}px "${family}"`;ctx.fillStyle=color;ctx.textAlign='left';ctx.textBaseline='alphabetic';ctx.fillText(value,x,y);
}
function lines(values,x,y,size,color,family,gap,maxWidth) {values.forEach((value,i)=>text(value,x,y+i*gap,size,color,family,maxWidth));}
function petal(size,color) {
  ctx.fillStyle=color;ctx.beginPath();
  ctx.moveTo(0,0);ctx.lineTo(-size,0);ctx.bezierCurveTo(-size,-size*.62,-size*.6,-size,0,-size);
  ctx.bezierCurveTo(size*.06,-size*.57,size*.08,-size*.3,0,0);ctx.fill();
}
function mark(x,y,size,color,rotation=0,openness=size*.026) {
  withTransform(ctx,{x,y,rotation},()=>{
    for(let i=0;i<4;i++) withTransform(ctx,{rotation:i*Math.PI/2,x:(i===0||i===3?-1:1)*openness,y:(i<2?-1:1)*openness},()=>petal(size*.49,color));
  });
}
function brand(x,y,color=p.ink,scale=1) {
  mark(x+23*scale,y-12*scale,42*scale,color);
  text(content.brand,x+65*scale,y,32*scale,color,'Field Sans',350*scale,600);
}
function grid(alpha=1) {
  ctx.save();ctx.globalAlpha=alpha;ctx.strokeStyle=p.line;ctx.lineWidth=1;
  for(let x=60;x<W;x+=120)for(let y=90;y<H;y+=120){ctx.beginPath();ctx.moveTo(x-3,y);ctx.lineTo(x+3,y);ctx.moveTo(x,y-3);ctx.lineTo(x,y+3);ctx.stroke();}
  ctx.restore();
}
function card(index,x,y,scale,rotation,alpha=1) {
  const item=content.cards[index % content.cards.length];
  withTransform(ctx,{x,y,rotation,scaleX:scale,scaleY:scale},()=>{
    ctx.globalAlpha*=alpha;
    const background = item.kind==='art'?p.accent:item.kind==='palette'?p.lilac:item.kind==='shape'?p.leaf:item.kind==='type'?p.ink:'#fcfaf4';
    rect(-175,-128,350,256,15,background);
    const color=item.kind==='type'?p.paper:p.ink;
    if(item.kind==='art') {
      ctx.save();ctx.beginPath();ctx.roundRect(-175,-128,350,256,15);ctx.clip();
      for(let j=0;j<4;j++)withTransform(ctx,{x:-92+j*63,y:10,rotation:-.25+j*.14},()=>petal(135,p.paper));
      ctx.restore();
      text(item.title,-145,97,22,p.paper,'Field Sans',290);
    } else if(item.kind==='palette') {
      text(item.title,-145,-86,22,color,'Field Sans',290,600);
      [p.accent,p.leaf,p.ink,p.paper].forEach((color,i)=>rect(-145+i*73,-48,74,98,0,color));
      text(item.body,-145,95,21,color,'Field Sans',290);
    } else if(item.kind==='shape') {
      text(item.title,-145,-86,22,color,'Field Sans',290,600);
      mark(0,8,150,p.ink,-.25);
      text(item.body,-145,100,20,color,'Field Sans',290);
    } else if(item.kind==='type') {
      text(item.title,-145,-80,25,p.leaf,'Field Sans',290);
      text(content.brand.split(' ')[0],-145,17,83,p.paper,'Field Serif',290);
      text(content.brand.split(' ').slice(1).join(' ') || 'Studio',-145,88,83,p.paper,'Field Italic',290);
    } else {
      circle(-135,-85,7,p.accent);
      text(item.title,-115,-78,24,color,'Field Sans',260,600);
      const words=item.body.split(' '), midpoint=Math.ceil(words.length/2);
      lines([words.slice(0,midpoint).join(' '),words.slice(midpoint).join(' ')],-145,2,40,color,'Field Serif',43,288);
      ctx.strokeStyle=p.line;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(-145,90);ctx.lineTo(142,90);ctx.stroke();
    }
  });
}

const scatter = [
  {x:1230,y:253,rotation:-.12},{x:1637,y:552,rotation:.12},{x:1154,y:813,rotation:-.05},
  {x:1645,y:69,rotation:.07},{x:1010,y:622,rotation:.1},{x:1734,y:938,rotation:-.12},
];
const columns=[704,1105,1506], rows=[436,754];
const settled = Array.from({length:6},(_,i)=>({x:columns[i%3],y:rows[Math.floor(i/3)],rotation:0}));
const cardMoves = scatter.map((from,i)=>keyframes([
  {time:0,value:from,ease:'linear'},
  {time:2.55+i*.065,value:{...from,y:from.y-17},ease:'inOutCubic'},
  {time:5.6+i*.065,value:settled[i]},
]));

function workspace(t) {
  const assembled=smooth(progress(t,2.8,5.6));
  const vanish=smooth(progress(t,8.6,10.25));
  const zoom=lerp(1,.86,vanish);
  ctx.fillStyle=p.paper;ctx.fillRect(0,0,W,H);grid(1-assembled*.8);
  ctx.save();ctx.globalAlpha=1-assembled;
  brand(105,109);
  lines(content.opening,100,355,125,p.ink,'Field Serif',125,820);
  ctx.restore();
  ctx.save();ctx.globalAlpha=assembled*(1-vanish);
  rect(83,88,1754,912,22,'#e6e6dc',p.line);
  rect(83,88,1754,84,22,'#faf8f1');rect(83,140,1754,32,0,'#faf8f1');
  brand(112,141,p.ink,.9);
  text(content.collection,690,140,25,p.ink,'Field Sans',600);
  circle(1681,130,18,p.lilac);circle(1705,130,18,p.leaf);circle(1729,130,18,p.accent);
  rect(112,217,334,732,15,'#f8f7ef');
  text('Your workspace',141,269,21,'#787f73','Field Sans',265);
  text(content.project,141,319,32,p.ink,'Field Serif',268);
  rect(133,355,290,52,10,p.ink);
  text(content.collection,152,388,22,p.paper,'Field Sans',230);
  text('Connections',152,452,22,p.ink,'Field Sans',235);
  text('Shared with everyone',143,914,17,'#787f73','Field Sans',265);
  text(content.workspace,528,250,46,p.ink,'Field Serif',1110);
  ctx.restore();
  withTransform(ctx,{x:W/2,y:H/2,scaleX:zoom,scaleY:zoom},()=>{
    ctx.translate(-W/2,-H/2);
    const connected=out(progress(t,5.3,7.1));
    ctx.save();ctx.globalAlpha=assembled*(1-vanish);
    ctx.strokeStyle=p.accent;ctx.lineWidth=3;
    for(let i=0;i<5;i++) {
      const a=settled[i],b=settled[(i+1)%6];
      ctx.setLineDash([18,12]);ctx.lineDashOffset=-t*28;
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.bezierCurveTo(a.x+170,a.y,b.x-170,b.y,lerp(a.x,b.x,connected),lerp(a.y,b.y,connected));ctx.stroke();
    }
    ctx.restore();
    scatter.forEach((_,i)=>{
      const pose=cardMoves[i](t);
      const shrink=out(progress(t,8.45+i*.07,10.05+i*.03));
      const angle=i*Math.PI/3-Math.PI/2;
      const x=lerp(pose.x,W/2+Math.cos(angle)*100,shrink), y=lerp(pose.y,H/2+Math.sin(angle)*100,shrink);
      card(i,x,y,lerp(1,.045,shrink),pose.rotation+shrink*Math.PI*.3,1-smooth(progress(shrink,.8,1)));
    });
  });
  const gesture=progress(t,4.3,5.7), selected=out(progress(t,5.6,6.2));
  if(t>4.3&&t<6.35){
    ctx.save();ctx.globalAlpha=Math.min(progress(t,4.3,4.7),1-progress(t,6.05,6.35));
    const x=lerp(1240,1530,smooth(gesture)),y=lerp(920,842,smooth(gesture));
    circle(x,y,12+selected*46,`rgba(236,87,60,${.18*(1-selected)})`);
    ctx.translate(x,y);ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(0,40);ctx.lineTo(12,29);ctx.lineTo(22,49);ctx.lineTo(31,45);ctx.lineTo(21,25);ctx.lineTo(38,25);ctx.closePath();ctx.fillStyle=p.ink;ctx.fill();ctx.strokeStyle=p.paper;ctx.lineWidth=3;ctx.stroke();ctx.restore();
  }
}

function identity(t) {
  const local=t-9.3;
  const background=out(progress(t,9.65,10.45));
  ctx.save();ctx.globalAlpha=background;ctx.fillStyle=p.accent;ctx.fillRect(0,0,W,H);ctx.restore();
  const reveal=out(progress(local,0,1.15)), compact=smooth(progress(t,11.5,12.65));
  const x=lerp(W/2,585,compact),y=lerp(H/2,522,compact),size=lerp(0,420,reveal)*lerp(1,.52,compact);
  mark(x,y,size,p.paper,lerp(-Math.PI/2,0,reveal),lerp(105,5,reveal));
  ctx.save();ctx.globalAlpha=compact;
  text(content.brand,745,566,122,p.paper,'Field Sans',970,600);
  ctx.restore();
}

function editorial(t) {
  const reveal=smooth(progress(t,13.0,14.35));
  if(reveal===0)return;
  ctx.save();ctx.beginPath();ctx.rect(0,0,W,H*reveal);ctx.clip();
  ctx.fillStyle=p.paper;ctx.fillRect(0,0,W,H);
  ctx.save();ctx.beginPath();ctx.rect(0,0,786,H);ctx.clip();ctx.fillStyle=p.ink;ctx.fillRect(0,0,786,H);
  for(let row=0;row<3;row++)for(let col=0;col<2;col++){
    const drift=out(progress(t,13.0,15.7));
    mark(-34+col*534,96+row*525,650,col%2?p.leaf:p.accent,lerp(-.3,0,drift)+row*.08);
  }
  ctx.restore();
  brand(864,119,p.ink,.9);
  const settle=out(progress(t,13.8,15.6));
  lines(content.closing,863,499+(1-settle)*55,155,p.ink,'Field Serif',151,978);
  text(content.edition,872,931,25,p.ink,'Field Sans',897);
  ctx.strokeStyle=p.line;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(872,881);ctx.lineTo(1796,881);ctx.stroke();
  ctx.restore();
}

window.seek = seconds => {
  const t=clamp(seconds,0,18);
  ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.setLineDash([]);
  ctx.fillStyle=p.paper;ctx.fillRect(0,0,W,H);
  if(t<10.5)workspace(t);
  if(t>=9.3)identity(t);
  editorial(t);
};
window.motionReady = Promise.all([fetch('./content.json').then(response=>{if(!response.ok)throw new Error('Content unavailable');return response.json();}),...fonts.map(font=>font.load().then(loaded=>document.fonts.add(loaded)))]).then(([data])=>{
  if(!data.cards?.length)throw new Error('At least one editable idea card is required');
  content=data;p=data.palette;window.seek(0);
});
