import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,'');
const template=fs.readFileSync('template.html','utf8');
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function deferred(){let resolve;const promise=new Promise(done=>{resolve=done});return {promise,resolve};}
function result(id='draft',project='project',extra={}){
  return {structuredContent:{project_id:project,media:{object_id:id,media_type:'video/mp4',url:`https://media.test/${id}.mp4`,download_url:`https://media.test/${id}.mp4?download=true`,final:false,...extra}}};
}
function host({serverTool,capabilities={serverTools:{}}}={}){
  const {document,window}=parseHTML(template);
  const timers=new Map(),calls=[],messages=[];
  let app,now=0,serial=0;
  class Clock extends Date{static now(){return now;}}
  class App{
    constructor(){app=this;}
    async connect(){}
    getHostCapabilities(){return capabilities;}
    async callServerTool(input){calls.push(input);return serverTool?serverTool(input):result();}
    async openLink(input){calls.push({open:input});}
    async sendMessage(input){messages.push(input);return {};}
    async updateModelContext(input){messages.push(input);}
  }
  vm.runInNewContext(source,{
    document,App,applyDocumentTheme(){},console,Date:Clock,
    setTimeout(fn,delay){const id=++serial;timers.set(id,{fn,at:now+delay});return id;},
    clearTimeout(id){timers.delete(id);},
  });
  async function advance(ms){
    const end=now+ms;
    while(true){
      const next=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at || a[0]-b[0])[0];
      if(!next)break;
      now=next[1].at;timers.delete(next[0]);next[1].fn();await flush();
    }
    now=end;await flush();
  }
  async function visible(value){document.hidden=!value;document.dispatchEvent(new window.Event('visibilitychange'));await flush();}
  return {document,app,calls,messages,timers,advance,visible};
}

{
  const h=host({serverTool:async()=>result('new-draft')});
  assert.equal(h.document.getElementById('visual').hidden,true);
  await h.advance(10000);assert.equal(h.calls.length,0,'no polling without actual media');
  h.app.ontoolresult(result());
  await h.advance(4999);assert.equal(h.calls.length,0);
  await h.advance(1);assert.equal(h.calls.length,1);
  assert.equal(h.calls[0].name,'video_preview_updates');
  assert.equal(h.calls[0].arguments.project_id,'project');
  assert(h.document.querySelector('video').src.includes('new-draft.mp4'));
  assert.equal(h.messages.length,0,'refresh never submits host messages or model context');
  const same=h.document.querySelector('video');
  await h.advance(5000);assert.equal(h.document.querySelector('video'),same,'unchanged media preserves playback element');
  await h.app.onteardown();assert.equal(h.timers.size,0);
  await h.advance(20000);assert.equal(h.calls.length,2,'teardown cancels refresh');
}

for(const event of ['onpause','onended']){
  let sequence=0;
  const h=host({serverTool:async()=>++sequence===1?result('new-draft'):result('final','project',{final:true})});
  h.app.ontoolresult(result());
  const playing=h.document.querySelector('video');playing.paused=false;playing.ended=false;
  await h.advance(5000);
  assert.equal(h.document.querySelector('video'),playing,'draft refresh must not interrupt playback');
  await h.advance(5000);
  assert.equal(h.document.querySelector('video'),playing,'final refresh must wait for playback');
  assert.equal(h.timers.size,0,'final media stops polling even while queued');
  if(event==='onended')playing.ended=true;else playing.paused=true;
  playing[event]();
  assert(h.document.querySelector('video').src.includes('final.mp4'),'only latest queued media is displayed');
  await h.document.getElementById('download').onclick();
  assert(h.calls.at(-1).open.url.includes('final.mp4'));
  assert.equal(h.messages.length,0);
}

