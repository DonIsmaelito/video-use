import {App,applyDocumentTheme,applyHostStyleVariables} from '@modelcontextprotocol/ext-apps';
const app = new App({name:'video-use project',version:'1.0.0'});
const $=id=>document.getElementById(id);
let projectId, snapshot, selected, shown, timer, stopped=false, busy=false, followLatest=true;
const opened=Date.now();
function unpack(result){
 if(result.isError) throw Error('The project could not be refreshed. Check your connection.');
 if(result.structuredContent) return result.structuredContent;
 for(const c of result.content||[]) if(c.type==='text'){try{return JSON.parse(c.text)}catch{}}
 return {};
}
function previews(data){
 const values=(data.updates||[]).filter(u=>u.preview).map(u=>({id:u.id,stage:u.stage,note:u.note,at:u.at,...u.preview}));
 for(const r of [...(data.revisions||[])].reverse()) values.push({id:r.id,stage:'Final export',note:r.summary,at:r.created,url:r.video_url,media_type:'video/mp4'});
 return values;
}
function render(data){
 if(!data.id) return;
 projectId=data.id;snapshot=data;$('title').textContent=data.title||'Video project';
 const tasks=data.tasks||[];const active=tasks.find(t=>['queued','running'].includes(t.status));
 const last=(data.updates||[]).at(-1);
 $('status').textContent=active?'Rendering':tasks[0]?.status==='failed'?'Needs attention':data.revisions?.length?'Export ready':data.stage||'Ready';
 $('summary').textContent=active?'Creating the next update. You can keep chatting.':tasks[0]?.status==='failed'?'The last step stopped. Your saved previews are still available.':last?.note||'Frames and draft clips will appear here as they are published.';
 $('next').textContent=data.next_action||data.continuation?.next_action||'No next step saved yet.';
 const list=previews(data);
 if(followLatest||!list.some(p=>p.id===selected))selected=list.at(-1)?.id;
 $('history').replaceChildren();
 for(const item of list){
  const b=document.createElement('button'); b.className=item.id===selected?'selected':''; b.setAttribute('aria-pressed',String(item.id===selected));
  b.textContent=item.stage;const when=document.createElement('small');when.textContent=new Date(item.at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});b.append(when);
  b.onclick=()=>{selected=item.id;followLatest=item.id===list.at(-1)?.id;render(snapshot)};$('history').append(b);
 }
 const item=list.find(p=>p.id===selected);
 $('empty').hidden=!!item;$('media').style.display=item?'block':'none';$('download').hidden=!item;
 if(item){
  $('caption').textContent=item.note||item.stage;
  if(shown!==item.id){
   const el=document.createElement(item.media_type==='video/mp4'?'video':'img');el.src=item.url;
   if(el.tagName==='VIDEO'){el.controls=true;el.playsInline=true;el.preload='metadata'}else{el.alt=item.note||'Project preview'}
   el.onerror=()=>{$('notice').textContent='Preview unavailable or expired. Press Refresh to renew it.'};
   $('media').replaceChildren(el);shown=item.id;
  }
 }
}
function schedule(){clearTimeout(timer);if(!stopped&&Date.now()-opened<30*60*1000)timer=setTimeout(refresh,8000)}
async function refresh(){
 if(busy||!projectId||stopped)return;
 if(document.hidden){schedule();return}
 busy=true;$('refresh').disabled=true;
 try{render(unpack(await app.callServerTool({name:'video_project_updates',arguments:{project_id:projectId}})));$('notice').textContent=''}
 catch(e){$('notice').textContent='Unable to refresh. Reconnect video-use if this persists.'}
 finally{busy=false;$('refresh').disabled=false;schedule()}
}
$('refresh').onclick=()=>{shown=undefined;refresh()};
$('studio').onclick=async()=>{if(snapshot?.workspace_url)await app.openLink({url:snapshot.workspace_url})};
$('download').onclick=async()=>{const item=previews(snapshot).find(x=>x.id===selected);if(item)await app.openLink({url:item.url})};
app.ontoolresult=r=>{try{render(unpack(r));refresh()}catch(e){$('notice').textContent=e.message}};
app.onhostcontextchanged=c=>{if(c.theme)applyDocumentTheme(c.theme);if(c.styles?.variables)applyHostStyleVariables(c.styles.variables)};
app.onteardown=async()=>{stopped=true;clearTimeout(timer);return {}};
app.connect().then(()=>{const ctx=app.getHostContext();if(ctx)app.onhostcontextchanged(ctx)}).catch(()=>{$('status').textContent='Connection needed';$('notice').textContent='Open this card through the video-use connector.'});
