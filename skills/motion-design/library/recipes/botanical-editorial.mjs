// Original photographic motion grammar: related crops, radial shutters and a full hero.
// The caller loads an image, chooses shots and supplies absolute state. No clock lives here.
export function createBotanicalEditorial({image,width=1920,height=1080}={}){
  if(!image?.width||!image?.height)throw new Error('A decoded image is required');
  const clamp=v=>Math.max(0,Math.min(1,v));
  // Feather only the asset's outer margin so its dark plate does not form a rectangle.
  const prepared=document.createElement('canvas');prepared.width=image.width;prepared.height=image.height;
  const pc=prepared.getContext('2d',{willReadFrequently:true});pc.drawImage(image,0,0);pc.globalCompositeOperation='destination-in';
  for(const axis of ['x','y']){
    const g=pc.createLinearGradient(0,0,axis==='x'?image.width:0,axis==='y'?image.height:0);
    g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(.025,'#000');g.addColorStop(.975,'#000');g.addColorStop(1,'rgba(0,0,0,0)');
    pc.fillStyle=g;pc.fillRect(0,0,image.width,image.height);
  }
  function photograph(ctx,{focus=[.5,.5],zoom=1,rotation=0}={}){
    const cover=Math.max(width/image.width,height/image.height)*zoom;
    ctx.save();ctx.translate(width/2,height/2);ctx.rotate(rotation);
    ctx.drawImage(prepared,-image.width*focus[0]*cover,-image.height*focus[1]*cover,image.width*cover,image.height*cover);ctx.restore();
  }
  function background(ctx){
    ctx.fillStyle='#050306';ctx.fillRect(0,0,width,height);
    const g=ctx.createRadialGradient(width*.49,height*.46,0,width*.5,height*.5,width*.65);
    g.addColorStop(0,'#190e25');g.addColorStop(1,'#030305');ctx.fillStyle=g;ctx.fillRect(0,0,width,height);
  }
  function hero(ctx,{zoom=.86,rotation=0}={}){
    ctx.save();ctx.globalCompositeOperation='screen';photograph(ctx,{focus:[.5,.49],zoom,rotation});ctx.restore();
  }
  function radial(ctx,{opening=1,twist=0,zoom=.86,sectors=14}={}){
    const radius=Math.hypot(width,height),step=Math.PI*2/sectors;
    for(let i=0;i<sectors;i++){
      const a=i*step-Math.PI/2,delay=i/sectors*.35,k=clamp((opening-delay)/.65);
      if(k<=0)continue;
      ctx.save();ctx.translate(width/2,height/2);ctx.rotate(a);
      ctx.beginPath();ctx.moveTo(0,0);ctx.arc(0,0,radius,-.001,step*k+.001);ctx.closePath();ctx.clip();
      ctx.rotate(-a);ctx.translate(-width/2,-height/2);
      hero(ctx,{zoom:zoom+(1-k)*.22,rotation:twist*(1-k)});ctx.restore();
    }
  }
  function strips(ctx,{progress=0,fromFocus=[.65,.30],toFocus=[.5,.49],fromZoom=2.25,toZoom=.86,columns=12}={}){
    photograph(ctx,{focus:fromFocus,zoom:fromZoom});
    for(let i=0;i<columns;i++){
      const delay=(i%2===0?i:columns-i)/columns*.30,k=clamp((progress-delay)/.7),w=width/columns;
      if(k<=0)continue;
      ctx.save();ctx.beginPath();ctx.rect(i*w,0,w+1,height*k);ctx.clip();
      photograph(ctx,{focus:toFocus,zoom:toZoom+(1-k)*.04});ctx.restore();
    }
  }
  function render(ctx,{mode='hero',...state}={}){
    ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';background(ctx);
    if(mode==='macro')photograph(ctx,state);
    else if(mode==='radial')radial(ctx,state);
    else if(mode==='strips')strips(ctx,state);
    else hero(ctx,state);
    ctx.restore();
  }
  return {render,photograph,hero,radial,strips};
}
