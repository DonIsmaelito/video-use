import {parseHTML} from 'linkedom';
import {PostMessageTransport} from '@modelcontextprotocol/ext-apps';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source=fs.readFileSync(new URL('question-app.js',import.meta.url),'utf8').replace(/^import[^\n]*\n/,''),template=fs.readFileSync(new URL('question-template.html',import.meta.url),'utf8');
const plain=value=>JSON.parse(JSON.stringify(value));
const caps={serverTools:{},updateModelContext:{text:{}},message:{text:{}}};
const question=(revision=1,id='involvement-one',project='project')=>({project_id:project,question:{id,revision,status:'awaiting_user',questions:[{id:'involvement',prompt:'How involved would you like to be?',recommended:'key_moments',options:[{id:'delegate',label:'Hands off'},{id:'key_moments',label:'Key moments'},{id:'hands_on',label:'Hands on'}]}],required:['involvement'],recorded_answers:{}}});
const basics=()=>({project_id:'project',question:{id:'basics-one',revision:1,status:'awaiting_user',questions:[{id:'duration',prompt:'How long should it be?',options:[{id:'30',label:'30 seconds'},{id:'you_decide',label:'You decide'}]},{id:'destination',prompt:'Where will it be watched?',options:[{id:'web',label:'On the web'},{id:'vertical',label:'Vertical'}]}],required:['duration','destination'],recorded_answers:{}}});
function host({capabilities=caps,tool,message,context,hostContext={theme:'light'}}={}){
  const {document}=parseHTML(template),calls=[],messages=[],contexts=[],events=[];let app;
  class App{
    constructor(){app=this;}async connect(){}getHostCapabilities(){return capabilities;}getHostContext(){return hostContext;}
    async callServerTool(input){calls.push(plain(input));events.push('save');return tool?tool(input):{structuredContent:{saved:true,message:'Hands on.',context:{project_id:input.arguments.project_id,saved_answers:input.arguments.answers}}};}
    async updateModelContext(input){contexts.push(plain(input));events.push('context');return context?context(input):{};}
    async sendMessage(input){messages.push(plain(input));events.push('message');return message?message(input):{};}
  }
  vm.runInNewContext(source,{document,App,console,applyDocumentTheme(theme){document.documentElement.setAttribute('data-theme',theme);},applyHostStyleVariables(values){for(const [key,value]of Object.entries(values))document.documentElement.style.setProperty(key,value);}});
  return {document,app,calls,messages,contexts,events,show(data){app.ontoolresult({structuredContent:plain(data)});}};
}
const el=(h,id)=>h.document.getElementById(id);
const button=(h,q='involvement',option='hands_on')=>h.document.querySelector(`[data-question="${q}"][data-option="${option}"]`);
const choose=(h,q,option)=>button(h,q,option).onclick();
const submit=h=>el(h,'choice-continue').onclick();

