import * as THREE from 'three';
const clamp=v=>Math.max(0,Math.min(1,Number.isFinite(v)?v:0));
const ease=v=>{v=clamp(v);return v*v*(3-2*v)};
const V=(x,y,z)=>new THREE.Vector3(x,y,z);
function smoothCoincidentNormals(g){const p=g.attributes.position,n=g.attributes.normal,sums=new Map(),keys=[];for(let i=0;i<p.count;i++){const key=[p.getX(i),p.getY(i),p.getZ(i)].map(v=>Math.round(v*1e5)).join(',');keys.push(key);const sum=sums.get(key)||V(0,0,0);sum.add(V(n.getX(i),n.getY(i),n.getZ(i)));sums.set(key,sum)}for(let i=0;i<p.count;i++){const v=sums.get(keys[i]).clone().normalize();n.setXYZ(i,v.x,v.y,v.z)}n.needsUpdate=true}
function roundRect(w,h,r){const s=new THREE.Shape(),x=-w/2,y=-h/2;s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s}

/** Original telephone assembly with a connected helical cord. Caller owns time/staging. */
export function createRotaryTelephone(){
 const group=new THREE.Group(),base=new THREE.Group(),handset=new THREE.Group(),dial=new THREE.Group();group.add(base,handset,dial);
 const red=new THREE.MeshPhysicalMaterial({color:'#ad0b13',roughness:.24,metalness:.03,clearcoat:.8,clearcoatRoughness:.17});
 const dark=new THREE.MeshStandardMaterial({color:'#251313',roughness:.48});
 const chrome=new THREE.MeshStandardMaterial({color:'#eee4cf',metalness:.75,roughness:.24});
 const ivory=new THREE.MeshStandardMaterial({color:'#f6e3b8',metalness:.12,roughness:.32});
 const cordMat=new THREE.MeshStandardMaterial({color:'#501419',roughness:.31,metalness:.08});
 const ownedMaterials=[red,dark,chrome,ivory,cordMat],geometries=[];
 const add=(parent,geo,mat,pos)=>{geometries.push(geo);const m=new THREE.Mesh(geo,mat);if(pos)m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m};
 const bodyGeo=new THREE.ExtrudeGeometry(roundRect(3.65,2.55,.6),{depth:.86,steps:1,bevelEnabled:true,bevelSegments:5,bevelSize:.14,bevelThickness:.13,curveSegments:24});bodyGeo.rotateX(-Math.PI/2);const pa=bodyGeo.attributes.position;for(let i=0;i<pa.count;i++){const y=pa.getY(i),z=pa.getZ(i);pa.setY(i,y*(1-.22*(z+1.3)/2.6))}bodyGeo.computeVertexNormals();smoothCoincidentNormals(bodyGeo);add(base,bodyGeo,red,[0,.15,0]);
 for(const x of [-1.28,1.28])for(const z of [-.75,.75])add(base,new THREE.CylinderGeometry(.18,.18,.10,20),dark,[x,.02,z]);
 for(const x of [-1.27,1.27]){add(base,new THREE.CylinderGeometry(.12,.16,.28,24),red,[x,1.18,-.66]);add(base,new THREE.CylinderGeometry(.07,.07,.08,20),chrome,[x,1.35,-.66])}
 const cordPort=add(base,new THREE.CylinderGeometry(.075,.075,.15,20),dark,[-1.88,.42,-.38]);cordPort.rotation.z=Math.PI/2;
 const mount=add(dial,new THREE.CylinderGeometry(.87,.92,.08,96),dark);mount.rotation.x=Math.PI/2;
 const ring=new THREE.Shape();ring.absarc(0,0,.81,0,Math.PI*2,false);for(let i=0;i<10;i++){const a=Math.PI*.12+i*Math.PI*2/10;const hole=new THREE.Path();hole.absarc(Math.cos(a)*.57,Math.sin(a)*.57,.119,0,Math.PI*2,true);ring.holes.push(hole)}
 const turntable=new THREE.Group();dial.add(turntable);add(turntable,new THREE.ExtrudeGeometry(ring,{depth:.045,bevelEnabled:true,bevelSize:.008,bevelThickness:.008,bevelSegments:2,steps:1,curveSegments:48}),ivory,[0,0,.054]);
 add(turntable,new THREE.CylinderGeometry(.34,.34,.055,72),chrome,[0,0,.11]).rotation.x=Math.PI/2;add(turntable,new THREE.CircleGeometry(.28,72),ivory,[0,0,.147]);
 const stop=add(dial,new THREE.TorusGeometry(.12,.033,12,24,Math.PI*1.35),chrome,[.68,-.36,.18]);stop.rotation.z=-.5;
 const handleCurve=new THREE.CatmullRomCurve3([V(-1.57,-.37,0),V(-1.54,-.12,-.04),V(-1.31,.20,-.05),V(-.73,.36,-.05),V(0,.38,-.05),V(.73,.36,-.05),V(1.31,.20,-.05),V(1.54,-.12,-.04),V(1.57,-.37,0)]);
 const hg=new THREE.TubeGeometry(handleCurve,100,.24,20,false),hp=hg.attributes.position;
 for(let i=0;i<=100;i++){const center=handleCurve.getPointAt(i/100),r=1+.55*Math.pow(Math.abs(i/100-.5)*2,5);for(let j=0;j<=20;j++){const n=i*21+j;hp.setXYZ(n,center.x+(hp.getX(n)-center.x)*r,center.y+(hp.getY(n)-center.y)*r,center.z+(hp.getZ(n)-center.z)*r)}}hg.computeVertexNormals();add(handset,hg,red);
 for(const x of [-1.57,1.57]){add(handset,new THREE.CylinderGeometry(.35,.35,.08,40),red,[x,-.35,0]);add(handset,new THREE.CylinderGeometry(.29,.29,.02,40),dark,[x,-.399,0]);for(let k=0;k<8;k++){const a=k*Math.PI/4;add(handset,new THREE.CylinderGeometry(.025,.025,.025,8),ivory,[x+Math.cos(a)*.19,-.414,Math.sin(a)*.19])}}
 const cord=new THREE.Mesh(new THREE.BufferGeometry(),cordMat);group.add(cord);cord.frustumCulled=false;cord.castShadow=true;
 function setState({assembly=1,handsetLift=0,dialTurn=0,ring=0,cordLoop=1,phase=0}={}){
  assembly=clamp(assembly);handsetLift=clamp(handsetLift);cordLoop=clamp(cordLoop);ring=clamp(ring);phase=Number.isFinite(phase)?phase:0;dialTurn=Number.isFinite(dialTurn)?dialTurn:0;
  const a=ease(assembly),bounce=Math.sin(a*Math.PI*3)*Math.sin(a*Math.PI)*.12;
  base.scale.set(.82+.18*a,.18+.82*a+bounce, .86+.14*a);
  handset.position.set(Math.sin(phase*4.6)*ring*.06,1.69+handsetLift*.68,-.64);handset.rotation.set(handsetLift*.18,handsetLift*-.2,handsetLift*-.12+Math.sin(phase*4.6)*ring*.05);
  dial.position.set(0,1.02+(1-a)*.6,.39);dial.rotation.set(-Math.PI/2+.20,0,(1-a)*-.75);turntable.rotation.z=dialTurn;
  const start=V(-1.70,-.16,.09).applyEuler(handset.rotation).add(handset.position),loop=cordLoop;
  const path=new THREE.CatmullRomCurve3([start,V(-2.03,.73,-.15),V(-2.23-loop*.45,.14,.48+loop*.6),V(-2.23-loop*1.45,.14,.43+loop*1.25),V(-2.33-loop*1.47,.14,-.3-loop*.52),V(-2.1-loop*.58,.16,-.61-loop*.61),V(-1.92,.3,-.71),V(-1.94,.42,-.38).multiply(base.scale)]);
  const ps=[],up=V(0,1,0),side=V(1,0,0),n=V(0,0,1);for(let i=0;i<=520;i++){const u=i/520,p=path.getPointAt(u),t=path.getTangentAt(u);side.crossVectors(t,up).normalize();if(side.lengthSq()<.01)side.set(1,0,0);n.crossVectors(t,side).normalize();const end=ease(u/.035)*ease((1-u)/.035);p.addScaledVector(side,Math.cos(u*Math.PI*2*33)*.061*end).addScaledVector(n,Math.sin(u*Math.PI*2*33)*.061*end);ps.push(p)}
  cord.geometry.dispose();cord.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ps),640,.026,6,false);
 }
 setState();
 return {group,base,handset,dial,cord,setState,controls:['assembly','handsetLift','dialTurn','ring','cordLoop','phase'],dispose(){for(const g of geometries)g.dispose();cord.geometry.dispose();for(const m of ownedMaterials)m.dispose();group.removeFromParent()}};
}
