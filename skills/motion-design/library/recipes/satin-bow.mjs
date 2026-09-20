import * as THREE from 'three';

const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
const V=(x,y,z)=>new THREE.Vector3(x,y,z);

/** Original continuous ribbon surface. Absolute controls, no clock or cloth solver. */
export function createSatinBow({width=.64,segments=320,crossSegments=12,material,edgeMaterial}={}){
  width=clamp(width,.35,.9);segments=Math.max(96,Math.min(640,Math.round(segments)));crossSegments=Math.max(4,Math.min(24,Math.round(crossSegments)));
  const ownsMaterial=!material,ownsEdge=!edgeMaterial;
  material??=new THREE.MeshPhysicalMaterial({color:'#d92579',roughness:.3,metalness:.12,sheen:1,sheenColor:'#ff81bc',sheenRoughness:.4,anisotropy:.85,side:THREE.DoubleSide});
  edgeMaterial??=new THREE.MeshStandardMaterial({color:'#ed6fa8',roughness:.37,metalness:.15});
  const group=new THREE.Group();group.name='Original continuous satin ribbon';
  const geometry=new THREE.BufferGeometry(),rows=segments+1,cols=crossSegments+1;
  const positions=new Float32Array(rows*cols*3),uvs=new Float32Array(rows*cols*2),indices=[];
  for(let i=0;i<rows;i++)for(let j=0;j<cols;j++){const n=i*cols+j;uvs[n*2]=i/segments;uvs[n*2+1]=j/crossSegments;if(i<segments&&j<crossSegments){indices.push(n,n+cols,n+1,n+1,n+cols,n+cols+1)}}
  geometry.setAttribute('position',new THREE.BufferAttribute(positions,3).setUsage(THREE.DynamicDrawUsage));geometry.setAttribute('uv',new THREE.BufferAttribute(uvs,2));geometry.setIndex(indices);
  const ribbon=new THREE.Mesh(geometry,material);ribbon.castShadow=true;ribbon.receiveShadow=true;ribbon.frustumCulled=false;group.add(ribbon);
  // Fine continuous selvedges have their own small cross-section, not disconnected ornaments.
  const edgeGeometry=new THREE.BufferGeometry(),edgePositions=new Float32Array(rows*2*6*3),edgeIndices=[];
  for(let side=0;side<2;side++)for(let i=0;i<segments;i++)for(let j=0;j<6;j++){const a=(side*rows+i)*6+j,b=(side*rows+i)*6+(j+1)%6;edgeIndices.push(a,a+6,b,b,a+6,b+6)}
  edgeGeometry.setAttribute('position',new THREE.BufferAttribute(edgePositions,3).setUsage(THREE.DynamicDrawUsage));edgeGeometry.setIndex(edgeIndices);const edges=new THREE.Mesh(edgeGeometry,edgeMaterial);edges.frustumCulled=false;group.add(edges);
  const centers=Array.from({length:rows},()=>V(0,0,0)),axis=V(0,0,1),previous=V(0,1,0),tangent=V(1,0,0),sideVector=V(0,1,0),normal=V(0,0,1),point=V(0,0,0);

  function setState({tie=1,cinch=1,flutter=0,phase=0,loopSpread=1,tailDrop=1}={}){
    tie=clamp(tie);cinch=clamp(cinch);flutter=clamp(flutter,0,1);phase=Number.isFinite(phase)?phase:0;loopSpread=clamp(loopSpread,.72,1.28);tailDrop=clamp(tailDrop,.65,1.25);
    const band=1.32-.32*cinch;
    const points=[
      [-2.04,-2.05,.18],[-1.72,-1.47,.35],[-.92,-.68,.14],[-.16,-.10,-.13],
      [-.82,.85,-.16],[-1.95,1.49,-.22],[-2.86,1.25,.08],[-2.96,.66,.63],[-2.25,.22,.88],[-1.05,.15,.79],[-.17,.13,.64],
      [.04,.18*band,1.02*band],[.04,-.22*band,1.03*band],[.04,-.48*band,.56],[.04,-.40,-.14],[.04,0,-.38*band],[.04,.43*band,.08],[.04,.43,.72*band],[.04,.15,1.12*band],[.34,.66,.45],
      [.65,.91,.06],[1.89,1.50,-.22],[2.81,1.25,.02],[2.94,.66,.56],[2.19,.20,.90],[.97,.12,.78],[.13,-.12,-.10],
      [.80,-.67,.10],[1.39,-1.46,.51],[2.06,-2.05,.51]
    ].map(([x,y,z],i)=>V(x*(Math.abs(x)>.65?loopSpread:1),y*(i<3||i>26?tailDrop:1),z));
    const curve=new THREE.CatmullRomCurve3(points,false,'centripetal');curve.arcLengthDivisions=800;
    const gathering=smooth(tie);
    for(let i=0;i<rows;i++){
      const u=i/segments,base=V(-4.1+8.2*u,1.08*Math.sin(u*Math.PI*3-.15)+.05,.48*Math.sin(u*Math.PI*2+.4));
      const target=curve.getPointAt(u);
      // The left bight gathers first; the continuous crossing follows, then the right loop.
      const delay=.12*Math.sin(u*Math.PI)+.10*smooth((u-.45)/.2);
      const local=smooth((tie-delay)/(1-delay));
      centers[i].copy(base).lerp(target,local);
      const free=Math.pow(Math.abs(u-.5)*2,2),settle=flutter*(.12+free*.25);
      centers[i].z+=Math.sin(phase-u*8.7)*settle*(.2+.8*gathering);
      centers[i].y+=Math.sin(phase*.81-u*7.3)*settle*.32;
    }
    previous.set(0,1,0);
    for(let i=0;i<rows;i++){
      const u=i/segments;
      tangent.subVectors(centers[Math.min(segments,i+1)],centers[Math.max(0,i-1)]).normalize();
      const central=Math.exp(-centers[i].x*centers[i].x/.35)*Math.exp(-centers[i].y*centers[i].y/1.2)*gathering;
      sideVector.copy(previous).addScaledVector(tangent,-previous.dot(tangent));
      if(sideVector.lengthSq()<.0001)sideVector.crossVectors(axis,tangent);
      sideVector.normalize();
      // The center collar is a horizontal-width wrap around the y/z loop.
      point.set(1,0,0).addScaledVector(tangent,-tangent.x);
      if(point.lengthSq()>.06){point.normalize();if(point.dot(sideVector)<0)point.negate();sideVector.lerp(point,central).normalize()}
      previous.copy(sideVector);
      const twist=((1-gathering)*(.70*Math.sin(u*Math.PI*4+.5)) + gathering*(.23*Math.sin(u*Math.PI*7-.3)+.12*Math.sin(u*Math.PI*13)))*(1-central*.9);
      normal.crossVectors(tangent,sideVector).normalize();sideVector.multiplyScalar(Math.cos(twist)).addScaledVector(normal,Math.sin(twist)).normalize();normal.crossVectors(tangent,sideVector).normalize();
      const taper=1-.07*Math.pow(Math.sin(u*Math.PI*2),2),w=width*taper*(1-central*.20);
      for(let j=0;j<cols;j++){
        const v=j/crossSegments*2-1;
        const cup=.036*(1-v*v)*(1+.6*Math.sin(u*31+phase*.2)*flutter);
        point.copy(centers[i]).addScaledVector(sideVector,v*w/2).addScaledVector(normal,cup);
        // Shallow chevron cuts are authored into the ribbon's two ends.
        if(u<.07)point.addScaledVector(tangent,.18*(1-Math.abs(v))*Math.pow(1-u/.07,2));
        if(u>.93)point.addScaledVector(tangent,-.18*(1-Math.abs(v))*Math.pow((u-.93)/.07,2));
        const n=(i*cols+j)*3;positions[n]=point.x;positions[n+1]=point.y;positions[n+2]=point.z;
      }
      for(let s=0;s<2;s++)for(let j=0;j<6;j++){
        const angle=j/6*Math.PI*2;point.copy(centers[i]).addScaledVector(sideVector,(s?1:-1)*w/2+Math.cos(angle)*.008).addScaledVector(normal,Math.sin(angle)*.008);
        const n=((s*rows+i)*6+j)*3;edgePositions[n]=point.x;edgePositions[n+1]=point.y;edgePositions[n+2]=point.z;
      }
    }
    geometry.attributes.position.needsUpdate=true;geometry.computeVertexNormals();geometry.computeTangents();geometry.attributes.tangent.needsUpdate=true;geometry.computeBoundingSphere();edgeGeometry.attributes.position.needsUpdate=true;edgeGeometry.computeVertexNormals();edgeGeometry.computeBoundingSphere();
  }
  setState();
  return {group,ribbon,edges,setState,controls:['tie','cinch','flutter','phase','loopSpread','tailDrop'],dispose(){geometry.dispose();edgeGeometry.dispose();if(ownsMaterial)material.dispose();if(ownsEdge)edgeMaterial.dispose();group.removeFromParent()}};
}
