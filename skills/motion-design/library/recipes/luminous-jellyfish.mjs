import * as THREE from 'three';

// Authored anatomy and absolute pose; the host owns the water, lights and clock.
export function createLuminousJellyfish({tentacleCount=18, color='#cca4ff'}={}) {
  if(!Number.isInteger(tentacleCount)||tentacleCount<4||tentacleCount>40) throw new Error('tentacleCount must be 4–40');
  const group=new THREE.Group(),geometries=[],materials=[];
  let disposed=false;
  const ownMaterial=m=>{materials.push(m);return m;};
  function surface(rows,columns,material){
    const geo=new THREE.BufferGeometry(),positions=new Float32Array((rows+1)*(columns+1)*3),indices=[];
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){const a=y*(columns+1)+x,b=a+columns+1;indices.push(a,b,a+1,b,b+1,a+1);}
    geo.setAttribute('position',new THREE.BufferAttribute(positions,3));geo.setIndex(indices);geometries.push(geo);
    const mesh=new THREE.Mesh(geo,material);mesh.frustumCulled=false;group.add(mesh);
    return {mesh,update(fn){let i=0;for(let y=0;y<=rows;y++)for(let x=0;x<=columns;x++){const p=fn(y/rows,x/columns);positions[i++]=p.x;positions[i++]=p.y;positions[i++]=p.z;}geo.attributes.position.needsUpdate=true;geo.computeVertexNormals();}};
  }
  const pearl=ownMaterial(new THREE.ShaderMaterial({transparent:true,side:THREE.DoubleSide,depthWrite:false,uniforms:{uTint:{value:new THREE.Color(color)}},vertexShader:`varying vec3 vN,vP;void main(){vec4 p=modelMatrix*vec4(position,1.);vP=p.xyz;vN=normalize(mat3(modelMatrix)*normal);gl_Position=projectionMatrix*viewMatrix*p;}`,fragmentShader:`uniform vec3 uTint;varying vec3 vN,vP;void main(){vec3 n=normalize(vN),v=normalize(cameraPosition-vP);float facing=abs(dot(n,v)),f=pow(1.-facing,1.7);vec3 light=normalize(vec3(-.6,.9,.8));float spec=pow(max(dot(reflect(-light,n),v),0.),55.);vec3 c=mix(uTint*.45,vec3(.37,.8,1.5),f);c+=vec3(1.1,.36,.7)*pow(max(0.,n.x),2.)*.34;c+=vec3(1.2)*spec*.7;gl_FragColor=vec4(c,.075+f*.62+spec*.16);}` }));
  const bell=surface(32,96,pearl);bell.mesh.renderOrder=3;
  const fringeMat=ownMaterial(new THREE.MeshStandardMaterial({color:'#efbfff',roughness:.23,metalness:.24,emissive:'#cd6aff',emissiveIntensity:.28,transparent:true,opacity:.73,side:THREE.DoubleSide,depthWrite:false}));
  const innerMat=ownMaterial(new THREE.MeshPhysicalMaterial({color:'#ff9cb9',roughness:.25,metalness:.1,clearcoat:1,emissive:'#eb377f',emissiveIntensity:.27,transparent:true,opacity:.64,side:THREE.DoubleSide,depthWrite:false}));
  const threadMat=ownMaterial(new THREE.MeshStandardMaterial({color:'#aacfff',roughness:.2,metalness:.24,emissive:'#5699f4',emissiveIntensity:.3}));
  const pinkThread=ownMaterial(new THREE.MeshStandardMaterial({color:'#efb5e8',roughness:.25,emissive:'#c268dc',emissiveIntensity:.2}));
  function tube(material,segments=72,sides=6){
    const out=surface(segments,sides,material);
    return (curve,radius)=>{
      out.update((u,v)=>{
        const p=curve(u),a=curve(Math.max(0,u-.002)),b=curve(Math.min(1,u+.002)),t=b.sub(a).normalize();
        const ref=Math.abs(t.y)>.96?new THREE.Vector3(1,0,0):new THREE.Vector3(0,1,0);
        const n=new THREE.Vector3().crossVectors(t,ref).normalize(),bin=new THREE.Vector3().crossVectors(t,n).normalize(),r=radius(u),ang=v*Math.PI*2;
        return p.addScaledVector(n,Math.cos(ang)*r).addScaledVector(bin,Math.sin(ang)*r);
      });
    };
  }
  const ribMat=ownMaterial(fringeMat.clone());ribMat.opacity=.16;ribMat.emissiveIntensity=.35;
  const rim=tube(fringeMat,128,8),ribs=Array.from({length:12},()=>tube(ribMat,28,5));
  const tentacles=Array.from({length:tentacleCount},(_,i)=>tube(i%3?threadMat:pinkThread,76,6));
  const oralArms=Array.from({length:4},()=>surface(90,7,innerMat));
  const organs=Array.from({length:4},(_,i)=>{
    const geo=new THREE.TorusGeometry(.19,.016,10,52);geometries.push(geo);
    const m=new THREE.Mesh(geo,fringeMat);m.rotation.x=.45;m.scale.set(.8,1.3,1);m.position.set(Math.cos(i*Math.PI/2)*.28,.40+Math.sin(i*Math.PI/2)*.17,Math.sin(i*Math.PI/2)*.20);group.add(m);return m;
  });
  function setState({pulse=0,phase=0,current=0}={}){
    if(disposed)throw new Error('Jellyfish disposed');
    if(![pulse,phase,current].every(Number.isFinite))throw new Error('finite state required');
    pulse=THREE.MathUtils.clamp(pulse,0,1);current=THREE.MathUtils.clamp(current,-1,1);
    const radius=1.48*(1-.22*pulse),height=1.17*(1+.18*pulse);
    function dome(u,v){const a=u*Math.PI*.5,az=v*Math.PI*2,r=radius*Math.sin(a)*(1+.021*Math.cos(az*16)*u**7),frill=.055*Math.sin(az*16+phase*.6)*u**12;return new THREE.Vector3(Math.cos(az)*r,Math.cos(a)*height+frill,Math.sin(az)*r);}
    bell.update(dome);
    rim(u=>dome(1,u),()=>.022);
    ribs.forEach((fn,i)=>fn(u=>dome(.25+.74*u,i/12),u=>.004+.004*u));
    tentacles.forEach((fn,i)=>{
      const a=i/tentacleCount*Math.PI*2,length=3.02+.78*(.5+.5*Math.sin(i*4.1));
      fn(u=>{
        const r=radius*.89,lag=phase-u*6.2+i*.61,wave=(.14+.38*u)*u;
        return new THREE.Vector3(Math.cos(a)*r+Math.sin(lag)*wave+current*u*u*.8, -.01-length*u+.12*u*Math.sin(lag*.63),Math.sin(a)*r+Math.cos(lag*.86)*wave);
      },u=>(.012+.003*Math.sin(i))*Math.max(.16,1-u*.82));
    });
    oralArms.forEach((arm,i)=>{
      const a=i*Math.PI*.5+.3;
      arm.update((u,v)=>{
        const lag=phase*.75-u*8+i*1.6,w=.20*(1-.64*u)*(1+.48*Math.sin(u*40-phase*1.6)),side=(v-.5)*2,edge=Math.abs(side)**2;
        const cx=Math.cos(a)*(.22+.30*u)+.22*u*Math.sin(lag)+current*u*u*.6,cz=Math.sin(a)*(.22+.30*u)+.23*u*Math.cos(lag*.9);
        return new THREE.Vector3(cx+Math.cos(a+1.57)*w*side,-u*(2.9+.18*Math.sin(i))+.18+edge*.065*Math.sin(u*62+phase+i),cz+Math.sin(a+1.57)*w*side+edge*.065*Math.cos(u*57+phase+i));
      });
    });
    organs.forEach((m,i)=>{m.position.y=.40+Math.sin(i*Math.PI/2)*.17+.10*pulse;m.scale.set(.65,.85,1);m.rotation.z=i*Math.PI*.5+phase*.03;});
  }
  setState();
  return {group,setState,dispose(){if(disposed)return;disposed=true;for(const g of geometries)g.dispose();for(const m of materials)m.dispose();group.removeFromParent();group.clear();}};
}
