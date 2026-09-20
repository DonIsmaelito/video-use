import {clamp,lerp,keyframes,seededRandom,withTransform} from './lib/motion.mjs';
import {twoBoneIK} from './lib/rig.mjs';
import {celIndex} from './lib/media.mjs';
const ctx=document.querySelector('canvas').getContext('2d');let cfg,performance,marks;
const line=(points,color,width)=>{ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke();};
function oval(x,y,rx,ry,color,rot=0){ctx.beginPath();ctx.ellipse(x,y,Math.max(.2,rx),Math.max(.2,ry),rot,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
function limb(root,target,bend){const q=twoBoneIK({root,target,upper:cfg.character.armUpper,lower:cfg.character.armLower,bend});line([root,q.elbow,q.end],cfg.colors.edge,31);line([root,q.elbow,q.end],cfg.colors.body,23);oval(q.end.x,q.end.y,22,18,cfg.colors.body);return q;}
function circle(x,y,r,roll,lift,t){
 oval(x,cfg.groundY+16,r*.79,18,cfg.colors.edge+'16');
 ctx.save();ctx.translate(x,y-lift);ctx.rotate(roll*cfg.ball.travel/r);
 ctx.beginPath();ctx.arc(0,0,r,0,Math.PI*2);ctx.fillStyle=cfg.colors.ball;ctx.fill();ctx.clip();
 ctx.fillStyle=cfg.colors.stripe;ctx.fillRect(-r*.26,-r*1.2,r*.32,r*2.4);
 ctx.strokeStyle='#9f402f22';ctx.lineWidth=2;
 for(let i=0;i<marks.length;i+=3){const m=marks[i];ctx.beginPath();ctx.moveTo(m.x%510-r,m.y%510-r);ctx.lineTo(m.x%510-r+5,m.y%510-r+2);ctx.stroke();}
 ctx.restore();
}
function character(p,t,ballX,lift){
 const ground=cfg.groundY;
 const velocity=Math.abs(performance(Math.min(16,t+.025)).x-performance(Math.max(0,t-.025)).x)/.05;
 const walking=clamp(velocity/80),step=t*9.5;
 const bounce=Math.abs(Math.sin(step))*7*walking;
 const hipY=ground-116+p.crouch-bounce;
 const topY=hipY-145;
 const shift=Math.sin(p.lean)*150;
 const rootLeft={x:p.x-32+shift,y:topY+25};
 const rootRight={x:p.x+35+shift,y:topY+24};
 const liftTarget={x:ballX-cfg.ball.radius*.79-12,y:ground-cfg.ball.radius*.44-lift};
 const pushTarget={x:ballX-cfg.ball.radius+3,y:ground-cfg.ball.radius-12};
 const solution=clamp((t-7.2)/1);
 const target={x:lerp(liftTarget.x,pushTarget.x,solution),y:lerp(liftTarget.y,pushTarget.y,solution)};
 oval(p.x,ground+16,95,12,cfg.colors.edge+'16');
 for(const side of [-1,1]){
  const s=step+(side===1?Math.PI:0),foot={x:p.x+side*45+Math.sin(s)*27*walking,y:ground-Math.max(0,Math.cos(s))*24*walking};
  const hip={x:p.x+side*30,y:hipY};const knee={x:lerp(hip.x,foot.x,.5)-17*walking,y:(hip.y+foot.y)/2};
  line([hip,knee,foot],cfg.colors.edge,26);line([hip,knee,foot],cfg.colors.body,18);oval(foot.x+12,foot.y,32,13,cfg.colors.body,-.05);
 }
 const leftRest={x:p.x-69,y:hipY+12};
 limb(rootLeft,{x:lerp(leftRest.x,target.x-14,p.reach),y:lerp(leftRest.y,target.y+18,p.reach)},1);
 ctx.save();ctx.translate(p.x,hipY);ctx.rotate(-p.lean);
 ctx.beginPath();ctx.moveTo(-54,7);ctx.bezierCurveTo(-73,-38,-75,-94,-42,-144);ctx.bezierCurveTo(-13,-161,38,-161,58,-131);ctx.bezierCurveTo(80,-96,68,-40,61,9);ctx.quadraticCurveTo(0,32,-54,7);ctx.fillStyle=cfg.colors.body;ctx.fill();
 ctx.strokeStyle=cfg.colors.edge;ctx.lineWidth=3;ctx.stroke();
 // Head is cut from the same paper; head tilt carries intention independently.
 ctx.translate(shift*.06,-190-p.pride*8);ctx.rotate(p.effort*.17-p.pride*.07);
 ctx.beginPath();ctx.moveTo(-72,-64);ctx.bezierCurveTo(-30,-85,55,-75,76,-28);ctx.bezierCurveTo(96,16,62,65,1,70);ctx.bezierCurveTo(-62,75,-97,20,-72,-64);ctx.fillStyle=cfg.colors.body;ctx.fill();ctx.stroke();
 ctx.save();ctx.clip();ctx.globalAlpha=.14;ctx.strokeStyle=cfg.colors.paper;ctx.lineWidth=1;
 for(let i=0;i<70;i++){const m=marks[i];ctx.beginPath();ctx.moveTo(m.x%160-80,m.y%160-80);ctx.lineTo(m.x%160-70,m.y%160-81);ctx.stroke();}ctx.restore();
 const blink=celIndex(t,[2.5,.13,3.7,.12,4.2,.14,5],{loop:true})%2===1;
 const eyeH=blink?2:Math.max(3,14-p.effort*8-p.pride*4);
 for(const x of [-12,34]){oval(x+p.gaze*7,-3-p.gaze*5,6,eyeH,cfg.colors.ink);line([{x:x-10,y:-30+p.effort*6},{x:x+10,y:-30-p.effort*5}],cfg.colors.ink,4);}
 ctx.strokeStyle=cfg.colors.ink;ctx.lineWidth=4;ctx.beginPath();
 if(p.pride>.3){ctx.arc(20,21,17,.15,Math.PI-.15);}else if(p.effort>.5){ctx.ellipse(20,29,6,9,0,0,Math.PI*2);}else{ctx.moveTo(12,31);ctx.quadraticCurveTo(21,33-p.gaze*4,28,29);}ctx.stroke();ctx.restore();
 const rest={x:p.x+85,y:hipY+1-p.pride*60};
 limb(rootRight,{x:lerp(rest.x,target.x,p.reach),y:lerp(rest.y,target.y,p.reach)},-1);
 // Effort marks appear only during strain, as acting accents rather than labels.
 if(p.effort>.65){ctx.globalAlpha=(p.effort-.65)/.35;for(let i=0;i<3;i++)line([{x:p.x+125+i*17,y:topY-150+i*8},{x:p.x+133+i*17,y:topY-165+i*8}],cfg.colors.edge,4);ctx.globalAlpha=1;}
}
function seek(time){
 if(!cfg)throw new Error('await motionReady');const t=clamp(time,0,16),p=performance(t);
 ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.fillStyle=cfg.colors.paper;ctx.fillRect(0,0,1920,1080);
 ctx.strokeStyle=cfg.colors.edge+'38';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(190,cfg.groundY+27);ctx.bezierCurveTo(640,cfg.groundY+21,1300,cfg.groundY+30,1770,cfg.groundY+24);ctx.stroke();
 const ballX=cfg.ball.startX+p.roll*cfg.ball.travel;
 const lift=14*Math.sin(clamp((t-3.4)/1.8)*Math.PI)*(t>3.4&&t<5.2?1:0);
 circle(ballX,cfg.groundY-cfg.ball.radius,cfg.ball.radius,p.roll,lift,t);
 character(p,t,ballX,lift);
 ctx.globalAlpha=.09;ctx.fillStyle=cfg.colors.edge;for(const m of marks)ctx.fillRect(m.x,m.y,m.s,m.s);ctx.globalAlpha=1;
}
window.motionReady=(async()=>{[cfg,performance]=await Promise.all([fetch('./content.json').then(r=>r.json()),fetch('./performance.json').then(r=>r.json()).then(keyframes)]);const rand=seededRandom(cfg.seed);marks=Array.from({length:1800},()=>({x:rand()*1920,y:rand()*1080,s:.4+rand()}));seek(0);})();window.seek=seek;
