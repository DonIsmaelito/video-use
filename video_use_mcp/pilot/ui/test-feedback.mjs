import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,'');
const template=fs.readFileSync('template.html','utf8');
const caps={serverTools:{},updateModelContext:{text:{}},message:{text:{}}};
const result=(object='video-one',project='project')=>({structuredContent:{project_id:project,media:{object_id:object,media_type:'video/mp4',url:`https://private.test/${object}?ticket=private-token`,duration:30,final:true}}});
function host({capabilities=caps,tool,message}={}){
  const {document}=parseHTML(template),calls=[],contexts=[],messages=[];let app;
  class App{
    constructor(){app=this}async connect(){}
    getHostCapabilities(){return capabilities}
    async callServerTool(input){calls.push(input);return tool?tool(input):{structuredContent:{creative:{revision:4},feedback:{id:'saved'}}}}
    async updateModelContext(input){contexts.push(input)}
    async sendMessage(input){messages.push(input);return message?message(input):{}}
    async openLink(){}
  }
  vm.runInNewContext(source,{document,App,applyDocumentTheme(){},console,setTimeout(){return 1},clearTimeout(){}});
  return {document,app,calls,contexts,messages};
}
function begin(h,seconds=6.375){
  const video=h.document.querySelector('video');video.currentTime=seconds;video.paused=false;
  video.pause=()=>{video.paused=true;video.onpause?.()};
  h.document.getElementById('suggest-edit').onclick();return video;
}
async function submit(h,note='Make the diagram larger'){
  h.document.getElementById('feedback-note').value=note;
  await h.document.getElementById('feedback-form').onsubmit({preventDefault(){}});
}

{
  const h=host();h.app.ontoolresult(result());
  assert.equal(h.document.getElementById('suggest-edit').hidden,false);
  const video=begin(h);
  assert(video.paused);assert.equal(h.document.getElementById('feedback-time').textContent,'At 0:06.4');
  assert.equal(h.calls.length,0,'opening feedback never sends tools or chat messages');
  const note='Make <this> bigger';await submit(h,note);
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].name,'add_video_feedback');
  assert.equal(h.calls[0].arguments.project_id,'project');assert.equal(h.calls[0].arguments.object_id,'video-one');
  assert.equal(h.calls[0].arguments.seconds,6.375);assert.equal(h.calls[0].arguments.note,note);
  assert(h.calls[0].arguments.request_id.length>5);
  assert.equal(h.contexts.length,1);assert.equal(h.messages.length,1);
  assert(JSON.stringify(h.messages).includes(note));assert(!JSON.stringify(h.messages).includes('private-token'));
  assert.equal(h.document.getElementById('feedback-form').hidden,true);
  assert.equal(h.document.getElementById('notice').textContent,'Suggestion sent.');
  assert.equal(h.document.querySelector('this'),null,'feedback text never becomes HTML');
}

{
  const h=host();h.app.ontoolresult(result());const original=begin(h,12);
  h.app.ontoolresult(result('new-version'));
  assert.equal(h.document.querySelector('video'),original,'new versions wait while a suggestion is being written');
  await submit(h,'Slow this section down');
  assert.equal(h.calls[0].arguments.object_id,'video-one','feedback is pinned to the watched version');
  assert(h.document.querySelector('video').src.includes('new-version'));
}

{
  const h=host();h.app.ontoolresult(result());begin(h,8);
  h.app.ontoolresult(result('new-version'));h.document.getElementById('feedback-cancel').onclick();
  assert.equal(h.calls.length,0);assert.equal(h.messages.length,0);
  assert(h.document.querySelector('video').src.includes('new-version'));
}

{
  const h=host({capabilities:{}});h.app.ontoolresult(result());begin(h,14);await submit(h,'Use less text');
  assert.equal(h.calls.length,0);assert.equal(h.messages.length,0);
  assert.equal(h.document.getElementById('notice').textContent,'Copy into chat: At 0:14.0, Use less text');
}
for(const options of [{capabilities:{serverTools:{},updateModelContext:{text:{}}}},{message:async()=>({isError:true})}]){
  const h=host(options);h.app.ontoolresult(result());begin(h);await submit(h);
  assert.equal(h.calls.length,1);
  assert.equal(h.document.getElementById('notice').textContent,'Suggestion saved. Tell your assistant to continue if the chat is waiting.');
}

{
  let attempts=0;
  const h=host({tool:async()=>++attempts===1?{isError:true,content:[{type:'text',text:'Transfer interrupted; try again.'}]}:{structuredContent:{creative:{revision:4}}}});
  h.app.ontoolresult(result());begin(h);await submit(h);
  assert.equal(h.messages.length,0,'failed saves never send a success message');
  assert.equal(h.document.getElementById('feedback-form').hidden,false);
  assert.equal(h.document.getElementById('feedback-note').disabled,false);
  await submit(h);assert.equal(h.calls[0].arguments.request_id,h.calls[1].arguments.request_id,'exact retry keeps idempotency key');
  assert.equal(h.messages.length,1);
}

{
  let resolve;const pending=new Promise(done=>{resolve=done});
  const h=host({tool:()=>pending});h.app.ontoolresult(result());begin(h,9);
  const sending=submit(h,'Align the heading');
  await submit(h,'Duplicate');assert.equal(h.calls.length,1,'duplicate submits never overlap');
  h.app.ontoolresult(result('another-video','another-project'));
  resolve({structuredContent:{creative:{revision:4}}});await sending;
  assert(h.document.querySelector('video').src.includes('another-video'));
  assert.equal(h.document.getElementById('notice').textContent,'','previous completion cannot claim the new project was edited');
  assert(JSON.stringify(h.messages).includes('project project'));
  assert(!JSON.stringify(h.messages).includes('another-project'));
}
console.log('PASS timestamped feedback captures the exact version saves once and sends messages only on explicit submission with honest host fallbacks');
