import * as THREE from 'three';

// Original sculptural insect. All state is absolute; the host owns time and staging.
export function createChromeBeetle({size=1, shellMaterial, darkMaterial, accentMaterial, membraneMaterial}={}) {
  if(!Number.isFinite(size)||size<=0)throw new Error('size must be positive and finite');
  const group=new THREE.Group();group.name='chrome-beetle';group.scale.setScalar(size);
  const owned=[],geometries=[];
  const makeMaterial=(provided,parameters)=>{if(provided)return provided;const m=new THREE.MeshPhysicalMaterial(parameters);owned.push(m);return m;};
  const shell=makeMaterial(shellMaterial,{color:'#d5e0ea',metalness:1,roughness:.17,clearcoat:1,clearcoatRoughness:.12,iridescence:.65,iridescenceIOR:1.36,iridescenceThicknessRange:[150,430]});
  const dark=makeMaterial(darkMaterial,{color:'#192032',metalness:.87,roughness:.28,clearcoat:.65});
  const accent=makeMaterial(accentMaterial,{color:'#d1ab67',metalness:.95,roughness:.23});
  const membrane=makeMaterial(membraneMaterial,{color:'#c78534',metalness:.14,roughness:.23,transparent:true,opacity:.34,transmission:.66,thickness:.018,side:THREE.DoubleSide,depthWrite:false,iridescence:.4});
  const eye=makeMaterial(null,{color:'#061720',metalness:.68,roughness:.12,clearcoat:1});
  const geometry=g=>{geometries.push(g);return g;};
  const mesh=(g,m,name,parent=group)=>{const object=new THREE.Mesh(geometry(g),m);object.name=name;object.castShadow=true;object.receiveShadow=true;parent.add(object);return object;};
  const ball=(p,s,m,name,parent=group,detail=48)=>{const o=mesh(new THREE.SphereGeometry(1,detail,Math.round(detail*.65)),m,name,parent);o.position.set(...p);o.scale.set(...s);return o;};
  const vec=p=>new THREE.Vector3(...p);
  const tube=(points,radius,m,name,parent=group)=>mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(vec)),Math.max(12,points.length*8),radius,7,false),m,name,parent);
  const rod=(from,to,r0,r1,m,name,parent=group)=>{const a=vec(from),b=vec(to),d=b.clone().sub(a);const o=mesh(new THREE.CylinderGeometry(r1,r0,d.length(),9),m,name,parent);o.position.copy(a).add(b).multiplyScalar(.5);o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return o;};
  const abdomen=ball([0,-.55,-.08],[.99,1.58,.40],dark,'ventral-abdomen');
  // A segmented ventral body remains visible between the raised wing cases.
  for(let i=0;i<7;i++){
    const y=-1.82+i*.34,w=.95*Math.sqrt(Math.max(.02,1-((y+.5)/1.64)**2));
    const points=Array.from({length:19},(_,j)=>{const a=j*Math.PI/18;return [w*Math.cos(a),y,.045+.22*Math.sin(a)];});
    tube(points,.019,i%2?dark:accent,'abdominal-suture-'+i);
  }
  const thorax=ball([0,.99,.20],[.83,.68,.50],shell,'sculpted-pronotum');
  thorax.rotation.x=-.1;
  for(const side of [-1,1])tube([[side*.70,.65,.36],[side*.78,1.02,.38],[side*.60,1.45,.35]],.024,accent,'pronotum-edge');
  const head=ball([0,1.74,.17],[.54,.45,.33],shell,'head');
  for(const side of [-1,1]){
    ball([side*.46,1.85,.21],[.21,.255,.22],eye,'compound-eye');
    tube([[side*.21,2.00,.12],[side*.30,2.28,.05],[side*.16,2.43,.05],[side*.075,2.32,.08]],.051,accent,'mandible');
  }
  const cases=[];
  const shellPoint=(side,t,theta)=>{const w=1.07*Math.pow(Math.sin(Math.PI*.66*t),.56),h=.60*Math.pow(Math.sin(Math.PI*(.07+.82*t)),.6);const c=Math.cos(theta);return [side*(.023+w*Math.sin(theta)),-2.08+2.83*t,.16+h*(c>=0?c:.16*c)];};
  for(const side of [-1,1]){
    const hinge=new THREE.Group();hinge.name=(side<0?'left':'right')+'-elytron-hinge';hinge.position.set(side*.40,.68,.25);group.add(hinge);cases.push(hinge);
    const points=[],uv=[],indices=[],rows=50,columns=32;
    for(let i=0;i<=rows;i++)for(let j=0;j<=columns;j++){
      const p=shellPoint(side,i/rows,j/columns*Math.PI);points.push(p[0]-hinge.position.x,p[1]-hinge.position.y,p[2]-hinge.position.z);uv.push(j/columns,i/rows);
      if(i<rows&&j<columns){const a=i*(columns+1)+j,b=a+columns+1;indices.push(...(side>0?[a,a+1,b,b,a+1,b+1]:[a,b,a+1,b,b+1,a+1]));}
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();
    mesh(g,shell,'iridescent-elytron',hinge);
    for(const theta of [.20,.41,.63,.85,1.09,1.35]){
      const p=Array.from({length:30},(_,i)=>{const q=shellPoint(side,.07+.88*i/29,theta);return [q[0]-hinge.position.x,q[1]-hinge.position.y,q[2]-hinge.position.z+.007];});
      tube(p,.009,dark,'elytron-engraved-ridge',hinge);
    }
    const edge=Array.from({length:40},(_,i)=>{const p=shellPoint(side,i/39,Math.PI/2);return [p[0]-hinge.position.x,p[1]-hinge.position.y,p[2]-hinge.position.z];});
    tube(edge,.022,accent,'elytron-edge',hinge);
    ball([0,0,0],[.14,.17,.13],accent,'elytron-pivot',hinge,24);
  }
  const flightWings=[];
  const wingZ=(x,y)=>.08*Math.sin(x*.85)+y*.025;
  for(const side of [-1,1]){
    const root=new THREE.Group();root.name=(side<0?'left':'right')+'-flight-wing';root.position.set(side*.43,.61,.14);group.add(root);
    const distal=new THREE.Group();distal.name='folding-wing-tip';distal.position.set(side*1.48,-.32,wingZ(1.48,-.32));root.add(distal);
    function panel(outline,parent,origin){
      const shape=new THREE.Shape();outline.forEach(([x,y],i)=>{const p=[side*(x-origin[0]),y-origin[1]];if(i===0)shape.moveTo(...p);else shape.lineTo(...p);});shape.closePath();
      const g=new THREE.ShapeGeometry(shape,20),p=g.attributes.position;
      for(let i=0;i<p.count;i++){const x=p.getX(i)*side+origin[0],y=p.getY(i)+origin[1];p.setZ(i,wingZ(x,y)-origin[2]);}g.computeVertexNormals();
      const o=mesh(g,membrane,'amber-wing-membrane',parent);o.castShadow=false;o.receiveShadow=false;o.renderOrder=2;
    }
    const base=[[0,0],[.47,.16],[1.48,-.04],[1.48,-1.32],[.85,-1.13],[.30,-.61]];
    const outer=[[1.48,-.04],[2.63,-.30],[3.43,-.93],[3.53,-1.28],[3.03,-1.73],[2.13,-1.83],[1.48,-1.32]];
    panel(base,root,[0,0,0]);panel(outer,distal,[1.48,-.32,wingZ(1.48,-.32)]);
    const vein=(path,parent,origin,r=.009)=>tube(path.map(([x,y])=>[side*(x-origin[0]),y-origin[1],wingZ(x,y)-origin[2]+.009]),r,accent,'wing-vein',parent);
    vein([...base,base[0]],root,[0,0,0],.013);vein([...outer,outer[0]],distal,[1.48,-.32,wingZ(1.48,-.32)],.013);
    vein([[0,0],[.55,-.3],[1.48,-.45]],root,[0,0,0]);vein([[0,0],[.7,-.73],[1.48,-1.13]],root,[0,0,0]);
    const origin=[1.48,-.32,wingZ(1.48,-.32)];
    for(const path of [[[1.48,-.45],[2.4,-.6],[3.43,-.93]],[[1.48,-.45],[2.05,-1.05],[3.03,-1.73]],[[1.48,-1.13],[2.13,-1.83]],[[2.4,-.6],[2.7,-1.1],[3.53,-1.28]],[[2.05,-1.05],[2.7,-1.1]],[[2.05,-1.05],[2.55,-1.48]]])vein(path,distal,origin);
    flightWings.push({root,distal,side});
  }
  const legs=[];
  for(const side of [-1,1])for(let i=0;i<3;i++){
    const y=[.82,.13,-.69][i],dy=[.50,-.14,-.61][i];
    const hip=new THREE.Group();hip.name=`leg-${side}-${i}-hip`;hip.position.set(side*.64,y,-.11);group.add(hip);
    const knee=[side*.69,dy,-.22];
    ball([0,0,0],[.16,.19,.15],accent,'coxa',hip,24);
    rod([0,0,0],knee,.12,.081,shell,'femur',hip);
    const shin=new THREE.Group();shin.name='tibia-hinge';shin.position.set(...knee);hip.add(shin);
    const end=[side*.40,dy*.62,-.64];
    ball([0,0,0],[.102,.105,.102],dark,'knee',shin,24);
    rod([0,0,0],end,.064,.028,shell,'tibia',shin);
    // Small backward-facing tibial spurs make the legs read as insect appendages.
    for(let n=1;n<=3;n++){const u=n/4,p=end.map(v=>v*u);rod(p,[p[0]+side*.09,p[1]-.08,p[2]+.01],.022,.002,accent,'tibial-spur',shin);}
    tube([end,[end[0]+side*.14,end[1]+dy*.25,end[2]-.025],[end[0]+side*.25,end[1]+dy*.43,end[2]-.01]],.025,accent,'tarsus',shin);
    for(const q of [-1,1])tube([[end[0]+side*.23,end[1]+dy*.42,end[2]],[end[0]+side*.30,end[1]+dy*.45+q*.055,end[2]-.025]],.012,dark,'tarsal-claw',shin);
    legs.push({hip,shin,side,index:i});
  }
  const antennae=[];
  for(const side of [-1,1]){
    const root=new THREE.Group();root.name='antenna-root';root.position.set(side*.38,2.00,.20);group.add(root);
    const path=[[0,0,0],[side*.22,.24,.09],[side*.42,.49,.20],[side*.52,.77,.27],[side*.64,1.03,.29]];
    for(let i=0;i<path.length-1;i++){rod(path[i],path[i+1],.028-i*.004,.024-i*.004,accent,'antenna-segment',root);ball(path[i+1],[.028,.035,.028],dark,'antenna-joint',root,16);}
    antennae.push({root,side});
  }
  const clamp=n=>Math.max(0,Math.min(1,n));let disposed=false;
  function setState({wingOpen=0,unfurl=0,flight=0,legTuck=0,flapPhase=0,antennaSweep=0}={}){
    if(disposed)throw new Error('Chrome beetle has been disposed');
    if(![wingOpen,unfurl,flight,legTuck,flapPhase,antennaSweep].every(Number.isFinite))throw new Error('Beetle state must be finite');
    const open=clamp(wingOpen),spread=clamp(unfurl),air=clamp(flight),tuck=clamp(legTuck);
    cases.forEach((hinge,i)=>{const side=i===0?-1:1;hinge.rotation.set(-open*.09,-side*open*1.02,side*open*.29);});
    flightWings.forEach(({root,distal,side})=>{root.visible=spread>.002;root.rotation.set(0,-side*(.02+Math.sin(flapPhase)*.42*air),side*(-.40*(1-spread)));distal.rotation.set(0,-side*(1-spread)*.12,-side*(1-spread)*2.50);});
    legs.forEach(({hip,shin,side,index})=>{hip.rotation.set(tuck*.10,-side*tuck*.62,side*tuck*([-.10,.12,.20][index]));shin.rotation.y=side*tuck*.98;});
    antennae.forEach(({root,side})=>{root.rotation.set(.08*air,side*antennaSweep*.10,side*(.06*air+antennaSweep*.13));});
  }
  function dispose(){if(disposed)return;disposed=true;for(const g of geometries)g.dispose();for(const m of owned)m.dispose();group.removeFromParent();}
  setState();
  return {group,setState,dispose,parts:{abdomen,thorax,head,cases,flightWings,legs,antennae}};
}
