import { App, applyDocumentTheme } from "@modelcontextprotocol/ext-apps";
const app = new App({ name: "Video preview", version: "3.0.0" });
const $ = (id) => document.getElementById(id);
let media, shown, mediaProject, pendingMedia, refreshState, refreshInFlight=false;
let feedbackDraft=null,feedbackSaving=false;
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
  if(element!==$('media').firstElementChild || playing() || feedbackDraft || !pendingMedia)return;
  const next=pendingMedia;pendingMedia=null;render(next);
}
function present(next){
  if(!next)return;
  const key=next.object_id || next.url;
  if(shown!==key && (playing() || feedbackDraft))pendingMedia=next;
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
  if(projectId!==mediaProject){stopRefresh();resetFeedback();mediaProject=projectId;render(next);}
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
  const canEdit=next.media_type==='video/mp4' && Boolean(mediaProject && next.object_id);
  $('suggest-edit').hidden=!canEdit;$('feedback-shortcuts').hidden=!canEdit;
  $('excerpt').hidden=next.truncated!==true;
  if(next.truncated===true){
    const seconds=Number(next.duration),total=Number(next.source_duration);
    $('excerpt').textContent=Number.isFinite(seconds) && Number.isFinite(total)
      ? `Preview excerpt · ${Math.round(seconds)}s of ${Math.round(total)}s`
      : 'Preview excerpt · the full video is longer';
  }
  $("notice").textContent="";
  syncDisplayMode();
}
function feedbackTime(seconds){
  const tenths=Math.round(seconds*10),minutes=Math.floor(tenths/600),remainder=((tenths%600)/10).toFixed(1).padStart(4,'0');
  return `${minutes}:${remainder}`;
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
function resetFeedback(){
  feedbackDraft=null;$('feedback-form').hidden=true;$('feedback-note').value='';
}
function finishFeedback(draft){
  if(feedbackDraft!==draft)return;
  resetFeedback();
  if(pendingMedia && !playing()){const next=pendingMedia;pendingMedia=null;render(next);}
}
function openFeedback(prefill=''){
  if(feedbackSaving || !mediaProject || !media?.object_id)return;
  const element=$('media').firstElementChild;
  if(element?.tagName!=='VIDEO')return;
  if(!feedbackDraft){
    const seconds=Number.isFinite(element.currentTime)?Math.max(0,element.currentTime):0;
    feedbackDraft={projectId:mediaProject,objectId:media.object_id,seconds:Math.round(seconds*1000)/1000,requestId:newFeedbackId()};
    $('feedback-note').value='';
  }
  // Capture/pin this exact version before pausing; a new draft may arrive meanwhile.
  element.pause?.();
  $('feedback-time').textContent=`At ${feedbackTime(feedbackDraft.seconds)}`;
  const note=$('feedback-note');
  if(prefill && !note.value.includes(prefill))note.value=(note.value.trim()?note.value.trim()+'\n':'')+prefill;
  $('feedback-form').hidden=false;note.focus?.();
  $('notice').textContent='';
}
$('suggest-edit').onclick=()=>openFeedback();
for(const [id,note] of [
  ['edit-labels','Make the labels larger and easier to read at this moment.'],
  ['edit-pace','Make the pacing faster around this moment, while keeping the explanation clear.'],
  ['edit-look','Explore a different visual style for this moment.'],
])$(id).onclick=()=>openFeedback(note);
$('feedback-cancel').onclick=()=>{if(!feedbackSaving)finishFeedback(feedbackDraft);};
$('feedback-form').onsubmit=async(event)=>{
  event?.preventDefault?.();
  if(feedbackSaving || !feedbackDraft)return;
  const draft=feedbackDraft,note=$('feedback-note').value.trim();
  if(!note || note.length>1200){$('notice').textContent='Write a short suggestion first.';return;}
  const label=feedbackTime(draft.seconds);
  const notice=text=>{if(feedbackDraft===draft)$('notice').textContent=text;};
  const caps=app.getHostCapabilities?.() || {};
  if(!caps.serverTools){notice(`Copy into chat: At ${label}, ${note}`);return;}
  if(draft.submittedNote && draft.submittedNote!==note)draft.requestId=newFeedbackId();
  draft.submittedNote=note;feedbackSaving=true;
  $('feedback-note').disabled=true;$('feedback-send').disabled=true;$('feedback-cancel').disabled=true;
  $('suggest-edit').disabled=true;$('feedback-shortcuts').querySelectorAll('button').forEach(button=>{button.disabled=true;});
  try{
    const result=readData(await app.callServerTool({name:'add_video_feedback',arguments:{project_id:draft.projectId,object_id:draft.objectId,seconds:draft.seconds,note,request_id:draft.requestId}}));
    const context=[{type:'text',text:`Saved feedback for video project ${draft.projectId}: ${JSON.stringify({object_id:draft.objectId,seconds:draft.seconds,note,creative_revision:result.creative.revision})}. Apply this to the referenced version, not an assumed moment in a newer video.`}];
    if(caps.updateModelContext?.text){try{await app.updateModelContext({content:context});}catch{}}
    const prepared=await prepareUserReply(`At ${label}, ${note}`);
    const stillHere=feedbackDraft===draft;finishFeedback(draft);
    if(stillHere)$('notice').textContent=`Suggestion saved. ${replyHint(prepared)}`;
  }catch(e){notice(e.message || 'Could not save this suggestion. Try again.');}
  finally{
    feedbackSaving=false;$('feedback-note').disabled=false;$('feedback-send').disabled=false;$('feedback-cancel').disabled=false;
    $('suggest-edit').disabled=false;$('feedback-shortcuts').querySelectorAll('button').forEach(button=>{button.disabled=false;});
  }
};
$("download").onclick=async()=>{
  if (media) await app.openLink({url:media.download_url || media.url + "&download=true"});
};
app.ontoolresult=(result)=>{
  try {receiveMediaResult(result);} catch(e){stopRefresh();$("notice").textContent=e.message;}
};
app.onhostcontextchanged=(context)=>{if(context.theme)applyDocumentTheme(context.theme);syncDisplayMode(context);};
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
  stopRefresh();resetFeedback();
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
  stopRefresh();resetFeedback();
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
  stopRefresh();resetFeedback();$('visual').hidden=true;$('choices').hidden=true;$('sources').hidden=true;$('widget').hidden=false;$('notice').textContent='';
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

let displayContext={},displayRequest=false;
function syncDisplayMode(context){
  displayContext={...(app.getHostContext?.() || {}),...displayContext,...(context || {})};
  const fullscreen=displayContext.displayMode==='fullscreen';
  const target=fullscreen?'inline':'fullscreen';
  $('expand').hidden=typeof app.requestDisplayMode!=='function' || !displayContext.availableDisplayModes?.includes(target);
  $('expand').textContent=fullscreen?'Exit fullscreen':'Expand';
  $('expand').setAttribute('aria-label',fullscreen?'Exit fullscreen preview':'Expand preview to fullscreen');
  document.documentElement.classList.toggle('fullscreen',fullscreen);
}
$('expand').onclick=async()=>{
  if(displayRequest)return;
  syncDisplayMode();const mode=displayContext.displayMode==='fullscreen'?'inline':'fullscreen';
  if(!displayContext.availableDisplayModes?.includes(mode) || typeof app.requestDisplayMode!=='function')return;
  displayRequest=true;$('expand').disabled=true;
  try{
    const result=await app.requestDisplayMode({mode});
    if(result?.isError || !['inline','fullscreen','pip'].includes(result?.mode))throw Error('The host could not expand this preview.');
    syncDisplayMode({displayMode:result.mode});
  }catch(e){$('notice').textContent=e.message || 'The host could not expand this preview.';}
  finally{displayRequest=false;$('expand').disabled=false;}
};
app.connect().then(()=>syncDisplayMode()).catch(()=>{$('notice').textContent='Ask your assistant to show this again.';});
