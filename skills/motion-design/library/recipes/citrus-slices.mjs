import * as THREE from 'three';

/** Original citrus bands and juicy cut faces. No scene, clock or network ownership. */
export function createCitrusSlices({sliceCount=7,radius=1.35,seed=709,peelMaterial,cutImage}={}){
  if(!Number.isInteger(sliceCount)||sliceCount<3||sliceCount>11)throw new Error('sliceCount must be an integer from 3 to 11');
  if(!Number.isFinite(radius)||radius<=0||!Number.isFinite(seed))throw new Error('radius must be positive and seed finite');
  let randomState=seed>>>0;
  const random=()=>{randomState=(Math.imul(randomState,1664525)+1013904223)>>>0;return randomState/4294967296};
  const group=new THREE.Group();group.name='blood-orange';
  const geometries=[],materials=[],textures=[],canvases=[],slices=[];
  const canvas=(w,h=w)=>{const c=document.createElement('canvas');c.width=w;c.height=h;canvases.push(c);return c};
  const texture=(c,color=false)=>{const t=new THREE.CanvasTexture(c);if(color)t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;textures.push(t);return t};
  const ownMaterial=m=>{materials.push(m);return m};
  const add=(g,m,parent,name)=>{geometries.push(g);const o=new THREE.Mesh(g,m);o.name=name;o.castShadow=true;o.receiveShadow=true;parent.add(o);return o};
  const peelColor=canvas(1024,512),peelBump=canvas(1024,512),pc=peelColor.getContext('2d'),pb=peelBump.getContext('2d');
  const base=pc.createLinearGradient(0,0,1024,512);base.addColorStop(0,'#e96a0a');base.addColorStop(.35,'#f88412');base.addColorStop(.68,'#d84b13');base.addColorStop(1,'#ee7410');pc.fillStyle=base;pc.fillRect(0,0,1024,512);pb.fillStyle='#999';pb.fillRect(0,0,1024,512);
  for(let i=0;i<14000;i++){
    const x=random()*1024,y=random()*512,r=.45+random()*1.65;
    pc.fillStyle=`rgba(${105+Math.floor(random()*50)},${30+Math.floor(random()*30)},4,${.06+random()*.16})`;pc.beginPath();pc.ellipse(x,y,r,r*.8,0,0,Math.PI*2);pc.fill();
    pb.fillStyle=`rgb(${45+Math.floor(random()*55)},${45},${45})`;pb.beginPath();pb.arc(x,y,r,0,Math.PI*2);pb.fill();
    pc.strokeStyle='rgba(255,194,58,.19)';pc.lineWidth=.55;pc.beginPath();pc.arc(x,y+.2,r+.25,.12,2.8);pc.stroke();
  }
  const blush=pc.createRadialGradient(700,245,20,700,245,240);blush.addColorStop(0,'rgba(167,17,24,.47)');blush.addColorStop(1,'rgba(167,17,24,0)');pc.fillStyle=blush;pc.fillRect(0,0,1024,512);
  const peel=peelMaterial??ownMaterial(new THREE.MeshPhysicalMaterial({map:texture(peelColor,true),bumpMap:texture(peelBump),bumpScale:.028,roughness:.46,clearcoat:.12,clearcoatRoughness:.35}));
  // Irregular membrane boundaries are shared by neighboring cuts, preserving fruit identity.
  const boundaries=[.13];for(let i=1;i<=10;i++)boundaries.push(.13+i*Math.PI*2/10+.035*Math.sin(i*2.17));boundaries[10]=boundaries[0]+Math.PI*2;
  const cutMaterials=[];
  function cutMaterial(y,index){
    const S=1024,C=S/2,R=496,color=canvas(S),height=canvas(S),ctx=color.getContext('2d'),hc=height.getContext('2d');
    const shellRadius=Math.sqrt(Math.max(0,radius*radius-y*y)),innerRadius=Math.sqrt(Math.max(0,(radius-.095)**2-y*y));
    const pulpRatio=Math.min(.91,innerRadius/shellRadius),P=R*pulpRatio;
    ctx.fillStyle='#e56710';ctx.fillRect(0,0,S,S);hc.fillStyle='#888';hc.fillRect(0,0,S,S);
    ctx.beginPath();for(let i=0;i<=360;i++){const a=i*Math.PI/180,r=R*.972+2.4*Math.sin(a*17)+1.5*Math.sin(a*29);const x=C+Math.cos(a)*r,z=C+Math.sin(a)*r;if(i)ctx.lineTo(x,z);else ctx.moveTo(x,z)}ctx.closePath();ctx.fillStyle='#f5d1a3';ctx.fill();
    const palettes=['#aa1729','#cb2a2c','#e3412c','#a41426','#d1342a','#bb1d2e','#e3492a','#b61a2c','#cc3027','#941826'];
    for(let s=0;s<10;s++){
      const a=boundaries[s]+.014,b=boundaries[s+1]-.014,mid=(a+b)/2;
      const path=new Path2D();path.moveTo(C+Math.cos(mid)*19,C+Math.sin(mid)*19);
      path.quadraticCurveTo(C+Math.cos(a+.02)*P*.54,C+Math.sin(a+.02)*P*.54,C+Math.cos(a)*P,C+Math.sin(a)*P);
      for(let j=1;j<=24;j++){const t=a+(b-a)*j/24,r=P*(1+.009*Math.sin(t*43+index));path.lineTo(C+Math.cos(t)*r,C+Math.sin(t)*r)}
      path.quadraticCurveTo(C+Math.cos(b-.025)*P*.49,C+Math.sin(b-.025)*P*.49,C+Math.cos(mid)*19,C+Math.sin(mid)*19);path.closePath();
      ctx.save();hc.save();ctx.clip(path);hc.clip(path);
      const g=ctx.createRadialGradient(C,C,15,C,C,P);g.addColorStop(0,'#6f0c20');g.addColorStop(.45,palettes[s]);g.addColorStop(1,s%3===0?'#e76335':palettes[(s+1)%10]);ctx.fillStyle=g;ctx.fillRect(0,0,S,S);
      for(let i=0;i<360;i++){
        const ang=a+(b-a)*random(),rr=Math.sqrt(random())*P*.985,x=C+Math.cos(ang)*rr,z=C+Math.sin(ang)*rr;
        const len=6+random()*17,w=2.1+random()*4.2,rot=ang+(random()-.5)*.28;
        const blood=(Math.sin(x*.019+index*.38)+Math.cos(z*.015-s*.5))*.5,shade=random();
        const red=Math.floor(158+shade*81+blood*9),green=Math.floor(24+shade*34-blood*11),blue=Math.floor(28+shade*20+blood*12);
        ctx.save();ctx.translate(x,z);ctx.rotate(rot);ctx.fillStyle=`rgba(${red},${Math.max(9,green)},${blue},.72)`;ctx.beginPath();ctx.ellipse(0,0,len,w,0,0,Math.PI*2);ctx.fill();
        ctx.strokeStyle='rgba(255,183,149,.22)';ctx.lineWidth=.65;ctx.beginPath();ctx.ellipse(0,-.6,len*.82,w*.74,0,Math.PI,Math.PI*2);ctx.stroke();ctx.restore();
        hc.save();hc.translate(x,z);hc.rotate(rot);const hg=hc.createRadialGradient(0,0,0,0,0,len);hg.addColorStop(0,'#ddd');hg.addColorStop(1,'#777');hc.fillStyle=hg;hc.beginPath();hc.ellipse(0,0,len,w,0,0,Math.PI*2);hc.fill();hc.restore();
      }
      ctx.restore();hc.restore();
      // Thin translucent membranes with an irregular edge, never uniform target rings.
      ctx.strokeStyle='rgba(255,218,181,.50)';ctx.lineWidth=1.2;ctx.stroke(path);
    }
    ctx.beginPath();for(let j=0;j<=30;j++){const a=j/30*Math.PI*2,r=17+5*Math.sin(a*7)+2*Math.sin(a*13);if(j)ctx.lineTo(C+Math.cos(a)*r,C+Math.sin(a)*r);else ctx.moveTo(C+Math.cos(a)*r,C+Math.sin(a)*r)}ctx.closePath();ctx.fillStyle='#eecdaa';ctx.fill();
    // A small natural seed, located inside one segment rather than a decorative center.
    if(index%2===0){const a=boundaries[6]+.22,x=C+Math.cos(a)*P*.44,z=C+Math.sin(a)*P*.44;ctx.save();ctx.translate(x,z);ctx.rotate(a);ctx.beginPath();ctx.ellipse(0,0,18,8,0,0,Math.PI*2);ctx.fillStyle='#eed3ab';ctx.fill();ctx.strokeStyle='#a97956';ctx.lineWidth=1.5;ctx.stroke();ctx.restore();}
    // A caller-owned decoded image may supply the cut appearance. Slight overscan
    // puts the photographed uneven peel edge beyond this geometric circle.
    // Paired neighboring faces share the same generated material and orientation.
    if(cutImage){
      ctx.drawImage(cutImage,-S*.035,-S*.025,S*1.07,S*1.07);
      const pixels=ctx.getImageData(0,0,S,S),data=pixels.data;
      for(let p=0;p<data.length;p+=4){const h=Math.round(92+.25*data[p]+.18*data[p+1]+.08*data[p+2]);data[p]=data[p+1]=data[p+2]=h;data[p+3]=255}
      hc.putImageData(pixels,0,0);
    }
    const mat=ownMaterial(new THREE.MeshPhysicalMaterial({map:texture(color,true),bumpMap:texture(height),bumpScale:cutImage?.009:.027,roughness:.29,metalness:0,clearcoat:.32,clearcoatRoughness:.21,transmission:.018,thickness:.15,ior:1.36,envMapIntensity:.38}));cutMaterials.push(mat);return mat;
  }
  const cuts=Array.from({length:sliceCount+1},(_,i)=>-radius+2*radius*i/sliceCount);
  const faces=cuts.slice(1,-1).map((y,i)=>cutMaterial(y,i));
  for(let i=0;i<sliceCount;i++){
    const low=cuts[i],high=cuts[i+1],center=(low+high)/2,part=new THREE.Group();part.name='slice-'+i;group.add(part);
    const thetaTop=Math.acos(high/radius),thetaBottom=Math.acos(low/radius);
    const outer=new THREE.SphereGeometry(radius,144,Math.max(8,Math.round(72*(thetaBottom-thetaTop)/Math.PI)),0,Math.PI*2,thetaTop,thetaBottom-thetaTop);
    const pos=outer.attributes.position,uv=outer.attributes.uv;
    for(let v=0;v<pos.count;v++){const x=pos.getX(v),y=pos.getY(v),z=pos.getZ(v);uv.setY(v,1-Math.acos(THREE.MathUtils.clamp(y/radius,-1,1))/Math.PI)}
    outer.translate(0,-center,0);add(outer,peel,part,'dimpled-peel');
    for(const [y,top,material]of [[low,false,faces[i-1]],[high,true,faces[i]]]){
      if(!material)continue;
      const r=Math.sqrt(radius*radius-y*y)*.9994,g=new THREE.CircleGeometry(r,144);g.rotateX(top?-Math.PI/2:Math.PI/2);if(!top)for(let v=0;v<g.attributes.uv.count;v++)g.attributes.uv.setY(v,1-g.attributes.uv.getY(v));g.translate(0,y-center,0);add(g,material,part,top?'upper-cut':'lower-cut');
    }
    part.position.y=center;slices.push({group:part,center,index:i});
  }
  const stemMat=ownMaterial(new THREE.MeshStandardMaterial({color:'#6e4823',roughness:.85}));
  const stem=add(new THREE.SphereGeometry(.105,20,12),stemMat,slices.at(-1).group,'natural-stem-scar');stem.scale.set(1,.28,1);stem.position.y=radius-slices.at(-1).center-.015;
  let disposed=false;
  function setState({separation=0,spiral=1,rotation=0}={}){
    if(disposed)throw new Error('Citrus recipe disposed');
    if(![separation,spiral,rotation].every(Number.isFinite))throw new Error('state values must be finite');
    const open=THREE.MathUtils.clamp(separation,0,1),turn=THREE.MathUtils.clamp(spiral,0,1.4),mid=(sliceCount-1)/2;
    slices.forEach(({group:part,center,index:i})=>{
      const angle=(i-mid)*.78*turn+rotation,spread=open*1.10*turn;
      part.position.set(Math.sin(angle)*spread,center+(i-mid)*.29*open,Math.cos(angle)*spread-spread*.25);
      part.rotation.set(open*(i===sliceCount-1?-1.40:.23+.025*Math.sin(i)),open*(i-mid)*.12,open*.035*Math.sin(i*1.7));
    });
  }
  function dispose(){if(disposed)return;disposed=true;geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());canvases.forEach(c=>{c.width=c.height=1});group.removeFromParent()}
  setState();return{group,setState,dispose,parts:slices.map(s=>s.group)};
}
