import * as THREE from 'three';

// Original distance-field type surface. Font loading and scene time belong to the caller.
export function createLiquidWord({text='MELT',fontFamily='Sora',weight=800,width=1920,height=1080}={}) {
  const W=1920,H=1080,canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  ctx.font=`${weight} 430px "${fontFamily}"`;
  const fontSize=Math.min(430,1580/ctx.measureText(text).width*430);
  ctx.font=`${weight} ${fontSize}px "${fontFamily}"`;ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.fillStyle='#fff';ctx.fillText(text,W/2,H*.47);
  const alpha=ctx.getImageData(0,0,W,H).data;
  // Separable exact squared Euclidean transform, following the lower-envelope
  // construction of Felzenszwalb and Huttenlocher (Theory of Computing, 2012).
  // Finite background costs also make entirely empty scanlines well-defined.
  function transform(inside){
    const d=new Float64Array(W*H),n=Math.max(W,H);
    const f=new Float64Array(n),out=new Float64Array(n),v=new Int32Array(n),z=new Float64Array(n+1);
    for(let i=0;i<d.length;i++)d[i]=(alpha[i*4+3]>127)===inside?0:1e12;
    function line(length){
      let k=0;v[0]=0;z[0]=-Infinity;z[1]=Infinity;
      for(let q=1;q<length;q++){
        let s=((f[q]+q*q)-(f[v[k]]+v[k]*v[k]))/(2*(q-v[k]));
        while(s<=z[k]){k--;s=((f[q]+q*q)-(f[v[k]]+v[k]*v[k]))/(2*(q-v[k]));}
        k++;v[k]=q;z[k]=s;z[k+1]=Infinity;
      }
      k=0;
      for(let q=0;q<length;q++){while(z[k+1]<q)k++;out[q]=(q-v[k])**2+f[v[k]];}
    }
    for(let x=0;x<W;x++){for(let y=0;y<H;y++)f[y]=d[y*W+x];line(H);for(let y=0;y<H;y++)d[y*W+x]=out[y];}
    for(let y=0;y<H;y++){for(let x=0;x<W;x++)f[x]=d[y*W+x];line(W);for(let x=0;x<W;x++)d[y*W+x]=Math.sqrt(out[x]);}
    return d;
  }
  const toInk=transform(true),toAir=transform(false),pixels=new Float32Array(W*H);
  let first=W,last=0;
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){
    const i=y*W+x,j=(H-1-y)*W+x;pixels[j]=(toAir[i]-toInk[i]);
    if(alpha[i*4+3]>127){first=Math.min(first,x);last=Math.max(last,x);}
  }
  // A three-pixel Gaussian removes raster stair-step noise from the bevel normals.
  const smooth=new Float32Array(W*H),radius=8,kernel=Array.from({length:17},(_,i)=>Math.exp(-((i-radius)**2)/18));
  const total=kernel.reduce((a,b)=>a+b,0);
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){let sum=0;for(let k=-radius;k<=radius;k++)sum+=pixels[y*W+Math.max(0,Math.min(W-1,x+k))]*kernel[k+radius];smooth[y*W+x]=sum/total;}
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){let sum=0;for(let k=-radius;k<=radius;k++)sum+=smooth[Math.max(0,Math.min(H-1,y+k))*W+x]*kernel[k+radius];pixels[y*W+x]=sum/total;}
  const anchors=[];
  for(let i=0;i<8;i++){
    const x=Math.round(first+(last-first)*(.035+i*.93/7));let bottom=H*.55;
    for(let y=H-1;y>=0;y--)if(alpha[(y*W+x)*4+3]>127){bottom=y;break;}
    anchors.push(new THREE.Vector2(x/W,1-bottom/H));
  }
  const texture=new THREE.DataTexture(pixels,W,H,THREE.RedFormat,THREE.FloatType);texture.minFilter=texture.magFilter=THREE.LinearFilter;texture.needsUpdate=true;
  const uniforms={uMask:{value:texture},uMelt:{value:0},uPhase:{value:0},uResolution:{value:new THREE.Vector2(width,height)},uAnchors:{value:anchors}};
  const material=new THREE.ShaderMaterial({uniforms,depthTest:false,depthWrite:false,vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}`,fragmentShader:`
    precision highp float;varying vec2 vUv;uniform sampler2D uMask;uniform float uMelt,uPhase;uniform vec2 uResolution;uniform vec2 uAnchors[8];
    float unite(float a,float b,float k){float h=clamp(.5+.5*(a-b)/k,0.,1.);return mix(b,a,h)+k*h*(1.-h);}
    float ellipse(vec2 p,vec2 center,vec2 radius){return (1.-length((p-center)/radius))*min(radius.x,radius.y)*1080.;}
    float surface(vec2 uv){
      float m=uMelt;float phase=uPhase;
      vec2 q=uv;
      q.x=.5+(uv.x-.5)/(1.+.12*m);
      float slump=m*(.11+.027*sin(uv.x*25.+.5)+.015*sin(uv.x*61.));
      q.y=.53+(uv.y-.53+slump)/(1.-.66*m);
      q.x+=m*.012*sin(q.y*37.+phase*1.8+q.x*10.);
      q.y+=m*.017*sin(q.x*32.+phase*.7);
      float glyph=texture2D(uMask,clamp(q,vec2(.001),vec2(.999))).r*(1.-.50*m);
      if(q.x<0.||q.x>1.||q.y<0.||q.y>1.)glyph=-200.;
      glyph-=smoothstep(.55,.93,m)*80.;
      float fill=smoothstep(.08,.95,m);
      float pool=ellipse(uv,vec2(.5,.27+.10*smoothstep(.5,1.,m)),vec2(.01+.36*fill,.001+.065*fill));
      pool+=sin(uv.x*42.+phase)*3.*fill;
      pool-=40.*(1.-smoothstep(.08,.3,m));
      float f=unite(glyph,pool,12.*m+.01);
      for(int i=0;i<8;i++){
        float a=float(i),x=.5+(uAnchors[i].x-.5)*(1.+.12*m);
        float drip=smoothstep(.12,.42,m)*(1.-smoothstep(.64,.98,m));
        float slump=m*(.11+.027*sin(x*25.+.5)+.015*sin(x*61.));
        float top=.53+(uAnchors[i].y-.53)*(1.-.66*m)-slump+.018;
        float bottom=.29+.10*smoothstep(.5,1.,m);
        float mid=(top+bottom)*.5;
        float drop=ellipse(uv,vec2(x+.002*sin(phase+a),mid),vec2(.004+.005*drip,max(.008,(top-bottom)*.55)));
        drop-=35.*(1.-drip);
        f=unite(f,drop,19.*drip+.01);
      }
      return f;
    }
    void main(){
      vec2 uv=vUv;float f=surface(uv),edge=smoothstep(-1.2,1.2,f);
      vec2 e=2./uResolution;
      float gx=(surface(uv+vec2(e.x,0.))-surface(uv-vec2(e.x,0.)))*.25;
      float gy=(surface(uv+vec2(0.,e.y))-surface(uv-vec2(0.,e.y)))*.25;
      float roundness=clamp(f/22.,0.,1.);
      vec3 n=normalize(vec3(-gx*1.1,-gy*1.1,.7+roundness*3.4));
      vec3 light=normalize(vec3(-.5,.9,1.));float diffuse=max(dot(n,light),0.);
      float spec=pow(max(dot(reflect(-light,n),vec3(0.,0.,1.)),0.),24.);
      float strip=pow(max(0.,sin(uv.y*4.8+uv.x*.8+uMelt*.8)),20.);
      vec3 body=vec3(1.,.69,.025)*(.62+.5*diffuse);
      body+=vec3(1.,.92,.58)*(spec*.52+strip*.12);
      body*=.88+.12*smoothstep(0.,7.,f);
      vec3 bg=mix(vec3(.045,.035,.42),vec3(.09,.115,.78),smoothstep(.8,.05,distance(uv,vec2(.45,.6))));
      float shade=smoothstep(-3.,3.,surface(uv+vec2(.006,.010)))*(1.-edge)*.27;
      bg*=1.-shade;
      gl_FragColor=vec4(mix(bg,body,edge),1.);
      #include <colorspace_fragment>
    }`});
  const geometry=new THREE.PlaneGeometry(2,2),mesh=new THREE.Mesh(geometry,material);mesh.frustumCulled=false;
  function setState({liquefaction=0,phase=0}={}){if(!Number.isFinite(liquefaction)||!Number.isFinite(phase))throw new Error('finite state required');uniforms.uMelt.value=THREE.MathUtils.clamp(liquefaction,0,1);uniforms.uPhase.value=phase;}
  return {mesh,setState,dispose(){geometry.dispose();material.dispose();texture.dispose();mesh.removeFromParent();}};
}
