import { App, applyDocumentTheme } from "@modelcontextprotocol/ext-apps";
const app = new App({ name: "Video preview", version: "3.0.0" });
const $ = (id) => document.getElementById(id);
let media, shown, mediaProject, pendingMedia, refreshState, refreshInFlight=false;
let followProject=true, mediaRenewal=null, tornDown=false, blockedEmbedKey;
let referencePoster;
const reportedEmbedFailures=new Set();
const REFRESH_INTERVAL_MS=5000,IDLE_REFRESH_INTERVAL_MS=30000;
function unpack(result) {
  if (result.isError) throw Error("This preview could not be loaded.");
  const data = result.structuredContent;
  if (data?.media) return data.media;
  // Previously opened conversations can still supply the older result shape.
  const project = data?.project_card || data;
  if (project) {
    const values = (project.updates || []).filter(u => u.preview && u.stage !== "review").map(u => ({...u.preview, at:u.at, caption:u.note}));
    for (const r of project.revisions || []) values.push({object_id:r.video, media_type:"video/mp4",url:r.video_url,download_url:r.download_url,at:r.created});
    values.sort((a,b) => new Date(a.at)-new Date(b.at));
    if (values.length) return values.at(-1);
  }
  return null;
}
function playing(){
  const element=$('media').firstElementChild;
  return element?.tagName==='VIDEO' && element.paused===false && !element.ended;
}
function stopRefresh(keepPending=false){
  const state=refreshState;refreshState=null;
  if(state)clearTimeout(state.timer);
  if(!keepPending)pendingMedia=null;
}
function settlePlayback(element){
  if(element!==$('media').firstElementChild || playing() || !pendingMedia)return;
  const next=pendingMedia;pendingMedia=null;render(next);
}
function present(next){
  if(!next)return;
  const key=next.object_id || next.embed_url || next.url;
  if(shown!==key && playing()){
    pendingMedia=next;
    $('media-status').textContent=next.final===true?'Final video ready · updates after playback.':'New sample ready · updates after playback.';
  }else{pendingMedia=null;render(next);}
}
function scheduleRefresh(state){
  if(refreshState!==state || state.timer || document.hidden===true)return;
  const delay=Date.now()-state.started<60000?REFRESH_INTERVAL_MS:IDLE_REFRESH_INTERVAL_MS;
  state.timer=setTimeout(()=>pollPreview(state),delay);
}
async function pollPreview(state){
  state.timer=null;
  if(refreshState!==state || document.hidden===true)return;
  if(!app.getHostCapabilities?.()?.serverTools){stopRefresh(true);return;}
  // Calls are read-only and app-initiated. Keep following while the host mounts
  // this player, including after a user spends more than ten minutes choosing.
  if(refreshInFlight){scheduleRefresh(state);return;}
  refreshInFlight=true;
  try{
    const result=await app.callServerTool({name:'video_preview_updates',arguments:{project_id:state.projectId}});
    if(refreshState!==state)return;
    const data=readData(result);
    if(data.project_id!==state.projectId || !data.media)throw Error('No matching preview');
    state.failures=0;present(data.media);
    if(data.media.final===true){stopRefresh(true);return;}
  }catch{
    if(refreshState===state && ++state.failures>=3){
      stopRefresh(true);
      $('notice').textContent='Live updates paused. Return to this chat to retry, or ask to show the video again.';
      return;
    }
  }finally{refreshInFlight=false;}
  scheduleRefresh(state);
}
function startRefresh(){
  if(tornDown || !followProject || !mediaProject || media?.final===true || !app.getHostCapabilities?.()?.serverTools || refreshState)return;
  const state={projectId:mediaProject,started:Date.now(),failures:0,timer:null};
  refreshState=state;scheduleRefresh(state);
}
function receiveMediaResult(result){
  const next=unpack(result);
  if(!next){stopRefresh();return;}
  tornDown=false;
  const data=result.structuredContent;
  const projectId=data?.project_id || data?.project_card?.id || data?.id;
  followProject=data?.follow_project!==false && !next.source_url;
  if(projectId!==mediaProject){stopRefresh();mediaProject=projectId;render(next);}
  else present(next);
  if(!followProject || next.final===true){stopRefresh(true);return;}
  startRefresh();
}
function loadSource(element,next,keepPosition=false){
  const seconds=keepPosition && Number.isFinite(element.currentTime)?element.currentTime:0;
  element.onloadedmetadata=()=>{
    if(element!==$('media').firstElementChild)return;
    if(seconds>0)element.currentTime=Number.isFinite(element.duration)?Math.min(seconds,element.duration):seconds;
  };
  element.src=next.url;
}
async function renewMedia(element,{reload=false}={}){
  const projectId=mediaProject,objectId=media?.object_id;
  if(tornDown || !followProject || !projectId || !objectId || !app.getHostCapabilities?.()?.serverTools)return false;
  if(mediaRenewal)return mediaRenewal;
  const promise=(async()=>{
    try{
      const data=readData(await app.callServerTool({name:'video_preview_updates',arguments:{project_id:projectId,object_id:objectId}}));
      if(tornDown || projectId!==mediaProject || objectId!==media?.object_id || element!==$('media').firstElementChild)return false;
      if(data.project_id!==projectId || data.media?.object_id!==objectId)throw Error('The saved preview is unavailable.');
      media={...media,...data.media};
      if(reload)loadSource(element,media,true);
      $('download').href=media.download_url || media.url;
      $('notice').textContent='';return true;
    }catch{
      if(!tornDown && projectId===mediaProject && objectId===media?.object_id)$('notice').textContent='This video could not be refreshed. Ask to show it again.';
      return false;
    }
  })();
  mediaRenewal=promise;
  try{return await promise;}finally{if(mediaRenewal===promise)mediaRenewal=null;}
}
let xWidgetPromise;
function xWidget(){
  if(globalThis.twttr?.widgets?.createTweet)return Promise.resolve(globalThis.twttr.widgets);
  if(xWidgetPromise)return xWidgetPromise;
  xWidgetPromise=new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    const timeout=setTimeout(()=>reject(Error('X embed unavailable')),8000);
    script.src='https://platform.twitter.com/widgets.js';script.async=true;
    script.onload=()=>{clearTimeout(timeout);const widgets=globalThis.twttr?.widgets;widgets?.createTweet?resolve(widgets):reject(Error('X embed unavailable'));};
    script.onerror=()=>{clearTimeout(timeout);reject(Error('X embed unavailable'));};
    document.head.append(script);
  });
  return xWidgetPromise;
}
async function renderXPost(element,next){
  try{
    if(!/^[0-9]{5,24}$/.test(String(next.post_id)))throw Error('Invalid post');
    const widgets=await xWidget();
    if(tornDown || element!==$('media').firstElementChild)return;
    // Only a validated post ID reaches the official factory. Never insert
    // returned oEmbed HTML or let a source choose a script URL.
    let timeout;
    const frame=await Promise.race([
      widgets.createTweet(String(next.post_id),element,{align:'center',dnt:true,conversation:'none'}),
      new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('X embed unavailable')),8000);}),
    ]).finally(()=>clearTimeout(timeout));
    if(tornDown || element!==$('media').firstElementChild)return;
    if(!frame)throw Error('X embed unavailable');
    if(currentReferenceFrames().some(frame=>hostAllowsFrame(frame.src)===false))blockedReference(element);
  }catch{
    if(!tornDown && element===$('media').firstElementChild && blockedEmbedKey!==shown)$('notice').textContent='This X post cannot be displayed here. Open the source link below.';
  }
}
function currentReferenceFrames(){
  const element=$('media').firstElementChild;
  if(element?.tagName==='IFRAME')return [element];
  if(media?.media_type!=='social/x' || !element?.classList.contains('social-post'))return [];
  return [...element.querySelectorAll('iframe')].filter(frame=>{
    try{return ['https://platform.twitter.com','https://platform.x.com'].includes(new URL(frame.src).origin);}catch{return false;}
  });
}
function hostAllowsFrame(url,context=app.getHostContext?.()){
  const domains=context?.csp?.frameDomains ?? app.getHostCapabilities?.()?.sandbox?.csp?.frameDomains;
  if(!Array.isArray(domains))return undefined; // Missing host information is not a denial.
  let target;try{target=new URL(url);}catch{return undefined;}
  let unknown=false;
  for(const domain of domains){
    if(domain==='*' || domain===target.protocol)return true;
    if(domain==="'none'")continue;
    if(domain==="'self'"){
      if(!globalThis.location?.origin){unknown=true;continue;}
      if(target.origin===globalThis.location.origin)return true;
      continue;
    }
    try{
      const allowed=new URL(domain);
      if(allowed.pathname!=='/' || allowed.search || allowed.hash){unknown=true;continue;}
      if(target.origin===allowed.origin)return true;
      if(allowed.hostname.startsWith('*.') && target.protocol===allowed.protocol && target.port===allowed.port
        && target.hostname.endsWith(allowed.hostname.slice(1)))return true;
    }catch{unknown=true;}
  }
  return unknown?undefined:false;
}
function youtubePosterUrl(next){
  if(next.provider!=='youtube' || !next.source_url || typeof next.poster_url!=='string')return null;
  try{
    const source=new URL(next.source_url),poster=new URL(next.poster_url);
    if(source.protocol!=='https:' || source.username || source.password || source.port
      || poster.origin!=='https://i.ytimg.com' || poster.username || poster.password || poster.hash)return null;
    let id;
    if(source.hostname==='youtu.be')id=source.pathname.slice(1);
    else if(['youtube.com','www.youtube.com','m.youtube.com'].includes(source.hostname)){
      id=source.pathname==='/watch'?source.searchParams.get('v'):source.pathname.match(/^\/(?:shorts|live)\/([^/]+)$/)?.[1];
    }
    if(!/^[a-zA-Z0-9_-]{11}$/.test(id || ''))return null;
    const path=poster.pathname.match(/^\/(vi|vi_webp)\/([a-zA-Z0-9_-]{11})\/(?:default|mqdefault|hqdefault|sddefault|maxresdefault|[0-3])(?:_live)?\.(jpg|webp)$/);
    if(!path || path[2]!==id || (path[1]==='vi'?path[3]!=='jpg':path[3]!=='webp'))return null;
    return poster.href;
  }catch{return null;}
}
function clearReferencePoster(){
  if(referencePoster){referencePoster.image.onload=null;referencePoster.image.onerror=null;}
  referencePoster=null;
  const link=$('reference-poster');link.hidden=true;link.removeAttribute('href');link.replaceChildren();
}
function showReferencePoster(next){
  const url=youtubePosterUrl(next),link=$('reference-poster');
  if(!url){clearReferencePoster();return;}
  const key=next.source_url+'|'+url;
  if(referencePoster?.key===key){link.hidden=referencePoster.status!=='loaded';return;}
  clearReferencePoster();
  const image=document.createElement('img'),label=document.createElement('span');
  const state={key,image,status:'loading'};referencePoster=state;
  image.alt=next.title?`Thumbnail for ${next.title}`:'YouTube source thumbnail';
  image.referrerPolicy='no-referrer';
  label.textContent='Watch on YouTube ↗';
  link.href=next.source_url;link.setAttribute('aria-label','Watch the original source on YouTube · opens YouTube');
  link.append(image,label);
  image.onload=()=>{
    if(tornDown || referencePoster!==state)return;
    state.status='loaded';link.hidden=false;$('media-status').textContent='Video thumbnail';
  };
  image.onerror=()=>{
    if(tornDown || referencePoster!==state)return;
    state.status='failed';link.hidden=true;link.replaceChildren();$('media-status').textContent=media?.caption || 'Source reference';
  };
  image.src=url;
}
function blockedReference(element){
  if(tornDown || !media?.source_url || element!==$('media').firstElementChild)return;
  blockedEmbedKey=shown;$('media').hidden=true;
  $('source-playback-hint').hidden=false;
  $('source-playback-hint').textContent='This chat blocked the embedded player. Open the original source using the link above.';
  showReferencePoster(media);
  const source=media.source_url;
  if(!reportedEmbedFailures.has(source) && app.getHostCapabilities?.()?.updateModelContext?.text){
    reportedEmbedFailures.add(source);
    try{Promise.resolve(app.updateModelContext({content:[{type:'text',text:`Reference embed display: blocked by the chat content security policy. Source: ${source}. Its description and source link remain visible; playback was not verified.`}]})).catch(()=>{});}catch{}
  }
}
document.addEventListener('securitypolicyviolation',event=>{
  const element=$('media').firstElementChild;
  if(tornDown || event.isTrusted===false || event.disposition!=='enforce'
    || !['frame-src','child-src'].includes(event.effectiveDirective || event.violatedDirective?.split(' ')[0]))return;
  try{
    const blocked=new URL(event.blockedURI);
    // Browsers may strip a cross-origin blocked URL down to its origin.
    if(currentReferenceFrames().some(frame=>{
      const current=new URL(frame.src);
      return blocked.href===current.href || (blocked.origin===current.origin && blocked.pathname==='/' && !blocked.search && !blocked.hash);
    }))blockedReference(element);
  }catch{} // Empty/inline/opaque reports do not identify this iframe.
});
// TikTok documents these player events. Only the currently displayed provider
// iframe may report an error; a load event or elapsed time is not playback proof.
globalThis.addEventListener?.('message',event=>{
  const element=$('media').firstElementChild;
  if(tornDown || element?.tagName!=='IFRAME' || element.getAttribute('data-provider')!=='tiktok'
    || !element.contentWindow || event.source!==element.contentWindow || event.origin!=='https://www.tiktok.com')return;
  const data=event.data;
  if(!data || typeof data!=='object' || data['x-tiktok-player']!==true)return;
  if(data.type==='onPlayerError' && [1001,2001,3001].includes(data.value?.errorCode)){
    $('source-playback-hint').hidden=false;
    $('source-playback-hint').textContent='TikTok reported a playback problem. Open the original source using the link above.';
  }else if(data.type==='onStateChange' && data.value===1){
    $('source-playback-hint').hidden=true;
    $('source-playback-hint').textContent='';
  }
});
function render(next) {
  if (!next) return;
  media = next;
  const key = next.object_id || next.embed_url || next.url || next.source_url;
  if (shown !== key) {
    blockedEmbedKey=undefined;
    clearReferencePoster();
    const video = ['video/mp4','video/webm'].includes(next.media_type);
    const embed=next.media_type === 'text/html' && next.embed_url;
    const sourceOnly=next.media_type==='source_link';
    const xPost=next.media_type==='social/x';
    const element = document.createElement(sourceOnly?'span':xPost?'div':embed?'iframe':video?'video':'img');
    $('media').hidden=sourceOnly;
    if(xPost){element.className='social-post';element.setAttribute('aria-label','X source post');}
    else if(embed){
      element.setAttribute('data-provider',next.provider || '');
      if(hostAllowsFrame(next.embed_url)!==false)element.src=next.embed_url;
      element.title=next.title || next.caption || 'Video reference';
      element.setAttribute('allow','fullscreen; picture-in-picture');
      element.setAttribute('allowfullscreen','');element.setAttribute('referrerpolicy','strict-origin-when-cross-origin');
      element.setAttribute('sandbox','allow-scripts allow-same-origin allow-presentation');
    }else if(video){
      element.controls=true;element.playsInline=true;element.preload='metadata';
      element.onpause=()=>settlePlayback(element);element.onended=()=>settlePlayback(element);
      let attemptedRepair=false;
      element.onerror=async()=>{
        if(element!==$('media').firstElementChild)return;
        if(!attemptedRepair && followProject){attemptedRepair=true;if(await renewMedia(element,{reload:true}))return;}
        $('notice').textContent=next.source_url?'This source does not allow playback here. Open the reference below.':'This video could not be loaded. Ask to show it again.';
      };
      element.onplay=()=>{attemptedRepair=false;startRefresh();};
      loadSource(element,next);
    }else if(!sourceOnly){element.src=next.url;element.alt=next.caption || 'Proposed video frame';}
    $('media').replaceChildren(element);shown=key;
    if(xPost)renderXPost(element,next);
  }
  $('visual').hidden=false;
  const source=next.source_url;
  $('source-reference').hidden=!source;
  $('source-reference').href=source || '';
  $('source-reference').textContent=next.title || next.caption || 'Open reference';
  for(const [id,field] of [['reference-description','description'],['reference-attribution','attribution'],['reference-evidence','evidence_status']]){
    const text=source && typeof next[field]==='string'?next[field].trim():'';
    $(id).textContent=text;$(id).hidden=!text;
  }
  const embedded=source && ['text/html','social/x'].includes(next.media_type);
  $('source-playback-hint').textContent=embedded?'If playback does not load, open the original source using the link above.':'';
  $('source-playback-hint').hidden=!embedded;
  if(blockedEmbedKey===shown || (next.embed_url && hostAllowsFrame(next.embed_url)===false))blockedReference($('media').firstElementChild);
  else if(source && next.media_type==='source_link')showReferencePoster(next);
  else clearReferencePoster();
  const downloadable=next.media_type==='video/mp4' && !source && Boolean(next.download_url || next.object_id);
  $('download').hidden=!downloadable;
  $('download').href=next.download_url || next.url || '';
  $('media-status').textContent=source?(referencePoster?.status==='loaded'?'Video thumbnail':next.caption || 'Source video'):next.final===true?'Final video':next.media_type==='video/mp4'?'Sample':'';
  $('excerpt').hidden=next.truncated!==true;
  if(next.truncated===true){
    const seconds=Number(next.duration),total=Number(next.source_duration);
    $('excerpt').textContent=Number.isFinite(seconds) && Number.isFinite(total)
      ? `Preview excerpt · ${Math.round(seconds)}s of ${Math.round(total)}s`
      : 'Preview excerpt · the full video is longer';
  }
  $('notice').textContent='';syncDisplayMode();
}
function newFeedbackId(){
  return globalThis.crypto?.randomUUID?.() || `edit-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
async function prepareUserReply(text){
  if(!app.getHostCapabilities?.()?.message?.text)return false;
  try{return !(await app.sendMessage({role:'user',content:[{type:'text',text}]}))?.isError;}catch{return false;}
}
function replyHint(prepared){
  // A host may place this reply in its composer rather than actually send it.
  return prepared?'Send the prepared reply to continue.':'Tell your assistant to continue if the chat is waiting.';
}
$('download').onclick=async(event)=>{
  event?.preventDefault?.();
  const active=media,element=$('media').firstElementChild;
  if(!active)return;
  // Signed downloads expire. Refresh this exact watched version, not whichever
  // draft happens to be newest while a sample review is waiting in chat.
  if(mediaProject && active.object_id && followProject && app.getHostCapabilities?.()?.serverTools && !await renewMedia(element))return;
  if(active.object_id!==media?.object_id || element!==$('media').firstElementChild)return;
  await app.openLink({url:media.download_url || media.url});
};
function openReference(event){
  // The anchor's real href remains usable when the host has no link API.
  if(!media?.source_url || !app.getHostCapabilities?.()?.openLinks || typeof app.openLink!=='function')return;
  event?.preventDefault?.();
  return app.openLink({url:media.source_url});
}
$('source-reference').onclick=openReference;
$('reference-poster').onclick=openReference;
document.addEventListener('visibilitychange',()=>{
  if(document.hidden===true){if(refreshState){clearTimeout(refreshState.timer);refreshState.timer=null;}return;}
  startRefresh();if(refreshState && !refreshState.timer)pollPreview(refreshState);
});
app.ontoolresult=(result)=>{
  try {receiveMediaResult(result);} catch(e){stopRefresh();$("notice").textContent=e.message;}
};
app.onhostcontextchanged=(context)=>{
  if(context.theme)applyDocumentTheme(context.theme);syncDisplayMode(context);
  if((media?.embed_url && hostAllowsFrame(media.embed_url,context)===false)
    || currentReferenceFrames().some(frame=>hostAllowsFrame(frame.src,context)===false))blockedReference($('media').firstElementChild);
};
app.onteardown=async()=>{
  tornDown=true;stopRefresh();
  clearReferencePoster();
  const element=$('media').firstElementChild;
  if(element){element.onpause=null;element.onended=null;}
  return {};
};


// Choices are explicit user actions. No polling or automatic chat messages.
let choiceData, choiceProject, choosing=false;
function readData(result){
  if(result.isError) throw Error(result.content?.find(c=>c.type==='text')?.text || 'Could not save this choice.');
  return result.structuredContent || JSON.parse(result.content.find(c=>c.type==='text').text);
}
function renderChoices(data){
  stopRefresh();
  choiceData=data.choices;choiceProject=data.project_id;
  $('visual').hidden=true;$('choices').hidden=false;
  $('question').textContent=choiceData.question;
  $('options').replaceChildren();
  for(const option of choiceData.options){
    const item=document.createElement('div');item.className='option';
    const clip=document.createElement('video');clip.src=option.url;clip.poster=option.poster_url || '';clip.controls=true;clip.muted=true;clip.loop=true;clip.playsInline=true;clip.preload='metadata';
    const button=document.createElement('button');button.textContent=option.label;button.setAttribute('aria-pressed',String(option.id===choiceData.selected));button.onclick=()=>choose(option);
    const desc=document.createElement('p');desc.textContent=option.description;
    item.append(clip,button,desc);$('options').append(item);
  }
}
async function choose(option){
  if(choosing)return;choosing=true;
  const activeChoice=choiceData,projectId=choiceProject;
  const notice=text=>{if(activeChoice===choiceData)$('notice').textContent=text;};
  const buttons=[...$('options').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  try{
    const caps=app.getHostCapabilities?.() || {};
    if(!caps.serverTools)throw Error('Tell Claude which style you prefer; this host does not support saving choices here.');
    const result=readData(await app.callServerTool({name:'choose_video_style',arguments:{project_id:projectId,choice:option.id,revision:activeChoice.revision}}));
    activeChoice.revision=result.creative.choice_revision;activeChoice.selected=option.id;
    buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.textContent===option.label)));
    const context=[{type:'text',text:`Saved style for video project ${projectId}: ${JSON.stringify({choice:option.id,label:option.label,creative_revision:result.creative.revision})}. Use this direction in the next affected edit.`}];
    if(caps.updateModelContext?.text){try{await app.updateModelContext({content:context});}catch{/* Server state remains authoritative. */}}
    const prepared=await prepareUserReply(`I'd like the ${option.label} style.`);
    notice(`Choice saved. ${replyHint(prepared)}`);
  }catch(e){notice(e.message);}
  finally{choosing=false;buttons.forEach(b=>b.disabled=false);}
}
const receiveMedia=app.ontoolresult;
app.ontoolresult=result=>{
  if(result.structuredContent?.widget){try{receiveWidget(readData(result));}catch(e){$('notice').textContent=e.message;}return;}
  $('widget').hidden=true;
  if(result.structuredContent?.source_picker){renderSourcePicker(result);return;}
  $("sources").hidden=true;
  if(result.structuredContent?.choices){try{renderChoices(result.structuredContent)}catch(e){$('notice').textContent=e.message;}}
  else{$('choices').hidden=true;receiveMedia(result);}
};



