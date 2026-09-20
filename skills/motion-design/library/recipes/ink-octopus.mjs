export function createInkOctopus({ink='#172994',paper='#f5edda',seed=8231}={}){
 if(!Number.isFinite(seed))throw new Error('seed must be finite');
 const canvas=document.createElement('canvas');canvas.width=1500;canvas.height=1150;const c=canvas.getContext('2d',{willReadFrequently:true}),grain=document.createElement('canvas');grain.width=1500;grain.height=1150;const g=grain.getContext('2d');let s=seed>>>0;
 const random=()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};
 for(let i=0;i<23000;i++){const x=random()*1500,y=random()*1150,r=.35+random()*1.25;g.fillStyle=random()>.45?'rgba(246,239,221,.095)':'rgba(4,12,65,.13)';g.beginPath();g.ellipse(x,y,r,r*(.3+random()),random()*Math.PI,0,Math.PI*2);g.fill();}
 for(let i=0;i<45;i++){const x=random()*1500,y=random()*1150,r=22+random()*110,gradient=g.createRadialGradient(x,y,0,x,y,r);gradient.addColorStop(0,'rgba(5,12,62,.07)');gradient.addColorStop(1,'rgba(5,12,62,0)');g.fillStyle=gradient;g.fillRect(x-r,y-r,r*2,r*2);}
 const clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*(3-2*x)},TAU=Math.PI*2;
 const roots=[-94,-67,-39,-13,13,39,67,94],angles=[-1.53,-1.07,-.62,-.21,.21,.62,1.07,1.53],lengths=[470,490,505,442,442,505,490,470];let disposed=false;
 function draw(ctx,{x=0,y=0,scale=1,rotation=0,form=1,phase=0,jet=1,curl=1}={}){
  if(disposed)throw new Error('Octopus disposed');if(![x,y,scale,rotation,form,phase,jet,curl].every(Number.isFinite))throw new Error('state values must be finite');form=clamp(form);jet=clamp(jet);curl=Math.max(.2,Math.min(1.5,curl));const growth=ease(form),pulse=Math.sin(phase)*jet,sx=1-.06*pulse,sy=1+.045*pulse;
  c.setTransform(1,0,0,1,0,0);c.globalAlpha=1;c.globalCompositeOperation='source-over';c.clearRect(0,0,1500,1150);c.translate(750,290);const paths=[];
  for(let arm=0;arm<8;arm++){
   const side=arm<4?-1:1,L=lengths[arm]*growth*(1+.045*Math.sin(phase-arm*.35)*jet),points=[],rootX=roots[arm]*sx,rootY=65+13*Math.abs(roots[arm])/94;let px=rootX,py=rootY;
   for(let j=0;j<=72;j++){
    const u=j/72,theta=angles[arm]+side*(4.35*curl)*u**3.25+.25*jet*Math.sin(phase-u*TAU*1.04+arm*.53)*u;
    if(j){px+=Math.sin(theta)*L/72;py+=Math.cos(theta)*L/72;}
    const half=(30-3*Math.abs(arm-3.5)/3.5)*(1-u)**.72*growth+1.6*growth;
    points.push({x:px,y:py,w:half,nx:Math.cos(theta),ny:-Math.sin(theta)});
   }
   paths.push(points);
  }
  const order=[0,7,1,6,2,5,3,4];
  function outline(points){c.beginPath();for(let j=0;j<points.length;j++){const p=points[j],x=p.x+p.nx*p.w,y=p.y+p.ny*p.w;if(j)c.lineTo(x,y);else c.moveTo(x,y);}for(let j=points.length-1;j>=0;j--){const p=points[j];c.lineTo(p.x-p.nx*p.w,p.y-p.ny*p.w);}c.closePath();}
  for(const arm of order){outline(paths[arm]);const grad=c.createLinearGradient(0,20,0,580);grad.addColorStop(0,ink);grad.addColorStop(.5,'#152783');grad.addColorStop(1,'#111e6c');c.fillStyle=grad;c.fill();c.strokeStyle='rgba(6,12,55,.55)';c.lineWidth=1.8;c.stroke();}
  // One continuous mantle develops from the original drop contour.
  const mix=(a,b)=>a+(b-a)*growth;c.save();c.scale(sx,sy);c.beginPath();c.moveTo(0,mix(-170,-156));c.bezierCurveTo(mix(19,84),mix(-118,-156),mix(123,145),mix(-76,-106),mix(119,127),mix(25,10));c.bezierCurveTo(mix(112,124),mix(153,97),mix(-112,-124),mix(153,97),mix(-119,-127),mix(25,10));c.bezierCurveTo(mix(-123,-145),mix(-76,-106),mix(-19,-84),mix(-118,-156),0,mix(-170,-156));c.closePath();const pool=c.createRadialGradient(-45,-60,15,0,5,210);pool.addColorStop(0,'#243ca7');pool.addColorStop(.65,ink);pool.addColorStop(1,'#101d71');c.fillStyle=pool;c.fill();c.strokeStyle='rgba(4,11,56,.62)';c.lineWidth=2.2;c.stroke();c.restore();
  c.setTransform(1,0,0,1,0,0);c.globalCompositeOperation='source-atop';c.drawImage(grain,0,0);c.globalCompositeOperation='source-over';c.translate(750,290);
  // Small negative-space suckers follow the same arm curves, never free particles.
  const detail=ease((form-.48)/.4);c.fillStyle=paper;c.globalAlpha=.72*detail;
  for(let arm=0;arm<8;arm++)for(let k=0;k<9;k++){const u=.29+k*.07,p=paths[arm][Math.round(u*72)],side=arm<4?1:-1;c.save();c.translate(p.x+p.nx*p.w*.43*side,p.y+p.ny*p.w*.43*side);c.rotate(Math.atan2(p.ny,p.nx));c.beginPath();c.ellipse(0,0,Math.max(1.6,p.w*.21),Math.max(1.1,p.w*.12),0,0,TAU);c.fill();c.restore();}
  c.globalAlpha=detail;for(const side of[-1,1]){c.save();c.translate(side*47*sx,39*sy);c.rotate(side*-.08);c.fillStyle=paper;c.beginPath();c.ellipse(0,0,15,21,0,0,TAU);c.fill();c.fillStyle='#101b62';c.beginPath();c.ellipse(side*-1.5,-1+2*jet*Math.sin(phase*.4),5.5,9.5,0,0,TAU);c.fill();c.restore();}c.globalAlpha=1;
  ctx.save();ctx.translate(x,y);ctx.rotate(rotation);ctx.scale(scale,scale);ctx.globalAlpha=.20;ctx.filter='blur(1.1px)';ctx.drawImage(canvas,-750,-290);ctx.filter='none';ctx.globalAlpha=1;ctx.drawImage(canvas,-750,-290);ctx.restore();
 }
 function dispose(){if(disposed)return;disposed=true;canvas.width=canvas.height=0;grain.width=grain.height=0;}
 return {draw,dispose,controls:['form','phase','jet','curl','x','y','scale','rotation']};
}
