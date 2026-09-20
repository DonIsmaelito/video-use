import * as THREE from 'three';

/** Original mechanism: one mechanical aperture with independent functional states.
 * Caller owns camera, environment, materials, timing, copy and audio.
 * No timeline, wall clock, randomness, renderer or network access lives here.
 */
export function createOpticalAssembly({bladeCount=8, radius=2, shellMaterial, bladeMaterial, trimMaterial, lensMaterial}={}) {
  if (!Number.isInteger(bladeCount) || bladeCount<5 || bladeCount>16) throw new Error('bladeCount must be an integer from 5 to 16');
  if (!Number.isFinite(radius) || radius<=0) throw new Error('radius must be positive');
  const group=new THREE.Group();group.name='optical-assembly';
  const shell=shellMaterial??new THREE.MeshPhysicalMaterial({color:0x343d48,metalness:.86,roughness:.3});
  const blade=bladeMaterial??new THREE.MeshPhysicalMaterial({color:0x9aa5b0,metalness:1,roughness:.24,side:THREE.DoubleSide});
  const trim=trimMaterial??new THREE.MeshPhysicalMaterial({color:0xe7b767,metalness:.78,roughness:.21});
  const glass=lensMaterial??new THREE.MeshPhysicalMaterial({color:0x537d93,metalness:.12,roughness:.07,transmission:.76,thickness:.8,ior:1.48,iridescence:.55,clearcoat:1});
  const ownedMaterials=[!shellMaterial&&shell,!bladeMaterial&&blade,!trimMaterial&&trim,!lensMaterial&&glass].filter(Boolean);
  const meshes=[],geometries=[];
  const mesh=(geometry,material,name,parent=group)=>{geometries.push(geometry);const m=new THREE.Mesh(geometry,material);m.name=name;m.castShadow=true;m.receiveShadow=true;parent.add(m);meshes.push(m);return m;};
  const ring=(r,tube,z,material,name,parent=group)=>{const m=mesh(new THREE.TorusGeometry(r,tube,24,180),material,name,parent);m.position.z=z;return m;};
  const annulus=(outer,inner,depth,z,material,name,parent=group)=>{
    const shape=new THREE.Shape();shape.absarc(0,0,outer,0,Math.PI*2,false);
    const hole=new THREE.Path();hole.absarc(0,0,inner,0,Math.PI*2,true);shape.holes.push(hole);
    const geometry=new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSegments:3,bevelSize:.025,bevelThickness:.025,curveSegments:96,steps:1});
    const m=mesh(geometry,material,name,parent);m.position.z=z;return m;
  };
  const casing=new THREE.Group();casing.name='casing';group.add(casing);
  annulus(2.55,1.97,.58,-.4,shell,'outer-shell',casing);
  ring(2.36,.048,.18,trim,'outer-rim',casing);
  ring(2.00,.075,.19,shell,'inner-rim',casing);
  ring(2.24,.12,-.46,shell,'rear-shell',casing);
  // Machined seams and fasteners remain attached to their parent housing.
  for(let i=0;i<48;i++){
    const a=i*Math.PI*2/48;
    const m=mesh(new THREE.BoxGeometry(.025,.13,.1),shell,'grip-'+i,casing);
    m.position.set(2.54*Math.cos(a),2.54*Math.sin(a),-.13);m.rotation.z=a-Math.PI/2;
  }
  for(let i=0;i<6;i++){
    const a=i*Math.PI/3+Math.PI/6;
    const m=mesh(new THREE.CylinderGeometry(.054,.054,.031,6),trim,'fastener-'+i,casing);
    m.rotation.x=Math.PI/2;m.position.set(2.24*Math.cos(a),2.24*Math.sin(a),.169);
  }
  const actuator=new THREE.Group();actuator.name='actuator';group.add(actuator);
  ring(2.1,.035,.25,trim,'actuator-track',actuator);
  const key=mesh(new THREE.BoxGeometry(.32,.12,.08),trim,'actuator-key',actuator);key.position.set(0,2.11,.265);

  const pivots=[];
  for(let i=0;i<bladeCount;i++){
    const a=i*Math.PI*2/bladeCount;
    const pivot=new THREE.Group();pivot.name='blade-pivot-'+i;
    pivot.position.set(1.78*Math.cos(a),1.78*Math.sin(a),.015+i*.005);
    group.add(pivot);pivots.push(pivot);
    // Wedge extends slightly beneath the fixed bezel; its tip covers the pupil.
    const span=Math.PI/bladeCount*1.32,outer=2.08,shape=new THREE.Shape();
    shape.moveTo(-1.80,-.025);
    shape.quadraticCurveTo(-.83,-.35,outer*Math.cos(-span)-1.78,outer*Math.sin(-span));
    shape.absarc(-1.78,0,outer,-span,span,false);
    shape.quadraticCurveTo(-.8,.34,-1.80,.025);shape.closePath();
    const geometry=new THREE.ExtrudeGeometry(shape,{depth:.026,bevelEnabled:true,bevelSegments:2,bevelSize:.012,bevelThickness:.006,steps:1,curveSegments:20});
    const m=mesh(geometry,blade,'iris-blade-'+i,pivot);m.rotation.z=0;
    const pin=mesh(new THREE.CylinderGeometry(.065,.065,.045,20),trim,'blade-pin-'+i,pivot);pin.rotation.x=Math.PI/2;pin.position.z=.057;
  }
  const lensGroup=new THREE.Group();lensGroup.name='lens-stack';group.add(lensGroup);
  ring(1.34,.08,-.38,shell,'lens-seat',lensGroup);
  ring(1.18,.026,-.31,trim,'lens-retainer',lensGroup);
  const lens=mesh(new THREE.SphereGeometry(1.21,80,48),glass,'convex-lens',lensGroup);lens.scale.z=.24;lens.position.z=-.51;
  const coreMaterial=new THREE.MeshStandardMaterial({color:0x193c42,emissive:0x194755,emissiveIntensity:.08,metalness:.7,roughness:.2});ownedMaterials.push(coreMaterial);
  const core=mesh(new THREE.CircleGeometry(1.15,96),coreMaterial,'optical-core',lensGroup);core.position.z=-.86;
  ring(.79,.018,-.82,trim,'focal-ring',lensGroup);
  ring(.27,.012,-.80,trim,'focal-center',lensGroup);
  const clamp=v=>Math.max(0,Math.min(1,v));
  function setState({aperture=0,separation=0,rotation=0}={}){
    if(![aperture,separation,rotation].every(Number.isFinite))throw new Error('state values must be finite');
    const open=clamp(aperture),spread=clamp(separation);
    group.scale.setScalar(radius/2);group.rotation.z=rotation;
    casing.position.z=-spread*.25;actuator.position.z=spread*.62;actuator.rotation.z=-open*.44;
    const travel=.58*Math.min(1,bladeCount/8);
    pivots.forEach((p,i)=>{const a=i*Math.PI*2/bladeCount;p.rotation.z=a-open*travel;p.position.z=.015+i*.005+spread*(.15+i*.023);});
    lensGroup.position.z=-spread*.72;
    coreMaterial.emissiveIntensity=.045+.12*open;
  }
  function dispose(){for(const g of geometries)g.dispose();for(const m of ownedMaterials)m.dispose();group.removeFromParent();}
  setState();
  return {group,setState,dispose,parts:{casing,actuator,blades:pivots,lensStack:lensGroup}};
}
