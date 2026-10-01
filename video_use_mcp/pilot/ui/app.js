import { App, applyDocumentTheme } from "@modelcontextprotocol/ext-apps";
const app = new App({ name: "Video preview", version: "2.0.0" });
const $ = (id) => document.getElementById(id);
let media, shown;
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
function render(next) {
  if (!next) return;
  media = next;
  const key = next.object_id || next.url;
  if (shown !== key) {
    const video = next.media_type === "video/mp4";
    const element = document.createElement(video ? "video" : "img");
    element.src = next.url;
    if (video) {element.controls=true; element.playsInline=true; element.preload="metadata";}
    else element.alt = next.caption || "Proposed video frame";
    element.onerror = () => {$("notice").textContent="The preview link expired. Ask Claude to show it again.";};
    $("media").replaceChildren(element);
    shown=key;
  }
  $("visual").hidden=false;
  $("download").hidden=next.media_type !== "video/mp4";
  $("notice").textContent="";
}
$("download").onclick=async()=>{
  if (media) await app.openLink({url:media.download_url || media.url + "&download=true"});
};
app.ontoolresult=(result)=>{
  try {render(unpack(result));} catch(e){$("notice").textContent=e.message;}
};
app.onhostcontextchanged=(context)=>{if(context.theme)applyDocumentTheme(context.theme);};
app.onteardown=async()=>({});


// Choices are explicit user actions. No polling or automatic chat messages.
let choiceData, choiceProject, choosing=false;
function readData(result){
  if(result.isError) throw Error(result.content?.find(c=>c.type==='text')?.text || 'Could not save this choice.');
  return result.structuredContent || JSON.parse(result.content.find(c=>c.type==='text').text);
}
function renderChoices(data){
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
  const buttons=[...$('options').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  try{
    const caps=app.getHostCapabilities?.() || {};
    if(!caps.serverTools)throw Error('Tell Claude which style you prefer; this host does not support saving choices here.');
    const result=readData(await app.callServerTool({name:'choose_video_style',arguments:{project_id:choiceProject,choice:option.id,revision:choiceData.revision}}));
    choiceData.revision=result.creative.choice_revision;choiceData.selected=option.id;
    buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.textContent===option.label)));
    $('notice').textContent='Saved. The next editing step will use your choice.';
    const content=[{type:'text',text:`For video project ${choiceProject}, I chose ${option.label}. Continue with that direction. Creative revision ${result.creative.revision}.`}];
    // Context delivery is host controlled; a click may also queue a user message.
    if(caps.updateModelContext?.text){try{await app.updateModelContext({content});}catch{/* Server state remains authoritative. */}}
    if(caps.message?.text){try{const sent=await app.sendMessage({role:'user',content});if(sent.isError)throw Error();}catch{$('notice').textContent='Choice saved. Tell Claude to continue if the conversation is paused.';}}
  }catch(e){$('notice').textContent=e.message;}
  finally{choosing=false;buttons.forEach(b=>b.disabled=false);}
}
const receiveMedia=app.ontoolresult;
app.ontoolresult=result=>{
  if(result.structuredContent?.choices){try{renderChoices(result.structuredContent)}catch(e){$('notice').textContent=e.message;}}
  else{$('choices').hidden=true;receiveMedia(result);}
};

app.connect().catch(()=>{$("notice").textContent="Ask Claude to show this preview again.";});