{
  const h=host();h.show(question());
  assert.equal(h.document.querySelectorAll('[aria-pressed="true"]').length,0,'recommendation is never selected');
  assert.equal(h.document.querySelectorAll('.choice-options button').length,3);
  assert.equal(el(h,'choice-continue').hidden,true);
  assert.equal(el(h,'chat-fallback').textContent,'Or reply in chat.');
  await choose(h);
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].name,'submit_video_choice');
  assert.deepEqual(h.calls[0].arguments.answers,{involvement:'hands_on'});
  assert.equal(h.calls[0].arguments.widget_id,'involvement-one');assert.equal(h.calls[0].arguments.revision,1);
  assert(h.calls[0].arguments.request_id);
  assert.deepEqual(h.events,['save','context','message']);
  assert.equal(h.messages[0].content[0].text,'Hands on.');
  assert(!JSON.stringify(h.messages).includes('project'));assert(!JSON.stringify(h.messages).includes('involvement'));
  assert.equal(button(h).getAttribute('aria-pressed'),'true');assert.equal(button(h).disabled,true);
  await choose(h);assert.equal(h.calls.length,1,'saved answer cannot be submitted twice');
  assert.equal(el(h,'choice-reply').hidden,true);
}
{
  const h=host();h.show(basics());
  assert.equal(el(h,'choice-continue').disabled,true);
  await choose(h,'duration','30');await submit(h);
  assert.equal(h.calls.length,0,'all required answers must be explicit');
  await choose(h,'destination','web');assert.equal(h.calls.length,0,'multi-question choice waits for Continue');
  await submit(h);assert.deepEqual(h.calls[0].arguments.answers,{duration:'30',destination:'web'});
}
{
  let resolve;const pending=new Promise(done=>{resolve=done;});
  const h=host({tool:()=>pending});h.show(question());const saving=choose(h);
  assert.equal(button(h).disabled,true);assert.equal(el(h,'choice-status').textContent,'Saving…');
  await choose(h,'involvement','delegate');assert.equal(h.calls.length,1,'double clicks cannot overlap saves');
  h.show(question(1,'other-question','another-project'));
  assert.equal(button(h).getAttribute('aria-pressed'),'true','unrelated result cannot replace pinned card');
  resolve({structuredContent:{saved:true,message:'Hands on.',context:'Saved involvement: Hands on.'}});await saving;
  assert.equal(h.messages.length,1);assert.equal(h.calls[0].arguments.project_id,'project');
}
{
  let attempts=0;
  const h=host({tool:async()=>{if(++attempts<3)throw Error('Disconnected');return {structuredContent:{saved:true,message:'Hands on.',context:'Saved Hands on.'}};}});
  h.show(question());await choose(h);assert.equal(el(h,'choice-continue').textContent,'Try again');
  const selected=button(h);h.show(question());assert.equal(button(h),selected,'identical refresh preserves draft and retry');
  await submit(h);await submit(h);
  assert.equal(h.calls.length,3);assert.equal(new Set(h.calls.map(c=>c.arguments.request_id)).size,1,'network retries are idempotent');
  assert.equal(h.messages.length,1);
}
{
  const h=host({tool:async()=>({isError:true,content:[{type:'text',text:'Not saved'}]})});
  h.show(question());await choose(h);await choose(h,'involvement','delegate');
  assert.equal(h.messages.length,0);assert.equal(h.contexts.length,0);
  assert.notEqual(h.calls[0].arguments.request_id,h.calls[1].arguments.request_id,'changed choice is a distinct request');
  assert(el(h,'choice-status').textContent.includes('Could not save'));
}
{
  let attempts=0;const h=host({message:async()=>++attempts===1?{isError:true}:{}});
  h.show(question());await choose(h);
  assert.equal(el(h,'choice-status').textContent,'Saved. Send reply');assert.equal(el(h,'choice-reply').hidden,false);
  assert.equal(el(h,'choice-reply-text').textContent,'Hands on.');
  await el(h,'choice-reply').onclick();await el(h,'choice-reply').onclick();
  assert.equal(h.calls.length,1,'reply retries never save again');
  assert.equal(h.contexts.length,1,'successfully updated context is not replayed');
  assert.equal(h.messages.length,2);assert.equal(el(h,'choice-reply').hidden,true);
}
{
  let attempts=0;const h=host({context:async()=>{if(++attempts===1)throw Error('Context failed');return {};}});
  h.show(question());await choose(h);assert.equal(h.messages.length,0,'context must be applied before the reply');
  await el(h,'choice-reply').onclick();assert.equal(h.calls.length,1);assert.equal(h.contexts.length,2);assert.equal(h.messages.length,1);
}
{
  const h=host({capabilities:{}});h.show(question());await choose(h);
  assert.equal(h.calls.length,0);assert(el(h,'choice-status').textContent.includes('reply in chat'));
}
for (const capabilities of [{serverTools:{},updateModelContext:{text:{}}},{serverTools:{},message:{text:{}}}]) {
  const h=host({capabilities});h.show(question());await choose(h);
  assert.equal(h.calls.length,1);assert.equal(h.messages.length,0);assert.equal(el(h,'choice-status').textContent,'Saved. Reply in chat to continue.');
  assert.equal(el(h,'choice-reply').hidden,true,'unsupported host capability must not produce a dead retry button');
  assert.equal(el(h,'choice-reply-text').textContent,'Hands on.');
}
{
  const h=host();const saved=question(2);saved.question.status='answered';saved.question.recorded_answers={involvement:'delegate'};
  h.show(saved);assert.equal(button(h,'involvement','delegate').getAttribute('aria-pressed'),'true');
  assert.equal(button(h).disabled,true);assert.equal(h.calls.length,0);assert.equal(h.messages.length,0,'loading saved choices never emits a reply');
  h.show(question(1));h.show(question(4,'other-question'));h.show(question(4,'involvement-one','other-project'));
  assert.equal(button(h,'involvement','delegate').getAttribute('aria-pressed'),'true');
  h.show({saved:true,message:'Another result',context:{}});assert.equal(el(h,'choice-status').textContent,'Saved.');
}
{
  const h=host();const malicious=question();malicious.question.questions[0].prompt='<img src=x onerror=alert(1)>';
  malicious.question.questions[0].options[0].label='<script>alert(1)</script>';
  h.show(malicious);assert.equal(h.document.querySelector('img'),null);assert.equal(h.document.querySelectorAll('script').length,1);
  assert.equal(h.document.querySelector('legend').textContent,'<img src=x onerror=alert(1)>');
  await Promise.resolve();assert.equal(h.document.documentElement.getAttribute('data-theme'),'light');
  h.app.onhostcontextchanged({theme:'dark',styles:{variables:{'--color-text-primary':'#fafafa'}}});
  assert.equal(h.document.documentElement.getAttribute('data-theme'),'dark');assert.equal(h.document.documentElement.style.getPropertyValue('--color-text-primary'),'#fafafa');
}
{
  let resolve;const h=host({tool:()=>new Promise(done=>{resolve=done;})});h.show(question());const pending=choose(h);
  await h.app.onteardown();resolve({structuredContent:{saved:true,message:'Hands on.',context:'Saved.'}});await pending;
  assert.equal(h.messages.length,0,'a closed card cannot send a late reply');assert.equal(h.contexts.length,0);
}
{
  const listeners=new Map(),parent={postMessage(){}};globalThis.window={parent,addEventListener(name,fn){listeners.set(name,fn);},removeEventListener(name){listeners.delete(name);}};
  const transport=new PostMessageTransport(parent,parent),received=[];transport.onmessage=value=>received.push(value);await transport.start();
  const message={jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:question()}};
  listeners.get('message')({source:{},data:message});assert.equal(received.length,0,'SDK ignores messages from unrelated windows');
  listeners.get('message')({source:parent,data:message});assert.equal(received.length,1);
  await transport.close();delete globalThis.window;
}
console.log('PASS compact choices save explicit answers and safely deliver chat replies');
