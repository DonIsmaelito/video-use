// Creative feedback belongs in the host chat; the media surface stays minimal.
import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,'');
const template=fs.readFileSync('template.html','utf8');
const result=(object='video-one',project='project',extra={})=>({structuredContent:{project_id:project,media:{object_id:object,media_type:'video/mp4',url:`https://private.test/${object}?ticket=expired-token`,download_url:`https://private.test/${object}?ticket=expired-token&download=true`,final:true,...extra}}});
function host({tool,capabilities={serverTools:{}}}={}){
  const {document}=parseHTML(template),calls=[],messages=[],links=[];let app;
  class App{
    constructor(){app=this}async connect(){}
    getHostCapabilities(){return capabilities}
    async callServerTool(input){calls.push(input);return tool?tool(input):result(input.arguments.object_id,input.arguments.project_id,{url:'https://private.test/fresh?ticket=new',download_url:'https://private.test/fresh?ticket=new&download=true'})}
    async updateModelContext(input){messages.push(input)}async sendMessage(input){messages.push(input)}
    async openLink(input){links.push(input)}
  }
  vm.runInNewContext(source,{document,App,applyDocumentTheme(){},console,setTimeout(){return 1},clearTimeout(){}});
  return {document,app,calls,messages,links};
}
{
  const h=host();h.app.ontoolresult(result());
  for(const id of ['suggest-edit','expand','feedback-form','feedback-shortcuts','edit-labels','edit-pace','edit-look'])assert.equal(h.document.getElementById(id),null,`${id} must not exist`);
  assert.equal(h.document.querySelector('.media-brand'),null);
  const player=h.document.querySelector('video');assert(player.controls);assert.equal(player.preload,'metadata');
  assert.equal(h.document.querySelectorAll('#visual button').length,0);assert.equal(h.calls.length,0);
  await h.document.getElementById('download').onclick();
  assert.equal(h.calls[0].name,'video_preview_updates');assert.equal(h.calls[0].arguments.object_id,'video-one');
  assert.equal(h.calls[0].arguments.project_id,'project');assert(h.links[0].url.includes('ticket=new'));
  assert.equal(h.document.querySelector('video'),player,'renewing download does not reset watched video');
  assert.equal(h.messages.length,0,'the player never prepares machine instructions in chat');
}
{
  const h=host();h.app.ontoolresult(result());const video=h.document.querySelector('video');video.currentTime=4.2;video.duration=30;
  await video.onerror();assert.equal(h.calls.length,1);assert.equal(h.calls[0].arguments.object_id,'video-one');
  assert(video.src.includes('ticket=new'));video.onloadedmetadata();assert.equal(video.currentTime,4.2,'URL repair preserves position');
  await video.onerror();assert.equal(h.calls.length,1,'an unplayable renewed URL cannot cause a retry loop');
  assert(h.document.getElementById('notice').textContent.includes('could not be loaded'));
}
{
  let finish;const pending=new Promise(done=>{finish=done});const h=host({tool:()=>pending});
  h.app.ontoolresult(result());const old=h.document.querySelector('video');const downloading=h.document.getElementById('download').onclick();
  h.app.ontoolresult(result('new-version','new-project'));
  finish(result('video-one','project'));await downloading;
  assert.equal(h.links.length,0,'late renewals never open a different project');assert.notEqual(h.document.querySelector('video'),old);
}
{
  const h=host({tool:async()=>({isError:true,content:[{type:'text',text:'Video not found'}]})});h.app.ontoolresult(result());
  await h.document.getElementById('download').onclick();assert.equal(h.links.length,0);
  assert(h.document.getElementById('notice').textContent.includes('could not be refreshed'));
}
for(const media of [
  {media_type:'video/mp4',url:'https://source.test/clip.mp4'},
  {media_type:'video/webm',url:'https://source.test/clip.webm'},
  {media_type:'text/html',embed_url:'https://player.vimeo.com/video/123'},
  {media_type:'source_link'},
]){
  const h=host();h.app.ontoolresult({structuredContent:{project_id:'project',follow_project:false,reference_id:'ref',media:{...media,source_url:'https://source.test/work',title:'The actual source',caption:'Source clip'}}});
  assert.equal(h.document.getElementById('download').hidden,true,'reference sources are never copied/downloaded');
  assert.equal(h.document.getElementById('media-status').textContent,'Source clip');
  assert.equal(h.document.getElementById('source-reference').hidden,false);assert.equal(h.document.getElementById('source-reference').textContent,'The actual source');
  if(media.media_type==='text/html'){
    const frame=h.document.querySelector('iframe');assert(frame);assert.equal(frame.getAttribute('sandbox'),'allow-scripts allow-same-origin allow-presentation');assert(frame.src.includes('/video/123'));
  }else if(media.media_type==='source_link'){assert.equal(h.document.querySelector('video,img,iframe'),null);assert(h.document.getElementById('media').hidden);}
  else{assert(h.document.querySelector('video').controls);await h.document.querySelector('video').onerror();assert(h.document.getElementById('notice').textContent.includes('Open the reference'));}
  await h.document.getElementById('source-reference').onclick();assert.equal(h.links[0].url,'https://source.test/work');
  assert.equal(h.calls.length,0);assert.equal(h.messages.length,0);
}
console.log('PASS native media supports external references and exact-version expiry repair with no custom editing controls');
