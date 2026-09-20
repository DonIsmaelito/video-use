import * as THREE from 'three';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

/** Original sculptural chair. Owns shape and absolute soft deformation, never time. */
export function createJellyChair({width=1,material,seamMaterial}={}){
  if(!Number.isFinite(width)||width<=0)throw new Error('width must be positive');
  const group=new THREE.Group();group.name='jelly-chair';
  const skin=material??new THREE.MeshPhysicalMaterial({color:0xaa0b24,roughness:.36,metalness:0,transmission:.35,thickness:.8,ior:1.38,clearcoat:.32,clearcoatRoughness:.28,attenuationColor:0xb60b29,attenuationDistance:2,envMapIntensity:.24});
  const seam=seamMaterial??new THREE.MeshPhysicalMaterial({color:0x9d1020,roughness:.28,clearcoat:.6});
  const owned=[!material&&skin,!seamMaterial&&seam].filter(Boolean),pieces=[];
  function surface(fn,nu,nv,name,mat=skin,reverse=false){
    const positions=[],indices=[];
    for(let i=0;i<=nu;i++)for(let j=0;j<=nv;j++)positions.push(...fn(i/nu,j/nv));
    for(let i=0;i<nu;i++)for(let j=0;j<nv;j++){const a=i*(nv+1)+j,b=a+nv+1;indices.push(a,b,a+1,b,b+1,a+1)}
    let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.setIndex(indices);
    if(reverse)for(let i=0;i<indices.length;i+=3)[indices[i+1],indices[i+2]]=[indices[i+2],indices[i+1]];
    g.setIndex(indices);g=mergeVertices(g,1e-5);g.computeVertexNormals();
    const m=new THREE.Mesh(g,mat);m.name=name;m.castShadow=true;m.receiveShadow=true;group.add(m);
    pieces.push({mesh:m,positions:g.attributes.position.array.slice(),normals:g.attributes.normal.array.slice()});return m;
  }
  const signed=(v,e)=>Math.sign(v)*Math.pow(Math.abs(v),e);
  function pillow(name,center,radii,roundness=.58,lean=0){
    return surface((u,v)=>{const a=(u-.5)*Math.PI,b=v*Math.PI*2,cy=signed(Math.sin(a),roundness),ring=signed(Math.cos(a),roundness);
      const x=radii[0]*ring*signed(Math.cos(b),roundness),z=radii[2]*ring*signed(Math.sin(b),roundness);
      return [center[0]+x+lean*cy,center[1]+radii[1]*cy,center[2]+z];},40,88,name);
  }
  // One continuous arm/back shell, with a rising rear and inflated round ends.
  // Analytic elliptical horseshoe keeps bend radius larger than tube radius.
  // This avoids inner pinches at interpolation knots in a padded back.
  const rail={
    getPoint(u){const a=u*Math.PI;return new THREE.Vector3(-1.08*Math.cos(a),1.29+.35*Math.sin(a)**2,1.03-1.98*Math.sin(a))},
    getTangent(u){const a=u*Math.PI;return new THREE.Vector3(1.08*Math.sin(a),.70*Math.sin(a)*Math.cos(a),-1.98*Math.cos(a)).normalize()}
  };
  const shell=surface((u,v)=>{
    const c=rail.getPoint(u),t=rail.getTangent(u),n=new THREE.Vector3(t.z,0,-t.x).normalize();
    const end=Math.min(u,1-u),cap=end<.062?Math.sqrt(Math.max(0,1-Math.pow(1-end/.062,2))):1;
    const rear=Math.pow(Math.sin(Math.PI*u),2),a=v*Math.PI*2;
    const subtle=.005*Math.sin(u*Math.PI*44)*Math.pow(Math.max(0,Math.sin(a)),4)*rear;
    const radial=(.295+subtle)*Math.cos(a)*cap,vertical=(.37+.29*rear)*Math.sin(a)*cap;
    return [c.x+n.x*radial,c.y+vertical,c.z+n.z*radial];
  },180,40,'continuous-back-and-arms',skin,true);
  const cushion=pillow('deep-seat-cushion',[0,.86,.08],[.90,.325,.84],.47);
  for(const x of [-1,1])for(const z of [-1,1])pillow('rounded-support-'+x+'-'+z,[x*.80,.37,z*.58],[.255,.37,.28],.68,x*.065);
  // A restrained molded parting line around the padded seat, not a graphic label.
  const piping=surface((u,v)=>{
    const a=u*Math.PI*2,b=v*Math.PI*2,r=.009;
    const x=.884*signed(Math.cos(a),.5),z=.817*signed(Math.sin(a),.5);
    const n=new THREE.Vector3(x/.884,0,z/.817).normalize();
    return [x+n.x*Math.cos(b)*r,.846+Math.sin(b)*r,.08+z+n.z*Math.cos(b)*r];
  },160,8,'molded-seat-seam',seam,true);
  function setState({squash=1,lift=0,bend=0,yaw=0}={}){
    if(![squash,lift,bend,yaw].every(Number.isFinite))throw new Error('state values must be finite');
    const vertical=THREE.MathUtils.clamp(squash,.42,1.5),horizontal=1/Math.sqrt(vertical),b=THREE.MathUtils.clamp(bend,-.5,.5);
    for(const p of pieces){
      const a=p.mesh.geometry.attributes.position,n=p.mesh.geometry.attributes.normal,base=p.positions,bn=p.normals;
      for(let i=0;i<a.count;i++){
        const k=i*3,x=base[k],y=base[k+1],z=base[k+2],dxdy=2*b*y/(2.3*2.3);
        a.setXYZ(i,x*horizontal+b*(y/2.3)**2,y*vertical,z*horizontal);
        const nx=bn[k]/horizontal,ny=bn[k+1]/vertical-bn[k]*dxdy/(horizontal*vertical),nz=bn[k+2]/horizontal,l=Math.hypot(nx,ny,nz)||1;
        n.setXYZ(i,nx/l,ny/l,nz/l);
      }
      a.needsUpdate=true;n.needsUpdate=true;p.mesh.geometry.computeBoundingSphere();
    }
    group.scale.setScalar(width);group.position.y=Math.max(0,lift);group.rotation.y=yaw;
  }
  function dispose(){pieces.forEach(p=>p.mesh.geometry.dispose());owned.forEach(m=>m.dispose());group.removeFromParent()}
  setState();
  return {group,setState,dispose,parts:{shell,cushion,piping,supports:pieces.filter(p=>p.mesh.name.startsWith('rounded-support')).map(p=>p.mesh)}};
}
