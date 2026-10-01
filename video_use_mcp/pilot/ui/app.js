import { App, applyDocumentTheme } from "@modelcontextprotocol/ext-apps";
const app = new App({ name: "Video preview", version: "3.0.0" });
const $ = (id) => document.getElementById(id);
let media, shown, mediaProject, pendingMedia, refreshState, refreshInFlight=false;
const REFRESH_INTERVAL_MS=5000,REFRESH_LIMIT_MS=10*60*1000;
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
  if(state){clearTimeout(state.timer);clearTimeout(state.expiry);}
  if(!keepPending)pendingMedia=null;
}
function settlePlayback(element){
  if(element!==$('media').firstElementChild || playing() || !pendingMedia)return;
  const next=pendingMedia;pendingMedia=null;render(next);
}
function present(next){
  if(!next)return;
  const key=next.object_id || next.url;
  if(shown!==key && playing())pendingMedia=next;
  else{pendingMedia=null;render(next);}
}
function scheduleRefresh(state){
  if(refreshState!==state || state.timer)return;
  if(Date.now()+REFRESH_INTERVAL_MS>state.deadline){stopRefresh(true);return;}
  state.timer=setTimeout(()=>pollPreview(state),REFRESH_INTERVAL_MS);
}
async function pollPreview(state){
  state.timer=null;
  if(refreshState!==state)return;
  if(Date.now()>=state.deadline || !app.getHostCapabilities?.()?.serverTools){stopRefresh(true);return;}
  // A previous project can still have an unabortable host request in flight.
  // Never overlap it, and never apply its result to a new project or view.
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
    if(refreshState===state && ++state.failures>=3){stopRefresh(true);return;}
  }finally{refreshInFlight=false;}
  scheduleRefresh(state);
}
function receiveMediaResult(result){
  const next=unpack(result);
  if(!next){stopRefresh();return;}
  const data=result.structuredContent;
  const projectId=data?.project_id || data?.project_card?.id || data?.id;
  if(projectId!==mediaProject){stopRefresh();mediaProject=projectId;render(next);}
  else present(next);
  if(next.final===true){stopRefresh(true);return;}
  if(!projectId || !app.getHostCapabilities?.()?.serverTools)return;
  if(refreshState?.projectId===projectId)return;
  stopRefresh(true);
  const state={projectId,deadline:Date.now()+REFRESH_LIMIT_MS,failures:0,timer:null,expiry:null};
  refreshState=state;
  state.expiry=setTimeout(()=>{if(refreshState===state)stopRefresh(true);},REFRESH_LIMIT_MS);
  scheduleRefresh(state);
}
function render(next) {
  if (!next) return;
  media = next;
  const key = next.object_id || next.url;
  if (shown !== key) {
    const video = next.media_type === "video/mp4";
    const element = document.createElement(video ? "video" : "img");
    element.src = next.url;
    if (video) {
      element.controls=true; element.playsInline=true; element.preload="metadata";
      element.onpause=()=>settlePlayback(element);element.onended=()=>settlePlayback(element);
    }
    else element.alt = next.caption || "Proposed video frame";
    element.onerror = () => {$("notice").textContent="The preview link expired. Ask Claude to show it again.";};
    $("media").replaceChildren(element);
    shown=key;
  }
  $("visual").hidden=false;
  $("download").hidden=next.media_type !== "video/mp4";
  $('excerpt').hidden=next.truncated!==true;
  if(next.truncated===true){
    const seconds=Number(next.duration),total=Number(next.source_duration);
    $('excerpt').textContent=Number.isFinite(seconds) && Number.isFinite(total)
      ? `Preview excerpt · ${Math.round(seconds)}s of ${Math.round(total)}s`
      : 'Preview excerpt · the full video is longer';
  }
  $("notice").textContent="";
}
$("download").onclick=async()=>{
  if (media) await app.openLink({url:media.download_url || media.url + "&download=true"});
};
app.ontoolresult=(result)=>{
  try {receiveMediaResult(result);} catch(e){stopRefresh();$("notice").textContent=e.message;}
};
app.onhostcontextchanged=(context)=>{if(context.theme)applyDocumentTheme(context.theme);};
app.onteardown=async()=>{
  stopRefresh();
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
    notice('Saved. The next editing step will use your choice.');
    const content=[{type:'text',text:`For video project ${projectId}, I chose ${option.label}. Continue with that direction. Creative revision ${result.creative.revision}.`}];
    // Context delivery is host controlled; a click may also queue a user message.
    if(caps.updateModelContext?.text){try{await app.updateModelContext({content});}catch{/* Server state remains authoritative. */}}
    if(caps.message?.text){try{const sent=await app.sendMessage({role:'user',content});if(sent.isError)throw Error();}catch{notice('Choice saved. Tell Claude to continue if the conversation is paused.');}}
  }catch(e){notice(e.message);}
  finally{choosing=false;buttons.forEach(b=>b.disabled=false);}
}
const receiveMedia=app.ontoolresult;
app.ontoolresult=result=>{
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
  const content=[{type:'text',text:`I added ${names.join(', ')} to video project ${projectId}. Inspect the sources and continue.`}];
  const caps=app.getHostCapabilities?.() || {};
  if(caps.updateModelContext?.text){try{await app.updateModelContext({content})}catch{}}
  if(caps.message?.text){try{return !(await app.sendMessage({role:'user',content}))?.isError}catch{}}
  return false;
}
async function finishSourceNotification(names,state){
  if(!names.length)return;
  const previousStatus=$('source-status').textContent;
  const sent=await notifySources(names,state.project_id);
  // A late host response must not replace a newer picker or transfer's status.
  if(!sent && sourceState===state && $('source-status').textContent===previousStatus){
    $('source-status').textContent=previousStatus+' If the chat is waiting, tell your assistant to continue.';
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
app.connect().catch(()=>{$('notice').textContent='Ask your assistant to show this again.';});
