import * as THREE from 'three';

// Original miniature railway. Coordinates and state are local to the returned group.
export function createToyPlanet({radius=2.25,wagonCount=2}={}){
  if(!Number.isFinite(radius)||radius<1.5)throw new Error('radius must be at least 1.5');
  if(!Number.isInteger(wagonCount)||wagonCount<0||wagonCount>3)throw new Error('wagonCount must be an integer from 0 to 3');
  const group=new THREE.Group();group.name='toy-planet';
  const geometries=[],materials=[],TAU=Math.PI*2,start=.35,latitude=.62;
  const material=(color,roughness=.3,extra={})=>{const m=new THREE.MeshPhysicalMaterial({color,roughness,metalness:0,clearcoat:.75,clearcoatRoughness:.2,...extra});materials.push(m);return m;};
  const blue=material('#2b8798',.43,{clearcoat:.40,clearcoatRoughness:.34,specularIntensity:.45}),red=material('#e93223',.25),cream=material('#fff1cd',.38),navy=material('#173b4f',.38),wood=material('#bf7950',.50,{clearcoat:.2}),gold=material('#e8b963',.28,{metalness:.5}),green=material('#418879',.43),lightGreen=material('#93b088',.44),teal=material('#175e67',.36),windowMat=material('#feeab1',.23),coal=material('#163544',.48);
  const mesh=(geometry,m,name,parent=group)=>{geometries.push(geometry);const o=new THREE.Mesh(geometry,m);o.name=name;o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;};
  const box=(size,position,m,name,parent=group)=>{const o=mesh(new THREE.BoxGeometry(...size),m,name,parent);o.position.set(...position);return o;};
  const sphere=(scale,position,m,name,parent=group)=>{const o=mesh(new THREE.SphereGeometry(1,40,28),m,name,parent);o.scale.set(...scale);o.position.set(...position);return o;};
  const cylinder=(r1,r2,height,position,m,name,parent=group,segments=24)=>{const o=mesh(new THREE.CylinderGeometry(r1,r2,height,segments),m,name,parent);o.position.set(...position);return o;};
  const clamp=v=>Math.max(0,Math.min(1,v)),smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
  const normalAt=(angle,lat=latitude)=>new THREE.Vector3(Math.cos(lat)*Math.cos(angle),Math.sin(lat),Math.cos(lat)*Math.sin(angle));
  const bridgeAngle=start+TAU*.60;
  const delta=a=>Math.atan2(Math.sin(a-bridgeAngle),Math.cos(a-bridgeAngle));
  const heightAt=a=>.052+.29*Math.exp(-Math.pow(delta(a)/.40,4));
  const pointAt=a=>normalAt(a).multiplyScalar(radius+heightAt(a));
  function frameAngle(angle){
    const position=pointAt(angle),tangent=pointAt(angle+.0001).sub(pointAt(angle-.0001)).normalize();
    const normal=normalAt(angle);normal.addScaledVector(tangent,-normal.dot(tangent)).normalize();
    const side=new THREE.Vector3().crossVectors(tangent,normal).normalize();
    const quaternion=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(tangent,normal,side));
    return {position,tangent,normal,side,quaternion};
  }
  const trackFrame=turns=>frameAngle(start+turns*TAU);
  const globe=sphere([radius,radius,radius],[0,0,0],blue,'glazed-ceramic-planet');
  const railMeshes=[],segments=256;
  for(const offset of [-.17,.17]){
    const curve=new THREE.Curve();curve.getPoint=t=>{const f=frameAngle(start+t*TAU);return f.position.addScaledVector(f.side,offset);};
    railMeshes.push(mesh(new THREE.TubeGeometry(curve,segments,.021,8,false),gold,'continuous-brass-rail'));
  }
  const bedPoints=[],bedIndices=[];
  for(let i=0;i<=segments;i++){
    const f=frameAngle(start+i/segments*TAU);
    for(const side of [-1,1]){const p=f.position.clone().addScaledVector(f.side,side*.25).addScaledVector(f.normal,-.026);bedPoints.push(p.x,p.y,p.z);}
    if(i<segments){const j=i*2;bedIndices.push(j,j+2,j+1,j+1,j+2,j+3);}
  }
  const bedGeometry=new THREE.BufferGeometry();bedGeometry.setAttribute('position',new THREE.Float32BufferAttribute(bedPoints,3));bedGeometry.setIndex(bedIndices);bedGeometry.computeVertexNormals();
  const bed=mesh(bedGeometry,cream,'ceramic-track-bed');bed.material.side=THREE.DoubleSide;
  const ties=[];
  for(let i=0;i<104;i++){const f=frameAngle(start+i/104*TAU),o=box([.053,.026,.42],[0,0,0],wood,'wooden-sleeper');o.position.copy(f.position).addScaledVector(f.normal,-.010);o.quaternion.copy(f.quaternion);ties.push(o);}

  const cars=[],wheelAxles=[],steam=[],carAngleStep=.69/((radius+.052)*Math.cos(latitude));
  for(let c=0;c<=wagonCount;c++){
    const car=new THREE.Group();car.name=c===0?'red-locomotive':'wagon-'+c;group.add(car);cars.push(car);
    const length=c===0?.78:.54;
    box([length,.10,.38],[0,.235,0],red,'undercarriage',car);
    box([length+.10,.034,.46],[0,.295,0],wood,'wooden-running-board',car);
    for(const x of [-length*.36,length*.36]){
      const axle=new THREE.Group();axle.name='surface-following-axle';group.add(axle);wheelAxles.push({axle,carIndex:c,offset:x,wheels:[]});
      const ax=wheelAxles.at(-1);
      for(const z of [-.17,.17]){
        const wheel=cylinder(.108,.108,.053,[0,.128,z],navy,'rail-wheel',axle,32);wheel.rotation.x=Math.PI/2;ax.wheels.push(wheel);
        const hub=cylinder(.043,.043,.062,[0,.128,z],gold,'wheel-hub',axle,24);hub.rotation.x=Math.PI/2;
        const spoke=box([.145,.017,.067],[0,.128,z],cream,'wheel-spoke',axle);ax.wheels.push(spoke);
      }
    }
    if(c===0){
      const boiler=cylinder(.175,.175,.46,[.12,.465,0],red,'red-boiler',car,40);boiler.rotation.z=Math.PI/2;
      const front=cylinder(.165,.165,.034,[.365,.465,0],navy,'smokebox-face',car,40);front.rotation.z=Math.PI/2;
      const ring=mesh(new THREE.TorusGeometry(.171,.015,8,40),gold,'boiler-ring',car);ring.rotation.y=Math.PI/2;ring.position.set(.30,.465,0);
      cylinder(.075,.055,.22,[.22,.71,0],red,'chimney',car);cylinder(.097,.097,.047,[.22,.837,0],navy,'chimney-lip',car);
      box([.27,.34,.36],[-.255,.49,0],red,'cab',car);
      const roof=box([.36,.050,.45],[-.255,.69,0],cream,'cream-cab-roof',car);roof.rotation.z=-.03;
      for(const side of [-1,1]){box([.145,.14,.013],[-.26,.535,side*.186],navy,'cab-window',car);box([.018,.14,.016],[-.26,.535,side*.196],cream,'window-mullion',car);}
      sphere([.055,.055,.055],[.398,.52,0],windowMat,'headlamp',car);
      box([.11,.052,.34],[.43,.245,0],gold,'front-buffer',car);
      for(let i=0;i<4;i++)steam.push(sphere([.06,.06,.06],[.22,.98,0],cream,'ceramic-steam',car));
    }else{
      for(const side of [-1,1])box([.55,.20,.045],[0,.415,side*.185],red,'wagon-side',car);
      for(const x of [-.255,.255])box([.04,.20,.36],[x,.415,0],red,'wagon-end',car);
      if(c===1){for(let j=0;j<3;j++){const log=cylinder(.055,.055,.39,[0,.43+j*.065,(j%2-.5)*.095],cream,'cargo-timber',car);log.rotation.z=Math.PI/2;}}
      else{sphere([.15,.14,.15],[0,.47,0],lightGreen,'tree-crown-cargo',car);cylinder(.045,.055,.22,[0,.38,0],wood,'tree-trunk-cargo',car);}
    }
    for(const x of [-length/2-.065,length/2+.065])sphere([.045,.035,.035],[x,.235,0],gold,'coupler',car);
  }
  const features=[];
  function surfaceFrame(theta,lat){
    const normal=normalAt(theta,lat),east=new THREE.Vector3(-Math.sin(theta),0,Math.cos(theta)),north=new THREE.Vector3().crossVectors(east,normal).normalize();
    return {normal,quaternion:new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(east,normal,north))};
  }
  function tree(parent,x,z,scale=1,kind=0){
    const t=new THREE.Group();parent.add(t);t.position.set(x,.055,z);t.scale.setScalar(scale);
    cylinder(.036,.045,.23,[0,.13,0],wood,'tree-trunk',t,12);
    if(kind){sphere([.18,.26,.16],[0,.38,0],green,'rounded-tree-crown',t);sphere([.14,.18,.13],[.10,.31,.025],lightGreen,'rounded-tree-lobe',t);}
    else for(let i=0;i<3;i++){const crown=cylinder(.007,.20-i*.034,.28,[0,.27+i*.115,0],i%2?lightGreen:green,'turned-wood-tree',t,24);}
  }
  function house(parent,x,z,scale=1,roofMaterial=teal){
    const h=new THREE.Group();parent.add(h);h.position.set(x,.04,z);h.scale.setScalar(scale);
    box([.44,.065,.36],[0,.01,0],cream,'house-foundation',h);
    box([.40,.38,.32],[0,.21,0],cream,'house-walls',h);
    const roofShape=new THREE.Shape();roofShape.moveTo(-.235,0);roofShape.lineTo(0,.19);roofShape.lineTo(.235,0);roofShape.closePath();
    const roof=mesh(new THREE.ExtrudeGeometry(roofShape,{depth:.38,bevelEnabled:true,bevelSegments:2,bevelSize:.012,bevelThickness:.012,steps:1}),roofMaterial,'gabled-roof',h);roof.position.set(0,.40,-.19);
    for(const side of [-1,1]){box([.09,.11,.012],[-.11,.25,side*.165],windowMat,'house-window',h);box([.012,.12,.015],[-.11,.25,side*.175],wood,'window-divider',h);}
    box([.085,.19,.013],[.09,.12,.167],wood,'house-door',h);box([.065,.15,.065],[.115,.49,-.055],cream,'house-chimney',h);
  }
  const specs=[
    [.04,1.03,'trees',.86],[.16,1.04,'house',.86],[.28,.10,'trees',1.02],[.39,1.10,'houses',.86],
    [.50,.10,'trees',.88],[.63,1.06,'house',.90],[.76,1.05,'trees',.90],[.88,.10,'houses',.90],
  ];
  for(let i=0;i<specs.length;i++){
    const [fraction,lat,type,scale]=specs[i],theta=start+fraction*TAU,f=surfaceFrame(theta,lat),cluster=new THREE.Group();cluster.name='landscape-cluster-'+i;cluster.quaternion.copy(f.quaternion);group.add(cluster);
    const island=sphere([.51,.115,.36],[0,-.055,0],i%2?lightGreen:green,'ceramic-island',cluster);
    if(type==='trees'){tree(cluster,-.18,-.015,scale,0);tree(cluster,.17,.04,scale*.78,1);}
    else{house(cluster,-.10,0,scale,i%2?teal:wood);tree(cluster,.30,-.045,.65,0);if(type==='houses')house(cluster,-.39,-.10,.62,wood);}
    const lineGeometry=new THREE.BufferGeometry();lineGeometry.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(36*3),3));geometries.push(lineGeometry);
    const lineMaterial=new THREE.LineBasicMaterial({color:'#ffe7af',transparent:true,opacity:.82});materials.push(lineMaterial);const tether=new THREE.Line(lineGeometry,lineMaterial);tether.name='train-pulls-landscape';group.add(tether);
    features.push({cluster,normal:f.normal,fraction,lat,tether});
  }
  // The track lifts over a miniature cream viaduct; wheels use this same raised path.
  const bridge=new THREE.Group();bridge.name='ceramic-viaduct';group.add(bridge);
  const bframe=surfaceFrame(bridgeAngle,latitude);bridge.quaternion.copy(bframe.quaternion);
  for(const x of [-.53,.53])box([.13,.30,.48],[x,.15,0],cream,'bridge-pier',bridge);
  for(const z of [-.225,.225]){
    const curve=new THREE.CatmullRomCurve3(Array.from({length:25},(_,i)=>{const x=-.54+i/24*1.08;return new THREE.Vector3(x,.035+.24*Math.sqrt(Math.max(0,1-(x/.55)**2)),z);}));
    mesh(new THREE.TubeGeometry(curve,48,.052,10,false),cream,'bridge-arch',bridge);
  }
  let disposed=false;
  function setState({travel=0,trackProgress=1,landscapeProgress=travel,pull=1}={}){
    if(disposed)throw new Error('Toy planet has been disposed');
    if(![travel,trackProgress,landscapeProgress,pull].every(Number.isFinite))throw new Error('state values must be finite');
    const built=clamp(trackProgress),angle=start+travel*TAU;
    for(const rail of railMeshes)rail.geometry.setDrawRange(0,Math.floor(segments*built)*8*6);
    bed.geometry.setDrawRange(0,Math.floor(segments*built)*6);
    ties.forEach((tie,i)=>{tie.visible=i/104<=built;});
    cars.forEach((car,i)=>{const f=frameAngle(angle-i*carAngleStep);car.position.copy(f.position);car.quaternion.copy(f.quaternion);});
    wheelAxles.forEach(({axle,carIndex,offset,wheels})=>{const f=frameAngle(angle-carIndex*carAngleStep+offset/((radius+.052)*Math.cos(latitude)));axle.position.copy(f.position);axle.quaternion.copy(f.quaternion);for(const wheel of wheels){if(wheel.name==='wheel-spoke')wheel.rotation.z=-travel*TAU*(radius+.052)*Math.cos(latitude)/.108;}});
    steam.forEach((p,i)=>{const age=((travel*3+i/steam.length)%1+1)%1,s=.04+.07*Math.sin(age*Math.PI);p.scale.setScalar(s);p.position.set(.19-age*.27,.96+age*.45,.025*Math.sin(age*5+i));});
    const rear=frameAngle(angle-wagonCount*carAngleStep-.20),from=rear.position.clone().addScaledVector(rear.normal,.26);
    features.forEach(({cluster,normal,fraction,tether},i)=>{
      const u=clamp((landscapeProgress-fraction-.07)/.095),rise=smooth(u),settle=rise+.06*Math.sin(Math.PI*u)*Math.sin(Math.PI*u*2);
      cluster.visible=rise>.001;cluster.position.copy(normal).multiplyScalar(radius-.34*(1-rise));cluster.scale.set(1,.04+.96*settle,1);
      tether.visible=pull>0&&u>.02&&u<.98;
      const to=normal.clone().multiplyScalar(radius+.08+.35*rise),middle=from.clone().add(to).multiplyScalar(.5).normalize().multiplyScalar(radius+.85);
      const a=tether.geometry.attributes.position;
      for(let j=0;j<a.count;j++){const t=j/(a.count-1),v=1-t,p=from.clone().multiplyScalar(v*v).addScaledVector(middle,2*v*t).addScaledVector(to,t*t);a.setXYZ(j,p.x,p.y,p.z);}a.needsUpdate=true;tether.geometry.computeBoundingSphere();
    });
    const bridgeRise=smooth((trackProgress-.48)/.08);bridge.visible=bridgeRise>.001;bridge.position.copy(bframe.normal).multiplyScalar(radius-.27*(1-bridgeRise));bridge.scale.y=.02+.98*bridgeRise;
  }
  function dispose(){if(disposed)return;disposed=true;for(const geometry of geometries)geometry.dispose();for(const m of materials)m.dispose();group.removeFromParent();}
  setState();return {group,setState,trackFrame,dispose,parts:{globe,cars,wheelAxles,features,bridge,rails:railMeshes,ties}};
}
