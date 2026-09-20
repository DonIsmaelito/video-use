import * as THREE from 'three';

/** Original attached zipper/fabric geometry and a continuous ribbon river.
 * The host owns renderer, environment, camera, clock and any supplied materials. */
export function createColorZipper({length=8.4,toothCount=46,colors=['#ae0f49','#f23e45','#ff941f','#bad830','#0bc5cb','#3d70d7','#a43aab'],metalMaterial,fabricMaterial}={}){
  if(!Number.isFinite(length)||length<4||length>14)throw new Error('length must be finite, 4–14');
  if(!Number.isInteger(toothCount)||toothCount<20||toothCount>100)throw new Error('toothCount must be an integer, 20–100');
  if(!Array.isArray(colors)||colors.length<3||colors.length>12)throw new Error('colors needs 3–12 entries');
  const group=new THREE.Group(),geometries=[],materials=[],textures=[],canvases=[];group.name='color-zipper';
  const ownM=m=>(materials.push(m),m),ownG=g=>(geometries.push(g),g);
  const metal=metalMaterial??ownM(new THREE.MeshPhysicalMaterial({color:'#9aaac0',metalness:1,roughness:.38,clearcoat:.1,clearcoatRoughness:.35,envMapIntensity:.20}));
  const canvas=document.createElement('canvas');canvas.width=canvas.height=512;canvases.push(canvas);const ctx=canvas.getContext('2d');ctx.fillStyle='#77818f';ctx.fillRect(0,0,512,512);
  for(let i=0;i<512;i+=4){ctx.strokeStyle=i%8?'#8d969f':'#626e7e';ctx.lineWidth=1.25;ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i,512);ctx.stroke();ctx.strokeStyle=i%8?'#a5adb4':'#657486';ctx.beginPath();ctx.moveTo(0,i);ctx.lineTo(512,i);ctx.stroke()}
  const weave=new THREE.CanvasTexture(canvas);weave.wrapS=weave.wrapT=THREE.RepeatWrapping;weave.repeat.set(16,12);textures.push(weave);
  const fabric=fabricMaterial??ownM(new THREE.MeshPhysicalMaterial({color:'#081127',roughness:.91,bumpMap:weave,bumpScale:.009,sheen:.35,sheenColor:new THREE.Color('#344765'),sheenRoughness:.7,side:THREE.DoubleSide}));
  const tape=ownM(new THREE.MeshStandardMaterial({color:'#122440',roughness:.79,bumpMap:weave,bumpScale:.007,side:THREE.DoubleSide}));
  const thread=ownM(new THREE.MeshStandardMaterial({color:'#65728a',roughness:.96}));
  function grid(nx,ny,mat,name){const g=ownG(new THREE.PlaneGeometry(1,1,nx,ny));const m=new THREE.Mesh(g,mat);m.name=name;m.castShadow=true;m.receiveShadow=true;group.add(m);return{g,m,nx,ny};}
  const panels=[1,-1].map(side=>({side,fabric:grid(144,30,fabric,'midnight-panel'),tape:grid(144,4,tape,'woven-zipper-tape')}));
  function rounded(x,y,w,h,r){const s=new THREE.Shape();s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s;}
  function extrude(shape,depth=.065,bevel=.015){return ownG(new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:bevel,bevelThickness:bevel,curveSegments:12}));}
  function mesh(g,m,parent=group){const o=new THREE.Mesh(g,m);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
  const pitch=length/toothCount,unit=pitch/.183;
  const ts=new THREE.Shape();ts.moveTo(-.065,.13);ts.lineTo(.065,.13);ts.lineTo(.065,.04);ts.lineTo(.034,.015);ts.lineTo(.05,-.105);ts.quadraticCurveTo(.05,-.14,.02,-.14);ts.lineTo(-.02,-.14);ts.quadraticCurveTo(-.05,-.14,-.05,-.105);ts.lineTo(-.034,.015);ts.lineTo(-.065,.04);ts.closePath();
  const teethGeometry=extrude(ts,.058,.01);teethGeometry.scale(unit,1,1);
  const teeth=[1,-1].map(side=>{const m=new THREE.InstancedMesh(teethGeometry,metal,toothCount);m.castShadow=true;m.receiveShadow=true;group.add(m);return{side,m}});
  const stitchGeometry=ownG(new THREE.CapsuleGeometry(.006,.047,2,6));stitchGeometry.rotateZ(Math.PI/2);const stitches=[1,-1].map(side=>{const m=new THREE.InstancedMesh(stitchGeometry,thread,74);group.add(m);return{side,m}});
  const slider=new THREE.Group();slider.name='silver-slider';group.add(slider);
  const bodyShape=new THREE.Shape();bodyShape.moveTo(-.35,-.31);bodyShape.quadraticCurveTo(-.43,0,-.35,.31);bodyShape.lineTo(.24,.205);bodyShape.quadraticCurveTo(.36,0,.24,-.205);bodyShape.closePath();mesh(extrude(bodyShape,.13,.035),metal,slider);
  const under=mesh(extrude(bodyShape,.055,.022),metal,slider);under.position.z=-.13;
  const hinge=mesh(ownG(new THREE.CylinderGeometry(.067,.067,.28,24)),metal,slider);hinge.rotation.x=Math.PI/2;hinge.position.set(.01,0,.25);
  const tabPivot=new THREE.Group();tabPivot.position.set(.01,0,.27);slider.add(tabPivot);
  const tabShape=rounded(.0,-.235,1.08,.47,.145);const hole=new THREE.Path();hole.moveTo(.32,-.10);hole.lineTo(.32,.10);hole.quadraticCurveTo(.32,.14,.37,.14);hole.lineTo(.83,.14);hole.quadraticCurveTo(.90,.14,.90,.07);hole.lineTo(.90,-.07);hole.quadraticCurveTo(.90,-.14,.83,-.14);hole.lineTo(.37,-.14);hole.quadraticCurveTo(.32,-.14,.32,-.10);tabShape.holes.push(hole);mesh(extrude(tabShape,.054,.024),metal,tabPivot);
  const ribs=[];for(const y of[-.105,.105]){const r=mesh(ownG(new THREE.CapsuleGeometry(.012,.27,2,6)),metal,tabPivot);r.rotation.z=Math.PI/2;r.position.set(.16,y,.076);ribs.push(r)}
  const rivers=colors.map((color,i)=>grid(192,8,ownM(new THREE.MeshPhysicalMaterial({color,roughness:.53,metalness:0,clearcoat:.08,clearcoatRoughness:.45,envMapIntensity:.35,side:THREE.DoubleSide})),`color-ribbon-${i}`));
  const matrix=new THREE.Matrix4(),position=new THREE.Vector3(),quaternion=new THREE.Quaternion(),scale=new THREE.Vector3(1,1,1),axis=new THREE.Vector3(0,0,1);let disposed=false;
  const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
  function setState({open=0,flow=0,spread=1.45,pullTilt=.38}={}){
    if(disposed)throw new Error('Color zipper disposed');if(![open,flow,spread,pullTilt].every(Number.isFinite))throw new Error('state values must be finite');
    open=clamp(open);spread=THREE.MathUtils.clamp(spread,.45,1.8);const front=-length/2+length*open,activation=smooth(open/.055);
    const gap=x=>spread*smooth((front-x-.20)/1.9)*activation;
    const lift=x=>.10+.17*smooth((front-x)/1.6)*activation;
    for(const {side,fabric,tape}of panels){
      for(const [part,isTape]of[[fabric,false],[tape,true]]){const a=part.g.attributes.position;let n=0;for(let j=0;j<=part.ny;j++)for(let i=0;i<=part.nx;i++){
        const x=(i/part.nx-.5)*(length+5.2),v=j/part.ny,g=gap(x),edge=lift(x),y=isTape?g+.07+v*.47:g+v*(6-g);
        const z=isTape?edge+.018+Math.sin(v*Math.PI)*.014:.1+(edge-.1)*Math.exp(-v*7)+.022*Math.sin(x*1.5+v*5)*Math.sin(v*Math.PI)*activation;
        a.setXYZ(n++,x,side*y,z);
      }a.needsUpdate=true;part.g.computeVertexNormals();}
    }
    for(const {side,m}of teeth){for(let i=0;i<toothCount;i++){const x=-length/2+(i+.3+(side<0?.5:0))*pitch,g=gap(x),derivative=(gap(x+.005)-gap(x-.005))/.01;position.set(x,side*(g+.103),lift(x)+.038);quaternion.setFromAxisAngle(axis,Math.atan2(side*derivative,1)+(side<0?Math.PI:0));matrix.compose(position,quaternion,scale);m.setMatrixAt(i,matrix)}m.instanceMatrix.needsUpdate=true;}
    for(const {side,m}of stitches){for(let i=0;i<74;i++){const x=(i/73-.5)*(length+.15),d=(gap(x+.005)-gap(x-.005))/.01;position.set(x,side*(gap(x)+.59),.109+(lift(x)-.1)*Math.exp(-.59/(6-gap(x))*7)+.022*Math.sin(x*1.5+.59/(6-gap(x))*5)*Math.sin(.59/(6-gap(x))*Math.PI)*activation);quaternion.setFromAxisAngle(axis,Math.atan2(side*d,1));matrix.compose(position,quaternion,scale);m.setMatrixAt(i,matrix)}m.instanceMatrix.needsUpdate=true;}
    slider.position.set(front,0,.175);slider.rotation.z=0;tabPivot.rotation.set(0,-THREE.MathUtils.clamp(pullTilt,-.2,.8),.055*Math.sin(flow*.8));
    const riverWidth=4.1,band=riverWidth/colors.length;
    rivers.forEach((part,k)=>{const a=part.g.attributes.position;let n=0;for(let j=0;j<=part.ny;j++)for(let i=0;i<=part.nx;i++){const x=(i/part.nx-.5)*(length+5.8),v=j/part.ny;const wave=.30*Math.sin(x*.86-flow)+.10*Math.sin(x*1.66-flow*.57+k*.23);const y=-riverWidth/2+(k+v)*band+wave;const z=-.17+k*.010+.038*Math.sin(x*1.02-flow*.9+k*.28)+.026*Math.sin(v*Math.PI);a.setXYZ(n++,x,y,z)}a.needsUpdate=true;part.g.computeVertexNormals();});
  }
  function dispose(){if(disposed)return;disposed=true;geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());canvases.forEach(c=>{c.width=c.height=1});group.removeFromParent();group.clear();}
  setState();return{group,setState,dispose,parts:{panels,teeth,slider,tabPivot,rivers,stitches}};
}
