import * as THREE from 'three';
export function createBeachUmbrella({panels=12,radius=1.9}={}){
 if(!Number.isInteger(panels)||panels<8||panels>24||panels%2)throw new Error('panels must be an even integer from8 to24');
 if(!Number.isFinite(radius)||radius<=0)throw new Error('radius must be positive');
 const group=new THREE.Group(),geometrySet=new Set(),materialSet=new Set(),TAU=Math.PI*2;
 const mat=(color,roughness=.55,extra={})=>{const m=new THREE.MeshPhysicalMaterial({color,roughness,metalness:0,clearcoat:.16,clearcoatRoughness:.4,...extra});materialSet.add(m);return m;};
 const coral=mat('#df5a4d'),cream=mat('#fff1d2'),wood=mat('#d4b58a',.47),metal=mat('#d4c5a6',.3,{metalness:.55}),hemMat=mat('#f9e8c2',.6);
 function mesh(g,m,parent=group){geometrySet.add(g);const o=new THREE.Mesh(g,m);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
 function rod(m,r){const o=mesh(new THREE.CylinderGeometry(r,r,1,12),m);return o;}
 const unitY=new THREE.Vector3(0,1,0);function join(o,a,b){o.position.copy(a).add(b).multiplyScalar(.5);const d=b.clone().sub(a);o.scale.y=d.length();o.quaternion.setFromUnitVectors(unitY,d.normalize());}
 function tube(samples,radial,tubeRadius,m){
  const g=new THREE.BufferGeometry(),pos=new Float32Array((samples+1)*(radial+1)*3),indices=[];
  for(let i=0;i<samples;i++)for(let j=0;j<radial;j++){const a=i*(radial+1)+j,b=a+radial+1;indices.push(a,b,a+1,b,b+1,a+1)}
  g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setIndex(indices);const o=mesh(g,m);
  o.update=fn=>{for(let i=0;i<=samples;i++){const t=i/samples,p=fn(t),v=fn(Math.min(1,t+.001)).sub(fn(Math.max(0,t-.001))).normalize();let n=new THREE.Vector3().crossVectors(v,new THREE.Vector3(0,1,0));if(n.lengthSq()<1e-6)n=new THREE.Vector3(1,0,0);n.normalize();const b=new THREE.Vector3().crossVectors(v,n).normalize();for(let j=0;j<=radial;j++){const a=j/radial*TAU,k=(i*(radial+1)+j)*3,q=p.clone().addScaledVector(n,Math.cos(a)*tubeRadius).addScaledVector(b,Math.sin(a)*tubeRadius);pos[k]=q.x;pos[k+1]=q.y;pos[k+2]=q.z;}}g.attributes.position.needsUpdate=true;g.computeVertexNormals();g.computeBoundingSphere();};return o;
 }
 const slices=[],ribs=[],struts=[],knuckles=[],N=24,M=12;
 for(let sector=0;sector<panels;sector++){
  const g=new THREE.BufferGeometry(),positions=new Float32Array((N+1)*(M+1)*3),uv=new Float32Array((N+1)*(M+1)*2),ids=[];
  for(let i=0;i<=N;i++)for(let j=0;j<=M;j++){const k=i*(M+1)+j;uv[k*2]=j/M;uv[k*2+1]=i/N;if(i<N&&j<M){const a=k,b=k+M+1;ids.push(a,a+1,b,b,a+1,b+1)}}
  g.setAttribute('position',new THREE.BufferAttribute(positions,3));g.setAttribute('uv',new THREE.BufferAttribute(uv,2));g.setIndex(ids);const material=sector%2?cream:coral;material.side=THREE.DoubleSide;slices.push(mesh(g,material));
  ribs.push(tube(28,5,.010,metal));struts.push(rod(metal,.012));knuckles.push(mesh(new THREE.SphereGeometry(.028,14,10),wood));
 }
 const rim=tube(panels*10,5,.018,hemMat),shaft=rod(wood,.033),runner=mesh(new THREE.CylinderGeometry(.069,.069,.095,24),coral),cap=mesh(new THREE.SphereGeometry(.085,28,20),coral),tip=mesh(new THREE.ConeGeometry(.040,.17,18),wood);
 let disposed=false;
 function setState({bloom=0,pole=bloom,spin=0,ripple=.4,phase=0}={}){
  if(disposed)throw new Error('Umbrella disposed');if(![bloom,pole,spin,ripple,phase].every(Number.isFinite))throw new Error('state values must be finite');
  bloom=THREE.MathUtils.clamp(bloom,0,1);pole=THREE.MathUtils.clamp(pole,0,1);const top=.2+.85*bloom,R=radius*(.735+.265*bloom),twist=.80*(1-bloom),height=.85*bloom;
  function surface(r,theta,sectorU=0){const a=theta+twist*(1-r)**1.2;const edge=1-.045*bloom*Math.sin(Math.PI*sectorU)**2*r**5;return new THREE.Vector3(R*r*edge*Math.cos(a),top-height*r**1.55-.018*ripple*bloom*r*r*Math.sin(theta*3+phase),R*r*edge*Math.sin(a));}
  for(let k=0;k<panels;k++){
   const a=slices[k].geometry.attributes.position;for(let i=0;i<=N;i++)for(let j=0;j<=M;j++){const q=surface(i/N,(k+j/M)*TAU/panels,j/M);a.setXYZ(i*(M+1)+j,q.x,q.y,q.z)}a.needsUpdate=true;slices[k].geometry.computeVertexNormals();slices[k].geometry.computeBoundingSphere();
   const theta=k*TAU/panels;ribs[k].update(t=>surface(t,theta).add(new THREE.Vector3(0,-.026,0)));
   const hub=new THREE.Vector3(0,top-(1.27-.77*bloom),0),end=surface(.61,theta).add(new THREE.Vector3(0,-.028,0));join(struts[k],hub,end);struts[k].visible=pole>.035;knuckles[k].position.copy(end);knuckles[k].visible=pole>.035;
  }
  rim.update(t=>{const sector=t*panels;return surface(1,t*TAU,sector-Math.floor(sector));});
  const bottom=top-(top+2.14)*pole;join(shaft,new THREE.Vector3(0,top,0),new THREE.Vector3(0,bottom,0));shaft.visible=pole>.001;
  runner.position.set(0,top-(1.27-.77*bloom),0);runner.visible=pole>.035;cap.position.set(0,top+.045,0);cap.scale.set(1,.52,1);tip.position.set(0,bottom-.025,0);tip.rotation.z=Math.PI;tip.visible=pole>.001;
  group.rotation.y=spin;
 }
 function dispose(){if(disposed)return;disposed=true;geometrySet.forEach(g=>g.dispose());materialSet.forEach(m=>m.dispose());group.removeFromParent();}
 setState();return {group,setState,dispose,parts:{slices,ribs,struts,shaft,runner,cap},materials:{coral,cream}};
}