let sourceState,sourceMeta,uploading=false;
function renderSourcePicker(result){
  stopRefresh();
  sourceState=result.structuredContent;sourceMeta=result._meta || {};
  $('choices').hidden=true;$('visual').hidden=true;$('sources').hidden=false;
  $('source-files').accept=sourceState.source_picker.accept;
  const extension=typeof window!=='undefined' ? window.openai : null;
  $('source-library').hidden=!(extension?.selectFiles && extension?.getFileDownloadUrl && app.getHostCapabilities?.()?.serverTools);
  $('source-status').textContent='Select media, documents or data · up to 200 MB total';
}
async function notifySources(names,projectId){
  const context=[{type:'text',text:`Sources added to video project ${projectId}: ${names.join(', ')}. Inspect the saved sources and continue with the current request.`}];
  const caps=app.getHostCapabilities?.() || {};
  if(caps.updateModelContext?.text){try{await app.updateModelContext({content:context})}catch{}}
  const summary=names.length<=3?names.join(', '):`${names.length} files`;
  return prepareUserReply(`I've added ${summary}. Please use ${names.length===1?'it':'them'} for this video.`);
}
async function finishSourceNotification(names,state){
  if(!names.length)return;
  const previousStatus=$('source-status').textContent;
  const prepared=await notifySources(names,state.project_id);
  // A late host response must not replace a newer picker or transfer's status.
  if(sourceState===state && $('source-status').textContent===previousStatus){
    $('source-status').textContent=previousStatus+' '+replyHint(prepared);
  }
}
$('source-files').onchange=async()=>{
  if(uploading || !sourceState)return;
  const state=sourceState,meta=sourceMeta;
  const status=text=>{if(sourceState===state)$('source-status').textContent=text;};
  const files=[...($('source-files').files || [])];if(!files.length)return;
  if(files.reduce((n,f)=>n+f.size,0)>state.source_picker.max_bytes){status('Please select less than 200 MB in total.');return;}
  if(!meta.source_upload_url || !meta.source_upload_token){status('Use the upload page below; this host did not provide upload access.');return;}
  uploading=true;$('source-files').disabled=true;
  const saved=[];
  try{
    for(const file of files){
      status(`Adding ${file.name}…`);
      const response=await fetch(meta.source_upload_url,{method:'POST',credentials:'omit',headers:{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(file.name),'X-Upload-Token':meta.source_upload_token},body:file});
      const data=await response.json();if(!response.ok)throw Error(data.detail || 'Upload failed. Use the upload page below.');
      saved.push(data.source.name || file.name);
    }
    status(`Added ${saved.join(', ')}.`);
  }catch(e){status((saved.length?`Added ${saved.join(', ')}. `:'')+e.message);}
  finally{uploading=false;$('source-files').disabled=false;$('source-files').value='';await finishSourceNotification(saved,state);}
};
$('source-library').onclick=async()=>{
  if(uploading || !sourceState)return;
  const state=sourceState;
  const status=text=>{if(sourceState===state)$('source-status').textContent=text;};
  const extension=typeof window!=='undefined' ? window.openai : null;
  if(!extension?.selectFiles || !extension?.getFileDownloadUrl)return;
  uploading=true;$('source-library').disabled=true;const saved=[];
  try{
    const selected=await extension.selectFiles();
    for(const file of selected){
      status(`Adding ${file.fileName}…`);
      const {downloadUrl}=await extension.getFileDownloadUrl({fileId:file.fileId});
      const result=readData(await app.callServerTool({name:'import_video_source',arguments:{project_id:state.project_id,url:downloadUrl,name:file.fileName}}));
      saved.push(result.source.name || file.fileName);
    }
    status(saved.length?`Added ${saved.join(', ')}.`:'No files selected.');
  }catch(e){status((saved.length?`Added ${saved.join(', ')}. `:'')+e.message);}
  finally{uploading=false;$('source-library').disabled=false;await finishSourceNotification(saved,state);}
};
$('source-fallback').onclick=async()=>{if(sourceState)await app.openLink({url:sourceState.source_picker.studio_url});};

