// Original flat illustration. Every limb and patterned surface follows absolute state.
export function createCheckerZebra({ink='#101218',ivory='#fffce9'}={}) {
  const outline=[[-310,15],[-323,-45],[-290,-106],[-238,-138],[-120,-152],[-10,-145],[58,-130],[91,-203],[99,-268],[103,-296],[113,-321],[128,-285],[148,-280],[154,-311],[170,-299],[166,-273],[204,-260],[221,-236],[269,-211],[271,-182],[249,-166],[218,-177],[177,-199],[153,-193],[137,-143],[136,-84],[125,-32],[97,6],[29,43],[-122,62],[-243,53],[-285,31]];
  const lengths=[0];let perimeter=0;
  for(let i=1;i<outline.length;i++){perimeter+=Math.hypot(outline[i][0]-outline[i-1][0],outline[i][1]-outline[i-1][1]);lengths.push(perimeter);}perimeter+=Math.hypot(outline[0][0]-outline.at(-1)[0],outline[0][1]-outline.at(-1)[1]);
  const clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*(3-2*x)},mix=(a,b,t)=>a+(b-a)*t;
  function rectangle(f){let d=(f*1800+140)%1800;if(d<600)return [-300+d,-150];d-=600;if(d<300)return [300,-150+d];d-=300;if(d<600)return [300-d,150];d-=600;return [-300,150-d];}
  function contour(peel){const p=new Path2D();outline.forEach(([x,y],i)=>{const a=rectangle(lengths[i]/perimeter),q=mix(a[0],x,peel),r=mix(a[1],y,peel)+Math.sin(lengths[i]/perimeter*Math.PI*3)*Math.sin(peel*Math.PI)*35;if(i)p.lineTo(q,r);else p.moveTo(q,r);});p.closePath();return p;}
  function segment(ctx,a,b,w1,w2,shade){
    const dx=b.x-a.x,dy=b.y-a.y,l=Math.hypot(dx,dy),nx=-dy/l,ny=dx/l;
    const p=new Path2D();p.moveTo(a.x+nx*w1/2,a.y+ny*w1/2);p.lineTo(b.x+nx*w2/2,b.y+ny*w2/2);p.quadraticCurveTo(b.x+dx/l*5,b.y+dy/l*5,b.x-nx*w2/2,b.y-ny*w2/2);p.lineTo(a.x-nx*w1/2,a.y-ny*w1/2);p.closePath();
    ctx.fillStyle=shade;ctx.fill(p);ctx.save();ctx.clip(p);ctx.strokeStyle=ink;
    for(let u=.1;u<1;u+=.2){const x=mix(a.x,b.x,u),y=mix(a.y,b.y,u);ctx.lineWidth=5+u*3;ctx.beginPath();ctx.moveTo(x-nx*35,y-ny*35);ctx.quadraticCurveTo(x+dx/l*5,y+dy/l*5,x+nx*35,y+ny*35);ctx.stroke();}ctx.restore();
  }
  function leg(ctx,x,y,phase,rear,amount,far){
    const theta=(rear?-.45:.28)+.82*Math.cos(phase),bend=(rear?-1:1)*(.48+.5*Math.sin(phase-.7));
    const a={x,y},b={x:x+Math.sin(theta)*92*amount,y:y+Math.cos(theta)*92*amount},c={x:b.x+Math.sin(theta+bend)*91*amount,y:b.y+Math.cos(theta+bend)*91*amount};
    if(amount<.005)return;
    segment(ctx,a,b,rear?47:34,20,far?'#d4d5c0':ivory);segment(ctx,b,c,22,14,far?'#d4d5c0':ivory);
    ctx.save();ctx.translate(c.x,c.y);ctx.rotate(-theta-bend);ctx.fillStyle=ink;ctx.beginPath();ctx.moveTo(-9,-2);ctx.lineTo(10,-2);ctx.lineTo(15,15);ctx.lineTo(-10,15);ctx.closePath();ctx.fill();ctx.restore();
  }
  function draw(ctx,{x=0,y=0,scale=1,peel=1,phase=0,gallop=1,rotation=0}={}){
    if(![x,y,scale,peel,phase,gallop,rotation].every(Number.isFinite))throw new Error('finite state required');peel=clamp(peel);gallop=clamp(gallop);
    const unfold=ease((peel-.64)/.36),face=ease((peel-.74)/.20),gait=phase*gallop;
    function attachment(x,y,index){const a=rectangle(lengths[index]/perimeter);return {x:mix(a[0],x,peel),y:mix(a[1],y,peel)+Math.sin(lengths[index]/perimeter*Math.PI*3)*Math.sin(peel*Math.PI)*35};}
    const rear=attachment(-252,24,30),front=attachment(91,-1,27),tail=attachment(-297,-50,1);
    ctx.save();ctx.translate(x,y);ctx.rotate(rotation+.025*Math.sin(gait)*gallop*unfold);ctx.scale(scale,scale);
    ctx.lineJoin='round';ctx.lineCap='round';
    ctx.globalAlpha=1;
    leg(ctx,rear.x+19*peel,rear.y-4*peel,gait+2.2,true,unfold,true);leg(ctx,front.x-14*peel,front.y+8*peel,gait+3.1,false,unfold,true);
    ctx.save();ctx.translate(tail.x,tail.y);ctx.scale(unfold,unfold);ctx.translate(297,50);
    // A tail grows from the rear attachment as the cloth resolves.
    ctx.strokeStyle=ink;ctx.lineWidth=6;ctx.beginPath();ctx.moveTo(-297,-50);ctx.bezierCurveTo(-363,-70+15*Math.sin(gait),-355,32,-382,38+22*Math.sin(gait-.6));ctx.stroke();
    ctx.save();ctx.translate(-382,38+22*Math.sin(gait-.6));ctx.rotate(-.4+.3*Math.sin(gait));ctx.fillStyle=ink;ctx.beginPath();ctx.moveTo(0,-8);ctx.quadraticCurveTo(-28,5,-29,33);ctx.quadraticCurveTo(-3,21,7,2);ctx.closePath();ctx.fill();ctx.restore();ctx.restore();
    ctx.globalAlpha=1;
    const body=contour(peel);ctx.fillStyle=ivory;ctx.fill(body);
    ctx.save();ctx.clip(body);ctx.fillStyle=ink;
    const stripes=ease((peel-.1)/.9),cell=42;
    for(let row=-10;row<6;row++)for(let col=-12;col<12;col++){
      const y0=row*cell,y1=y0+cell+.7;
      function edge(y,right){const start=col*cell*2+(Math.abs(row)%2)*cell+(right?cell:0);const target=col*51+Math.sin(y*.012+col*.51)*14+Math.sin(y*.028-col*.8)*5+(right?23+7*Math.sin(col*.8):0);return mix(start,target,stripes);}
      ctx.beginPath();ctx.moveTo(edge(y0,false),y0);ctx.lineTo(edge(y0,true),y0);ctx.lineTo(edge(y1,true),y1);ctx.lineTo(edge(y1,false),y1);ctx.closePath();ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha=1;
    leg(ctx,rear.x,rear.y,gait+.75,true,unfold,false);leg(ctx,front.x,front.y,gait+4.3,false,unfold,false);
    // Upright striped mane and the long dark muzzle are specific zebra landmarks.
    ctx.globalAlpha=face;ctx.save();if(peel<.999)ctx.clip(body);
    const mane=[[56,-130,6],[72,-216,7],[88,-280,8],[101,-291,9],[107,-272,8],[94,-207,7],[73,-126,6]];
    ctx.fillStyle=ink;ctx.beginPath();mane.forEach(([x,y,i],j)=>{const p=attachment(x,y,i);if(j)ctx.lineTo(p.x,p.y);else ctx.moveTo(p.x,p.y);});ctx.closePath();ctx.fill();
    const muzzle=attachment(248,-192,19),eye=attachment(179,-246,16);
    ctx.fillStyle=ink;ctx.beginPath();ctx.ellipse(muzzle.x,muzzle.y,25*peel,15*peel,.38,0,Math.PI*2);ctx.fill();
    ctx.fillStyle=ivory;ctx.beginPath();ctx.ellipse(muzzle.x+5*peel,muzzle.y-4*peel,5*peel,2*peel,.4,0,Math.PI*2);ctx.fill();
    ctx.fillStyle=ivory;ctx.beginPath();ctx.ellipse(eye.x,eye.y,13*peel,10*peel,.22,0,Math.PI*2);ctx.fill();ctx.fillStyle=ink;ctx.beginPath();ctx.ellipse(eye.x+2*peel,eye.y,5*peel,6*peel,.22,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle=ink;ctx.lineWidth=5;ctx.beginPath();
    for(const pair of [[[113,-302,10],[119,-283,11]],[[157,-297,13],[157,-281,15]]]){const a=attachment(...pair[0]),b=attachment(...pair[1]);ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);}ctx.stroke();ctx.restore();
    ctx.restore();
  }
  return {draw,dispose(){}};
}
