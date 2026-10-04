import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,'');
const template=fs.readFileSync('template.html','utf8');
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function deferred(){let resolve;const promise=new Promise(done=>{resolve=done});return {promise,resolve};}
function result(id='draft',project='project',extra={}){
  return {structuredContent:{project_id:project,follow_project:false,media:{object_id:id,media_type:'video/mp4',url:`https://media.test/${id}.mp4`,download_url:`https://media.test/${id}.mp4?download=true`,final:false,...extra}}};
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
    async callServerTool(input){calls.push(input);return serverTool?serverTool(input):result(input.arguments.object_id,input.arguments.project_id,{url:`https://media.test/${input.arguments.object_id}.mp4?renewed=true`,download_url:`https://media.test/${input.arguments.object_id}.mp4?renewed=true&download=true`});}
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
  const h=host();
  await h.advance(10000);assert.equal(h.calls.length,0);
  const legacy=result('snippet');legacy.structuredContent.follow_project=true;
  h.app.ontoolresult(legacy);
  const player=h.document.querySelector('video');
  await h.advance(60*60000);await h.visible(false);await h.advance(60*60000);await h.visible(true);
  assert.equal(h.calls.length,0,'even legacy follow_project flags never poll for another asset');
  assert.equal(h.timers.size,0);assert.equal(h.document.querySelector('video'),player);
  assert.equal(h.messages.length,0);
}
for(const isPlaying of [false,true]){
  const h=host();h.app.ontoolresult(result('snippet','project',{duration:6}));
  const player=h.document.querySelector('video');player.paused=!isPlaying;player.ended=false;
  h.app.ontoolresult(result('final','project',{final:true,duration:30}));
  h.app.ontoolresult(result('other','other-project',{final:true}));
  h.app.ontoolresult({structuredContent:{project_id:'project',choices:{question:'Wrong card',options:[]}}});
  h.app.ontoolresult({structuredContent:{project_id:'project',media:{object_id:'snippet',media_type:'text/html',source_url:'https://example.test/other'}}});
  assert.equal(h.document.querySelector('video'),player,'late final, foreign project and other widget results cannot replace the sample');
  assert.equal(h.document.getElementById('visual').hidden,false);
  assert.equal(h.document.getElementById('choices').hidden,true);
  assert(player.src.includes('/snippet.mp4'));
  assert.equal(h.document.getElementById('media-status').textContent,'Sample · 6s');
  player.paused=true;player.ended=true;await h.visible(false);await h.visible(true);
  assert.equal(h.document.querySelector('video'),player,'ending playback or revisiting never promotes the sample to final');
  await h.document.getElementById('download').onclick();
  assert.equal(h.calls[0].arguments.object_id,'snippet');
  assert.equal(h.calls[0].arguments.project_id,'project');
  assert(h.calls.at(-1).open.url.includes('/snippet.mp4'));
  assert.equal(h.messages.length,0);
}
{
  const sample=host(),final=host(),other=host();
  sample.app.ontoolresult(result('snippet','project',{duration:6}));
  final.app.ontoolresult(result('final','project',{duration:30,final:true}));
  other.app.ontoolresult(result('other-video','other-project',{final:true}));
  const old=sample.document.querySelector('video');
  final.app.ontoolresult(result('final','project',{duration:30,final:true,url:'https://media.test/final.mp4?fresh=true'}));
  assert.equal(sample.document.querySelector('video'),old);
  assert(old.src.includes('/snippet.mp4'));
  assert.equal(final.document.getElementById('media-status').textContent,'Final video · 30s');
  for(const [h,object,project] of [[sample,'snippet','project'],[final,'final','project'],[other,'other-video','other-project']]){
    await h.document.getElementById('download').onclick();
    assert.equal(h.calls[0].arguments.object_id,object);
    assert.equal(h.calls[0].arguments.project_id,project);
    assert(h.calls.at(-1).open.url.includes(`/${object}.mp4`));
    assert.equal(h.messages.length,0);
  }
}
{
  const h=host();h.app.ontoolresult(result('snippet','project',{duration:6}));
  const player=h.document.querySelector('video');player.currentTime=3.2;player.duration=6;
  await player.onerror();
  assert.equal(h.calls[0].arguments.object_id,'snippet');
  assert.equal(h.document.querySelector('video'),player);
  assert(player.src.includes('?renewed=true'));
  player.onloadedmetadata();assert.equal(player.currentTime,3.2,'exact-object playback repair preserves position');
  assert.equal(h.document.getElementById('media-status').textContent,'Sample · 6s');
  h.app.ontoolresult({structuredContent:{project_id:'project',media:{object_id:'snippet',media_type:'video/mp4',url:'https://media.test/snippet.mp4?ticket=new',download_url:'https://media.test/snippet.mp4?ticket=new&download=true'}}});
  assert.equal(h.document.querySelector('video'),player,'same-object updates preserve the playback element');
  assert.equal(h.document.getElementById('media-status').textContent,'Sample · 6s','URL-only updates retain media metadata');
  assert(h.document.getElementById('download').href.includes('ticket=new'));
}
for(const wrong of [result('final','project'),result('snippet','other-project')]){
  const h=host({serverTool:async()=>wrong});h.app.ontoolresult(result('snippet'));
  const player=h.document.querySelector('video');
  await h.document.getElementById('download').onclick();
  assert.equal(h.calls.filter(call=>call.open).length,0,'a mismatched renewal never opens another file');
  assert.equal(h.document.querySelector('video'),player);assert(player.src.includes('/snippet.mp4'));
  assert(h.document.getElementById('notice').textContent.includes('could not be refreshed'));
}
{
  const pending=deferred(),h=host({serverTool:()=>pending.promise});
  h.app.ontoolresult(result('snippet'));
  const player=h.document.querySelector('video'),repair=player.onerror();
  const download=h.document.getElementById('download').onclick();
  assert.equal(h.calls.length,1,'simultaneous repair and download share one exact-object renewal');
  await h.app.onteardown();pending.resolve(result('snippet','project',{url:'https://media.test/late.mp4'}));await repair;await download;
  assert(player.src.includes('/snippet.mp4'),'late URL responses after teardown are ignored');
  assert.equal(h.calls.filter(call=>call.open).length,0);
  await h.visible(false);await h.visible(true);await h.advance(60000);assert.equal(h.calls.length,1);
}
{
  const h=host({capabilities:{}});h.app.ontoolresult(result('snippet'));
  await h.document.getElementById('download').onclick();
  assert.equal(h.calls.length,1);assert(h.calls[0].open.url.includes('/snippet.mp4'),'hosts without tool calls retain the supplied download link');
}
{
  const h=host();h.app.ontoolresult(result('snippet'));
  const first=h.document.querySelector('video');await h.app.onteardown();
  h.app.ontoolresult(result('final','project',{final:true}));
  assert.equal(h.document.querySelector('video'),first,'teardown does not release the pinned identity');
  h.app.ontoolresult(result('snippet'));
  const restored=h.document.querySelector('video');
  assert.notEqual(restored,first,'remounting the same asset restores playback callbacks');
  await restored.onerror();assert.equal(h.calls[0].arguments.object_id,'snippet');
  assert(restored.src.includes('renewed=true'));
}
{
  const h=host();h.app.ontoolresult(result('snippet','project',{truncated:true,duration:6,source_duration:30}));
  assert.equal(h.document.getElementById('excerpt').textContent,'Preview excerpt · 6s of 30s');
  h.app.ontoolresult(result('final','project',{final:true}));
  assert.equal(h.document.getElementById('excerpt').hidden,false,'the original sample keeps its own excerpt label');
}
console.log('PASS pinned sample and final cards stay separate across playback, host updates, visibility, exact URL renewal and independent projects');