// Optional edits stay local until the person explicitly sends them.
let widgetState=null;
const clone=value=>JSON.parse(JSON.stringify(value));
function widgetHere(state){return widgetState===state && !$('widget').hidden;}
function widgetPayload(state){return state.widget.kind==='brief'?{answers:state.draft.answers}:{beats:state.draft.beats};}
function widgetBaseline(widget){return widget.kind==='brief'?{answers:widget.answers || {}}:{beats:widget.beats};}
function widgetReply(widget,payload){
  if(widget.kind==='story')return "I've updated the story. Please use my saved changes.";
  const answers=(widget.questions || []).filter(q=>payload.answers?.[q.id]).map(q=>({
    id:q.id,prompt:q.prompt,label:q.options.find(o=>o.id===payload.answers[q.id])?.label,
  })).filter(answer=>answer.label);
  if(!answers.length)return 'I cleared those saved preferences. Please leave them undecided for now.';
  if(widget.purpose==='mode')return `${answers[0].label}, please.`;
  if(widget.purpose==='excerpt_review')return payload.answers.excerpt_review==='continue'
    ? 'Continue with this direction.' : "I'd like to refine this sample.";
  return (answers.length===1?answers[0].label:answers.map(a=>`${a.prompt} ${a.label}`).join(' ')).replace(/[.!?]$/,'')+'.';
}
function widgetIncomplete(state){return (state.widget.required || []).some(id=>!state.draft.answers?.[id]);}
function widgetControls(state){
  if(!widgetHere(state))return;
  $('widget-submit').disabled=state.saving || !state.dirty || Boolean(state.pending) || widgetIncomplete(state);
  $('widget-latest').hidden=!state.pending;
  $('widget-latest').disabled=state.saving;
  $('widget-fields').querySelectorAll('input,textarea,button').forEach(el=>{el.disabled=state.saving;});
}
function widgetEdited(state){
  state.dirty=JSON.stringify(widgetPayload(state))!==JSON.stringify(widgetBaseline(state.widget));
  if(widgetHere(state) && !state.pending)$('widget-status').textContent='';
  widgetControls(state);
}
function receiveWidget(data,replace=false){
  const widget=data.widget;
  if(!data.project_id || !widget?.id || !['brief','story'].includes(widget.kind))throw Error('This editor could not be loaded.');
  stopRefresh();$('visual').hidden=true;$('choices').hidden=true;$('sources').hidden=true;$('widget').hidden=false;$('notice').textContent='';
  const same=widgetState?.projectId===data.project_id && widgetState.widget.id===widget.id;
  if(same && !replace){
    if(widget.revision<=widgetState.widget.revision)return;
    if(widgetState.dirty || widgetState.saving){
      if(!widgetState.pending || widget.revision>widgetState.pending.widget.revision)widgetState.pending=data;
      $('widget-status').textContent='A newer version is available. Your unsent edits are still here.';
      widgetControls(widgetState);return;
    }
  }
  const state={projectId:data.project_id,widget:clone(widget),draft:clone(widgetBaseline(widget)),dirty:false,saving:false,pending:null,submission:null};
  widgetState=state;drawWidget(state);
}
function drawWidget(state){
  const widget=state.widget,fields=$('widget-fields');fields.replaceChildren();fields.className='';fields.removeAttribute('aria-label');
  $('widget-title').textContent=widget.title || (widget.kind==='brief'?'A few preferences':'Shape the story');
  $('widget-submit').textContent=widget.purpose==='excerpt_review'?'Send decision':widget.required?.length?'Continue':widget.kind==='brief'?'Save preferences':'Send changes';
  $('widget-status').textContent='';
  if(widget.kind==='brief'){
    for(const question of widget.questions || []){
      const group=document.createElement('fieldset');group.className='brief-question';
      const legend=document.createElement('legend');legend.textContent=question.prompt;group.append(legend);
      const options=document.createElement('div');options.className='brief-options';group.append(options);
      for(const option of question.options || []){
        const button=document.createElement('button');button.type='button';button.textContent=option.label;
        button.dataset.option=option.id;button.dataset.question=question.id;
        button.setAttribute('aria-pressed',String(state.draft.answers[question.id]===option.id));
        if(question.recommended===option.id){const hint=document.createElement('small');hint.textContent='Suggested';button.append(hint);}
        button.onclick=()=>{
          if(state.saving)return;
          if(state.draft.answers[question.id]===option.id)delete state.draft.answers[question.id];
          else state.draft.answers[question.id]=option.id;
          for(const el of options.children)el.setAttribute('aria-pressed',String(el.dataset.option===state.draft.answers[question.id]));
          widgetEdited(state);
        };
        options.append(button);
      }
      fields.append(group);
    }
  }else{
    fields.className='story-strip';fields.setAttribute('aria-label','Story beats');
    state.draft.beats.forEach((beat,index)=>{
      const card=document.createElement('article');card.className='story-beat';card.setAttribute('aria-label',`Beat ${index+1}`);
      const heading=document.createElement('div');heading.className='beat-heading';
      const number=document.createElement('span');number.textContent=`${index+1}`;heading.append(number);
      const duration=document.createElement('label');duration.className='beat-duration';duration.textContent='Seconds';
      const seconds=document.createElement('input');seconds.type='number';seconds.min='0.1';seconds.max='600';seconds.step='0.1';seconds.required=true;seconds.value=String(beat.seconds);
      seconds.setAttribute('aria-label',`Beat ${index+1} seconds`);seconds.dataset.field='seconds';seconds.dataset.beat=beat.id;
      seconds.oninput=()=>{beat.seconds=Number(seconds.value);widgetEdited(state);};duration.append(seconds);heading.append(duration);card.append(heading);
      for(const [key,label,maxLength,rows] of [['title','Title',100,0],['visual','Visual',400,3],['narration','Narration',2000,4]]){
        const wrapper=document.createElement('label');wrapper.textContent=label;
        const input=document.createElement(rows?'textarea':'input');input.value=beat[key] || '';input.maxLength=maxLength;
        if(rows)input.rows=rows;
        input.required=key!=='narration';
        input.setAttribute('aria-label',`Beat ${index+1} ${label.toLowerCase()}`);input.dataset.field=key;input.dataset.beat=beat.id;
        input.oninput=()=>{beat[key]=input.value;widgetEdited(state);};wrapper.append(input);card.append(wrapper);
      }
      fields.append(card);
    });
  }
  widgetControls(state);
}
$('widget-latest').onclick=()=>{const state=widgetState;if(state?.pending && !state.saving)receiveWidget(state.pending,true);};
$('widget-form').onsubmit=async event=>{
  event?.preventDefault?.();
  const state=widgetState;if(!state || state.saving || !state.dirty || state.pending || widgetIncomplete(state))return;
  const payload=clone(widgetPayload(state)),caps=app.getHostCapabilities?.() || {};
  const notice=text=>{if(widgetHere(state))$('widget-status').textContent=text;};
  if(state.widget.kind==='story' && payload.beats.some(b=>!b.title.trim() || !b.visual.trim() || !Number.isFinite(b.seconds) || b.seconds<0.1 || b.seconds>600)){
    notice('Give each beat a title, a visual, and a duration between 0.1 and 600 seconds.');return;
  }
  if(!caps.serverTools){notice('This host cannot save here. Copy your preferences or story changes into the chat.');return;}
  const signature=JSON.stringify({revision:state.widget.revision,...payload});
  if(state.submission?.signature!==signature)state.submission={signature,id:newFeedbackId()};
  state.saving=true;widgetControls(state);notice('Saving…');
  try{
    const data=readData(await app.callServerTool({name:'save_video_widget',arguments:{project_id:state.projectId,widget_id:state.widget.id,revision:state.widget.revision,request_id:state.submission.id,...payload}}));
    if(data.project_id!==state.projectId || data.widget?.id!==state.widget.id || data.widget.kind!==state.widget.kind || !(data.widget.revision>state.widget.revision || (data.saved===false && data.widget.revision===state.widget.revision)))throw Error('The save could not be confirmed. Your edits are still here; try again.');
    const saved=data.widget,submittedRevision=state.widget.revision;
    const newerChanges=data.repeated===true && (saved.revision>submittedRevision+1 || data.creative?.revision>saved.creative_revision);
    const reply=widgetReply(state.widget,payload);
    const current={project_id:state.projectId,widget_id:saved.id,widget_revision:saved.revision,creative_revision:data.creative?.revision ?? saved.creative_revision};
    for(const key of ['brief_answers','beats','direction','preferences','selected','latest_feedback','plan_provenance','intake']){
      if(data.creative?.[key]!==undefined)current[key]=data.creative[key];
    }
    if(data.intake!==undefined)current.intake=data.intake;
    if(saved.kind==='brief' && current.brief_answers===undefined)current.brief_answers=(saved.questions || []).filter(q=>saved.answers?.[q.id]).map(q=>({question:q.prompt,answer:q.options.find(o=>o.id===saved.answers[q.id])?.label || saved.answers[q.id]}));
    if(saved.kind==='story' && current.beats===undefined)current.beats=saved.beats;
    const context=[{type:'text',text:`Authoritative saved video context: ${JSON.stringify(current)}. ${newerChanges?'An earlier request was already applied and later changes now exist. Do not replay the earlier submitted values. ':''}Use this current state for the next appropriate edit. These preferences are not final approval.`}];
    state.widget=clone(saved);state.draft=clone(widgetBaseline(saved));state.dirty=false;
    if(state.pending?.widget.revision<=saved.revision)state.pending=null;
    if(widgetHere(state))drawWidget(state);
    if(data.saved===false){notice('No new changes to save.');return;}
    if(caps.updateModelContext?.text){try{await app.updateModelContext({content:context});}catch{}}
    // A retry is not a new instruction to restore its old choices. Keep the
    // authoritative state in model context without waking it with stale edits.
    if(newerChanges){notice('Earlier save confirmed. Newer changes are shown.');return;}
    const prepared=await prepareUserReply(reply);
    notice(state.pending?'Saved. A newer version is available.':`Changes saved. ${replyHint(prepared)}`);
  }catch(e){notice(e.message || 'Could not save your changes. Try again.');}
  finally{state.saving=false;widgetControls(state);}
};

function syncDisplayMode(context){
  const host=context || app.getHostContext?.() || {};
  document.documentElement.classList.toggle('fullscreen',host.displayMode==='fullscreen');
}
app.connect().then(()=>syncDisplayMode()).catch(()=>{$('notice').textContent='Ask your assistant to show this again.';});