for(const mode of ['final','unsupported','choices','sources','empty','reference']){
  const h=host({capabilities:mode==='unsupported'?{}:{serverTools:{}}});
  if(mode==='final')h.app.ontoolresult(result('final','project',{final:true}));
  else if(mode==='choices')h.app.ontoolresult({structuredContent:{project_id:'project',choices:{question:'Style?',revision:1,options:[]}}});
  else if(mode==='sources')h.app.ontoolresult({structuredContent:{project_id:'project',source_picker:{accept:'.mp4'}}});
  else if(mode==='empty')h.app.ontoolresult({structuredContent:{project_id:'project'}});
  else if(mode==='reference'){const r=result();r.structuredContent.follow_project=false;h.app.ontoolresult(r);}
  else h.app.ontoolresult(result());
  assert.equal(h.timers.size,0,`${mode} must not poll`);
  await h.advance(600000);assert.equal(h.calls.length,0);
}

{
  const pending=deferred(),h=host({serverTool:()=>pending.promise});
  h.app.ontoolresult(result());
  await h.advance(5000);await h.advance(20000);
  assert.equal(h.calls.length,1,'slow requests never overlap');
  await h.app.onteardown();
  pending.resolve(result('late'));await flush();
  assert(h.document.querySelector('video').src.includes('draft.mp4'),'late response after teardown is ignored');
  assert.equal(h.timers.size,0);
}

{
  let final=false;
  const h=host({serverTool:async()=>final?result('final','project',{final:true}):result()});
  h.app.ontoolresult(result());await h.advance(41*60000);
  assert(h.timers.size>0,'long decisions do not permanently expire the player');
  assert(h.calls.length<=93,'older players poll only twice per minute');
  final=true;await h.advance(30000);
  assert(h.document.querySelector('video').src.includes('final.mp4'));
  assert.equal(h.timers.size,0,'the initial sample becomes final and stops polling');
  assert.equal(h.messages.length,0);
}
{
  const h=host();h.app.ontoolresult(result());await h.advance(5000);
  await h.visible(false);assert.equal(h.timers.size,0);
  await h.advance(60*60000);assert.equal(h.calls.length,1,'hidden hosts do no background work');
  await h.visible(true);assert.equal(h.calls.length,2,'returning immediately checks for final');assert(h.timers.size>0);
  await h.app.onteardown();await h.visible(false);await h.visible(true);assert.equal(h.calls.length,2,'teardown is permanent until a new result');
}

{
  const pending=deferred();let count=0;
  const h=host({serverTool:async input=>++count===1?pending.promise:result('newer',input.arguments.project_id)});
  h.app.ontoolresult(result('old','old-project'));await h.advance(5000);
  h.app.ontoolresult(result('new','new-project'));await h.advance(5000);
  assert.equal(h.calls.length,1,'changing projects never overlaps a pending host request');
  pending.resolve(result('old-late','old-project'));await flush();
  assert(h.document.querySelector('video').src.includes('/new.mp4'));
  await h.advance(5000);
  assert.equal(h.calls.length,2);assert.equal(h.calls[1].arguments.project_id,'new-project');
  assert(h.document.querySelector('video').src.includes('/newer.mp4'));
}

{
  const h=host({serverTool:async()=>{throw Error('disconnected');}});
  h.app.ontoolresult(result());await h.advance(15000);
  assert.equal(h.calls.length,3);assert.equal(h.timers.size,0,'three failures stop silent refresh retries');
  assert.equal(h.document.getElementById('visual').hidden,false,'existing playable media stays visible');
}

{
  const h=host();h.app.ontoolresult(result('excerpt','project',{truncated:true,duration:120,source_duration:245}));
  assert.equal(h.document.getElementById('excerpt').hidden,false);
  assert.equal(h.document.getElementById('excerpt').textContent,'Preview excerpt · 120s of 245s');
  h.app.ontoolresult(result('final','project',{final:true}));
  assert.equal(h.document.getElementById('excerpt').hidden,true);
  assert.equal(h.timers.size,0);
}

console.log('PASS adaptive visible-player refresh survives long decisions and updates the original sample to final without interrupting playback');
