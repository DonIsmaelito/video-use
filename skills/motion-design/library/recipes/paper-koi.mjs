/** Original Canvas paper koi. Geometry and pose controls only; caller owns time and staging. */
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v);return v*v*(3-2*v)};
const mix=(a,b,t)=>a+(b-a)*t;
const blendPoint=(a,b,t)=>[mix(a[0],b[0],t),mix(a[1],b[1],t)];
const polygon=(ctx,points)=>{ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath()};

export function createPaperKoi({seed=1978,red='#dc3927',vermilion='#ef5136',dark='#a82221',cream='#fff0d4'}={}){
  const grain=document.createElement('canvas');grain.width=grain.height=256;
  const gg=grain.getContext('2d');let randomState=seed>>>0;
  const random=()=>{randomState=(1664525*randomState+1013904223)>>>0;return randomState/4294967296};
  gg.fillStyle='rgba(255,248,220,.035)';
  for(let i=0;i<2100;i++)gg.fillRect(random()*256,random()*256,.35+random()*1.25,.35+random()*.7);
  for(let i=0;i<170;i++){const x=random()*256,y=random()*256;gg.strokeStyle=i%2?'rgba(255,240,216,.09)':'rgba(91,19,13,.045)';gg.lineWidth=.45;gg.beginPath();gg.moveTo(x,y);gg.lineTo(x+2+random()*7,y+(random()-.5)*2);gg.stroke()}
  const finalOutline=[[270,0],[248,42],[190,80],[115,113],[15,122],[-100,92],[-195,45],[-238,15],[-246,0],[-238,-15],[-195,-45],[-100,-92],[15,-122],[115,-113],[190,-80],[248,-42]];
  const square=[[180,0],[180,90],[180,180],[90,180],[0,180],[-90,180],[-180,180],[-180,90],[-180,0],[-180,-90],[-180,-180],[-90,-180],[0,-180],[90,-180],[180,-180],[180,-90]];
  const palette=[vermilion,red,'#d63025','#cb3025','#e5402b','#c32c25',dark,'#c92923','#ba2723','#c52c25','#d73626','#f05235','#ee4a2e','#e84129','#f36945',vermilion];

  function draw(ctx,{x=0,y=0,scale=1,rotation=0,unfold=1,swim=0,phase=0,bend=0,finLift=0,tailSweep=0,shadow=1}={}){
    unfold=clamp(unfold);swim=clamp(swim);bend=clamp(bend,-1,1);
    const bodyOpen=smooth(unfold),finOpen=smooth((unfold-.3)/.54),tailOpen=smooth((unfold-.52)/.48);
    const constructionHinge=Math.pow(Math.sin(Math.PI*bodyOpen),1.3);
    const warp=([px,py])=>{
      const rear=clamp((230-px)/640);
      const foldProjection=py<0?Math.cos(constructionHinge*1.49):1;
      return [px,py*foldProjection+bend*rear*rear*93+swim*Math.sin(phase-rear*2.7)*rear*rear*42];
    };
    ctx.save();ctx.translate(x,y);ctx.rotate(rotation);ctx.scale(scale,scale);
    const texture=ctx.createPattern(grain,'repeat');
    const face=(points,color,{line=true,alpha=1}={})=>{
      const ps=points.map(warp);ctx.save();ctx.globalAlpha=alpha;polygon(ctx,ps);ctx.fillStyle=color;ctx.fill();
      ctx.save();ctx.clip();ctx.fillStyle=texture;ctx.fillRect(-520,-380,1050,760);ctx.restore();
      if(line){ctx.lineWidth=.75;ctx.strokeStyle='rgba(102,22,12,.16)';ctx.stroke()}ctx.restore();
    };
    const outline=finalOutline.map((p,i)=>blendPoint(square[i],p,bodyOpen));
    const silhouette=[...outline.map(warp)];
    ctx.save();ctx.shadowColor=`rgba(91,63,29,${.22*shadow})`;ctx.shadowBlur=20+unfold*9;ctx.shadowOffsetX=-5;ctx.shadowOffsetY=13+unfold*4;polygon(ctx,silhouette);ctx.fillStyle=red;ctx.fill();ctx.restore();

    // Tail opens from a narrow packet into two tapered, differently folded lobes.
    const tailRoot=mix(-174,-235,bodyOpen),tailAngle=tailSweep*.16+swim*Math.sin(phase-2.4)*.15;
    const tailPoint=([px,py])=>{
      const dx=(px+235)*tailOpen,dy=py*tailOpen;
      return [tailRoot+dx*Math.cos(tailAngle)-dy*Math.sin(tailAngle),dx*Math.sin(tailAngle)+dy*Math.cos(tailAngle)];
    };
    if(tailOpen>.001){
      const tailPanels=[
        [[-235,0],[-306,-39],[-405,-128],[-377,-16],[-333,14]],
        [[-235,0],[-333,14],[-387,120],[-403,138],[-312,48]],
        [[-306,-39],[-405,-128],[-350,-74],[-333,14]],
        [[-333,14],[-387,120],[-341,63],[-312,48]],
        [[-235,0],[-312,48],[-333,14],[-306,-39]]
      ];
      tailPanels.forEach((p,i)=>face(p.map(tailPoint),[red,vermilion,'#f76a47',dark,'#c72d22'][i]));
      [[-405,-128],[-387,120]].forEach((tip,j)=>{ctx.beginPath();ctx.moveTo(...warp(tailPoint([-239,0])));ctx.lineTo(...warp(tailPoint(j?[-341,63]:[-350,-74])));ctx.lineTo(...warp(tailPoint(tip)));ctx.strokeStyle='rgba(255,217,173,.5)';ctx.lineWidth=1.0;ctx.stroke()});
    }

    // Pectoral fins share exact body anchors. Projection across a hinge reveals paper thickness.
    for(const side of [-1,1]){
      const fold=finOpen*(.87+.13*Math.sin(phase+side*.8)*swim),lift=clamp(finLift,-1,1);
      const root=[95,side*mix(124,82,bodyOpen)];
      const tip=[-27,side*(82+118*fold*(1+.09*lift))];
      const back=[-72,side*(82+49*fold)];
      const joint=[38,side*mix(124,108,bodyOpen)];
      if(finOpen>.001){face([root,tip,back,joint],side<0?'#f4714f':'#ba2621');face([root,tip,[-16,side*(82+73*fold)],joint],side<0?vermilion:red);face([tip,back,[-16,side*(82+73*fold)]],side<0?cream:'#e95336')}
    }

    // Persistent crease network: each perimeter segment meets the same raised spine.
    for(let i=0;i<16;i++){
      const next=(i+1)%16;
      const ridge=[mix(0,(finalOutline[i][0]+finalOutline[next][0])*.27,bodyOpen),mix(0,-8,bodyOpen)];
      face([outline[i],outline[next],ridge],palette[i]);
    }
    // Long asymmetric folded planes keep an anatomical carp silhouette rather than a symbol.
    if(bodyOpen>.01){
      const p=(point)=>blendPoint([point[0]*.48,point[1]*.32],point,bodyOpen);
      face([[242,0],[136,34],[-117,11],[-227,0],[4,-15]].map(p),'#ed4930',{alpha:bodyOpen});
      face([[232,0],[139,-32],[30,-73],[-113,-47],[-212,-11],[-79,-8],[65,-7]].map(p),'#f35a38',{alpha:bodyOpen});
      face([[138,34],[28,78],[-111,47],[-211,11],[-117,11]].map(p),'#c82d23',{alpha:bodyOpen});
      face([[202,52],[145,93],[108,108],[126,66]].map(p),cream,{alpha:bodyOpen*.94});
      face([[116,-112],[20,-122],[-80,-95],[2,-90],[74,-81]].map(p),'#fcdfbd',{alpha:bodyOpen*.92});
      face([[-140,-6],[-14,-31],[88,-16],[35,0]].map(p),'#9e2723',{alpha:bodyOpen});
      face([[-140,-6],[-14,-31],[26,-16]].map(p),'#f16a47',{alpha:bodyOpen});
    }
    // Original eyes, operculum creases and paired paper barbels identify the koi head.
    const faceReveal=smooth((unfold-.66)/.2);
    if(faceReveal>0){ctx.save();ctx.globalAlpha=faceReveal;
      for(const side of [-1,1]){
        const eye=warp([215,side*48]);ctx.fillStyle=cream;ctx.beginPath();ctx.ellipse(eye[0],eye[1],12,9,side*.27,0,Math.PI*2);ctx.fill();ctx.fillStyle='#27241f';ctx.beginPath();ctx.ellipse(eye[0]+3,eye[1],6.2,6.8,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#fff5de';ctx.beginPath();ctx.arc(eye[0]+4,eye[1]-2,1.7,0,Math.PI*2);ctx.fill();
        const a=warp([169,side*34]),b=warp([159,side*76]);ctx.beginPath();ctx.moveTo(...a);ctx.quadraticCurveTo(...warp([145,side*48]),...b);ctx.strokeStyle='rgba(117,26,20,.48)';ctx.lineWidth=1.2;ctx.stroke();
        const m=warp([256,side*18]);ctx.beginPath();ctx.moveTo(...m);ctx.quadraticCurveTo(...warp([284,side*17]),...warp([290,side*39]));ctx.strokeStyle='#c23026';ctx.lineWidth=3;ctx.lineCap='round';ctx.stroke();
      }
      const mouth=warp([263,0]);ctx.beginPath();ctx.moveTo(mouth[0]-1,mouth[1]-11);ctx.quadraticCurveTo(mouth[0]+6,mouth[1],mouth[0]-1,mouth[1]+11);ctx.strokeStyle='#9c2926';ctx.lineWidth=1.8;ctx.stroke();ctx.restore();
    }
    // Fine scoring on the still-folded square remains tied to its original center.
    if(unfold<.4){ctx.save();ctx.globalAlpha=(1-unfold/.4)*.36;ctx.strokeStyle='#ffb184';ctx.lineWidth=.8;ctx.beginPath();ctx.moveTo(...warp(outline[2]));ctx.lineTo(...warp(outline[10]));ctx.moveTo(...warp(outline[6]));ctx.lineTo(...warp(outline[14]));ctx.stroke();ctx.restore()}
    ctx.restore();
  }
  return {draw,controls:['unfold','swim','phase','bend','finLift','tailSweep'],dispose(){grain.width=grain.height=1}};
}
