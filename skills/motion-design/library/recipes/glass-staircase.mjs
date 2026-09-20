import * as THREE from 'three';
const clamp=v=>Math.max(0,Math.min(1,Number.isFinite(v)?v:0));
const ease=v=>{v=clamp(v);return v*v*v*(v*(v*6-15)+10)};
function tileShape(){const w=1.98,h=.86,r=.065,s=new THREE.Shape();s.moveTo(-w/2+r,-h/2);s.lineTo(w/2-r,-h/2);s.quadraticCurveTo(w/2,-h/2,w/2,-h/2+r);s.lineTo(w/2,h/2-r);s.quadraticCurveTo(w/2,h/2,w/2-r,h/2);s.lineTo(-w/2+r,h/2);s.quadraticCurveTo(-w/2,h/2,-w/2,h/2-r);s.lineTo(-w/2,-h/2+r);s.quadraticCurveTo(-w/2,-h/2,-w/2+r,-h/2);return s}

/** Original colored tile assembly. Per-tile state follows one absolute cascade control. */
export function createGlassStaircase({tileCount=20,turns=1.10}={}){
 tileCount=Math.max(10,Math.min(30,Math.round(Number.isFinite(tileCount)?tileCount:20)));turns=Math.max(.65,Math.min(1.4,Number.isFinite(turns)?turns:1.1));
 const group=new THREE.Group(),tiles=[],materials=[];
 const geometry=new THREE.ExtrudeGeometry(tileShape(),{depth:.145,steps:1,bevelEnabled:true,bevelSize:.025,bevelThickness:.025,bevelSegments:3,curveSegments:10});geometry.rotateX(-Math.PI/2);geometry.translate(0,-.0725,0);
 const edgeGeometry=new THREE.EdgesGeometry(geometry,25),colors=['#3bccdf','#4a9be0','#786ecf','#d873b1','#efae62','#87caaa'];
 for(let i=0;i<tileCount;i++){const color=new THREE.Color(colors[Math.floor(i/3)%colors.length]);const material=new THREE.MeshPhysicalMaterial({color:color.clone().lerp(new THREE.Color('#ffffff'),.38),roughness:.075,metalness:0,transmission:.66,transparent:true,opacity:.72,depthWrite:false,thickness:.22,ior:1.47,attenuationColor:color,attenuationDistance:.82,clearcoat:.6,clearcoatRoughness:.10,envMapIntensity:1.2});materials.push(material);const part=new THREE.Group(),mesh=new THREE.Mesh(geometry,material),edgeMaterial=new THREE.LineBasicMaterial({color:color.clone().lerp(new THREE.Color('#ffffff'),.45),transparent:true,opacity:.48});materials.push(edgeMaterial);part.add(mesh,new THREE.LineSegments(edgeGeometry,edgeMaterial));mesh.castShadow=true;mesh.receiveShadow=true;group.add(part);tiles.push(part)}
 function setState({cascade=1,spread=1,settle=1,phase=0}={}){
  cascade=clamp(cascade);spread=Math.max(.75,Math.min(1.25,Number.isFinite(spread)?spread:1));settle=clamp(settle);phase=Number.isFinite(phase)?phase:0;
  for(let i=0;i<tileCount;i++){const k=i/(tileCount-1),local=ease((cascade-k*.58)/.42),theta=-Math.PI*.72+k*Math.PI*2*turns,r=1.22*spread;
   const rise=i*.224+.17,flight=Math.sin(local*Math.PI)*(.31+.07*Math.sin(i*1.8));
   tiles[i].position.set(Math.cos(theta)*r*local,rise+flight,Math.sin(theta)*r*local);tiles[i].rotation.set(Math.sin(local*Math.PI)*.13*Math.sin(i*.7),-theta*local,Math.sin(local*Math.PI)*.10*Math.cos(i*.7));
   const calm=(1-settle)*.016*local;tiles[i].position.y+=Math.sin(phase-i*.42)*calm;
  }
 }
 setState();return {group,tiles,setState,controls:['cascade','spread','settle','phase'],dispose(){geometry.dispose();edgeGeometry.dispose();for(const m of materials)m.dispose();group.removeFromParent()}};
}
