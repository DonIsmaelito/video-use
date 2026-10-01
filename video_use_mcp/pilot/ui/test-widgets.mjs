import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,''),template=fs.readFileSync('template.html','utf8');
const plain=value=>JSON.parse(JSON.stringify(value));
const caps={serverTools:{},updateModelContext:{text:{}},message:{text:{}}};
const brief=(revision=1,id='brief-one',project='project')=>({project_id:project,widget:{id,kind:'brief',title:'What should this feel like?',revision,creative_revision:3,state:'open',questions:[{id:'audience',prompt:'Who is watching?',recommended:'new',options:[{id:'new',label:'New to the topic'},{id:'familiar',label:'Already familiar'}]},{id:'mood',prompt:'What mood?',options:[{id:'calm',label:'Calm'},{id:'energetic',label:'Energetic'}]}],answers:{}},creative:{revision:3}});
const story=(revision=1)=>({project_id:'project',widget:{id:'story-one',kind:'story',title:'The story',revision,creative_revision:3,state:'open',beats:[{id:'opening',title:'The question',visual:'A sunlit panel',narration:'Where does electricity begin?',seconds:4},{id:'answer',title:'The mechanism',visual:'Charge moves around a circuit',narration:'Light releases charge.',seconds:6}]},creative:{revision:3}});
function host({capabilities=caps,tool,message,context,display}={}){
  const {document}=parseHTML(template),calls=[],messages=[],contexts=[],displayCalls=[];let app,latest;
  class App{
    constructor(){app=this}async connect(){}getHostCapabilities(){return capabilities}
    getHostContext(){return context || {}}
    async callServerTool(input){calls.push(plain(input));if(tool)return tool(input);return {structuredContent:{...latest,saved:true,widget:{...latest.widget,...input.arguments,revision:input.arguments.revision+1,creative_revision:4},creative:{revision:4}}};}
    async updateModelContext(input){contexts.push(plain(input));return {}}
    async sendMessage(input){messages.push(plain(input));return message?message(input):{}}
    async requestDisplayMode(input){displayCalls.push(input);return display?display(input):{mode:input.mode}}
    async openLink(){}
  }
  vm.runInNewContext(source,{document,App,applyDocumentTheme(){},console,setTimeout(){return 1},clearTimeout(){}});
  return {document,app,calls,messages,contexts,displayCalls,show(data){latest=plain(data);app.ontoolresult({structuredContent:data});}};
}
const el=(h,id)=>h.document.getElementById(id);
const choose=(h,q='audience',option='new')=>h.document.querySelector(`[data-question="${q}"][data-option="${option}"]`).onclick();
const submit=h=>el(h,'widget-form').onsubmit({preventDefault(){}});
function edit(h,field,value,beat='opening'){
  const input=h.document.querySelector(`[data-beat="${beat}"][data-field="${field}"]`);input.value=value;input.oninput();return input;
}

{
  const h=host();h.show(brief());
  assert.equal(el(h,'visual').hidden,true);assert.equal(el(h,'widget').hidden,false);
  assert.equal(h.document.querySelectorAll('[aria-pressed="true"]').length,0,'suggested option is never implicit selection');
  assert.equal(el(h,'widget-submit').disabled,true);
  choose(h);assert.equal(h.calls.length,0);assert.equal(h.messages.length,0,'chips stay local until Save');
  await submit(h);
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].name,'save_video_widget');
  assert.deepEqual(h.calls[0].arguments.answers,{audience:'new'});
  assert.equal(h.calls[0].arguments.revision,1);assert(h.calls[0].arguments.request_id);
  assert.equal(h.messages.length,1);assert.equal(h.contexts.length,1);
  assert.equal(h.messages[0].content[0].text,'New to the topic.');
  assert(JSON.stringify(h.contexts).includes('not final approval'));
  assert(!JSON.stringify(h.messages).includes('brief-one'));assert(!JSON.stringify(h.messages).includes('revision'));
  assert.equal(el(h,'widget-status').textContent,'Changes saved. Send the prepared reply to continue.');
  await submit(h);assert.equal(h.calls.length,1,'a second save of unchanged inputs is not a second user message');
}
{
  const h=host();h.show(brief());choose(h);choose(h);await submit(h);
  assert.equal(h.calls.length,0,'an empty selection is not submitted');
}
{
  const saved=brief(2);saved.widget.answers={audience:'new'};
  const h=host();h.show(saved);
  assert.equal(el(h,'widget-submit').disabled,true,'unchanged persisted answers do not resubmit');
  choose(h);
  assert.equal(el(h,'widget-submit').disabled,false,'clearing the last persisted answer is an explicit edit');
  assert.equal(h.calls.length,0,'deselecting stays local until Save');
  await submit(h);
  assert.deepEqual(h.calls[0].arguments.answers,{});
  assert.equal(h.messages.length,1);
  assert.equal(h.messages[0].content[0].text,'I cleared those saved preferences. Please leave them undecided for now.');
  assert(!JSON.stringify(h.contexts).includes('New to the topic'),'cleared answers do not remain in model context');
  assert.equal(el(h,'widget-submit').disabled,true);
}
{
  const h=host();h.show(story());
  assert.equal(h.document.querySelectorAll('.story-beat').length,2);
  assert.equal(el(h,'widget-submit').textContent,'Send changes');
  const title=edit(h,'title','<img src=x onerror=alert(1)>');
  edit(h,'narration','A clearer opening.');edit(h,'seconds','5.5');
  h.show(story());assert.equal(h.document.querySelector('[data-field="title"]'),title,'same revision refresh preserves input DOM and focus');
  assert.equal(title.value,'<img src=x onerror=alert(1)>');
  await submit(h);
  assert.equal(h.calls[0].arguments.beats[0].seconds,5.5);
  assert.equal(h.calls[0].arguments.beats[0].id,'opening');
  assert.equal(h.calls[0].arguments.beats[1].id,'answer');
  assert.equal(h.document.querySelector('img'),null,'user content stays text');
  assert.equal(h.messages[0].content[0].text,"I've updated the story. Please use my saved changes.");
  assert(h.contexts[0].content[0].text.includes('A clearer opening.'));
  assert(!h.messages[0].content[0].text.includes('opening'),'story JSON and beat IDs never enter the composer');
}
{
  const h=host();h.show(story());const input=edit(h,'visual','My unsent diagram');
  const update=story(2);update.widget.beats[0].visual='New server direction';h.show(update);
  assert.equal(input.value,'My unsent diagram');assert.equal(el(h,'widget-latest').hidden,false);
  await submit(h);assert.equal(h.calls.length,0,'newer revision is never silently overwritten');
  el(h,'widget-latest').onclick();assert.equal(h.document.querySelector('[data-field="visual"]').value,'New server direction');
  assert.equal(h.calls.length,0,'loading latest does not approve or save it');
  edit(h,'title','After review');await submit(h);assert.equal(h.calls[0].arguments.revision,2);
  h.show(story(1));assert.equal(h.document.querySelector('[data-field="title"]').value,'After review','late older result cannot regress saved content');
}
{
  let attempts=0;
  const h=host({tool:async input=>++attempts<3?{isError:true,content:[{type:'text',text:'This widget changed. Your edit was not saved.'}]}:{structuredContent:{...brief(),widget:{...brief().widget,revision:2,answers:plain(input.arguments.answers)},creative:{revision:4}}}});
  h.show(brief());choose(h);await submit(h);await submit(h);
  assert.equal(h.calls[0].arguments.request_id,h.calls[1].arguments.request_id,'unchanged retries retain their request ID');
  assert.equal(h.messages.length,0);assert.equal(el(h,'widget-submit').disabled,false);
  assert.equal(h.document.querySelector('[aria-pressed="true"]').dataset.option,'new','save errors preserve the chosen answer');
  choose(h,'mood','calm');await submit(h);
  assert.notEqual(h.calls[1].arguments.request_id,h.calls[2].arguments.request_id,'changed input receives a new request ID');
  assert.equal(h.messages.length,1);
}
{
  let resolve;const pending=new Promise(done=>{resolve=done});
  const h=host({tool:()=>pending});h.show(brief());choose(h);const save=submit(h);await submit(h);
  assert.equal(h.calls.length,1,'double click cannot create overlapping requests');
  h.show(brief(1,'different-widget','another-project'));
  resolve({structuredContent:{...brief(),widget:{...brief().widget,revision:2,answers:{audience:'new'}},creative:{revision:4}}});await save;
  assert.equal(h.document.querySelectorAll('[aria-pressed="true"]').length,0,'late save cannot edit a new widget');
  assert.equal(el(h,'widget-status').textContent,'');
  assert(h.contexts[0].content[0].text.includes('\"project_id\":\"project\"'));
  assert(!JSON.stringify(h.messages).includes('project'));
  assert(!JSON.stringify(h.messages).includes('another-project'));
}
{
  const h=host({tool:async()=>({structuredContent:{...brief(),saved:false}})});h.show(brief());choose(h);await submit(h);
  assert.equal(h.messages.length,0);assert.equal(h.contexts.length,0);
  assert.equal(el(h,'widget-status').textContent,'No new changes to save.');
}
{
  const latest=brief(3);latest.widget.answers={audience:'familiar'};
  const h=host({tool:async()=>({structuredContent:{...latest,saved:true,repeated:true}})});
  h.show(brief());choose(h);await submit(h);
  assert.equal(h.document.querySelector('[aria-pressed="true"]').dataset.option,'familiar','acknowledged retries display authoritative newer state');
  assert.equal(h.messages.length,0,'acknowledging an older request does not replay it as a new user instruction');
  const context=JSON.stringify(h.contexts);
  assert(context.includes('Already familiar'),'model context receives authoritative later choices');
  assert(!context.includes('New to the topic'),'earlier values are not published as current context');
  assert(context.includes('Do not replay the earlier submitted values'));
  assert.equal(el(h,'widget-status').textContent,'Earlier save confirmed. Newer changes are shown.');
}
{
  const saved=story(2);saved.widget.creative_revision=4;saved.creative={revision:5,beats:[{...saved.widget.beats[0],title:'Latest plan elsewhere'}],preferences:'Keep the later feedback'};
  const h=host({tool:async()=>({structuredContent:{...saved,saved:true,repeated:true}})});
  h.show(story());edit(h,'title','Earlier submitted title');await submit(h);
  const context=JSON.stringify(h.contexts);
  assert.equal(h.messages.length,0);
  assert(context.includes('Latest plan elsewhere'));assert(context.includes('Keep the later feedback'));
  assert(!context.includes('Earlier submitted title'));
}
{
  const same=brief(2);same.widget.answers={audience:'new'};
  const h=host({tool:async()=>({structuredContent:{...same,saved:true,repeated:true}})});
  h.show(brief());choose(h);await submit(h);await submit(h);
  assert.equal(h.calls.length,1);assert.equal(h.messages.length,1,'an exact retry with no later changes acknowledges the original save once');
  assert(JSON.stringify(h.contexts).includes('New to the topic'));
}
{
  const h=host({tool:async()=>({structuredContent:brief(1,'wrong-widget')})});h.show(brief());choose(h);await submit(h);
  assert.equal(h.messages.length,0);assert.equal(h.contexts.length,0);
  assert.equal(h.document.querySelector('[aria-pressed="true"]').dataset.option,'new');
  assert(el(h,'widget-status').textContent.includes('could not be confirmed'));
}
{
  const h=host({capabilities:{}});h.show(brief());choose(h);await submit(h);
  assert.equal(h.calls.length,0);assert.equal(h.messages.length,0);
  assert(el(h,'widget-status').textContent.includes('Copy your preferences'));
}
for(const options of [{capabilities:{serverTools:{},updateModelContext:{text:{}}}},{message:async()=>({isError:true})}]){
  const h=host(options);h.show(brief());choose(h);await submit(h);
  assert.equal(h.calls.length,1);assert.equal(el(h,'widget-status').textContent,'Changes saved. Tell your assistant to continue if the chat is waiting.');
}
{
  const h=host();h.show(story());edit(h,'seconds','0');await submit(h);
  assert.equal(h.calls.length,0);assert(el(h,'widget-status').textContent.includes('duration'));
}
const media={project_id:'project',media:{object_id:'video',media_type:'video/mp4',url:'https://private.test/clip',final:true}};
{
  const h=host({context:{availableDisplayModes:['inline','fullscreen'],displayMode:'inline'}});h.show(media);
  const video=h.document.querySelector('video');video.currentTime=4.2;video.paused=false;
  assert.equal(el(h,'expand').hidden,false);await el(h,'expand').onclick();
  assert.equal(h.displayCalls[0].mode,'fullscreen');assert.equal(el(h,'expand').textContent,'Exit fullscreen');
  assert.equal(h.document.querySelector('video'),video);assert.equal(video.currentTime,4.2);assert.equal(video.paused,false);
  await el(h,'expand').onclick();assert.equal(h.displayCalls[1].mode,'inline');
  assert.equal(h.messages.length,0);assert.equal(h.calls.length,0,'display mode never sends model or server requests');
  h.app.onhostcontextchanged({availableDisplayModes:['inline'],displayMode:'inline'});assert.equal(el(h,'expand').hidden,true);
}
{
  const h=host();h.show(media);assert.equal(el(h,'expand').hidden,true);await el(h,'expand').onclick();assert.equal(h.displayCalls.length,0);
}
{
  const h=host({context:{availableDisplayModes:['inline','fullscreen'],displayMode:'inline'},display:async()=>({isError:true})});h.show(media);const video=h.document.querySelector('video');
  await el(h,'expand').onclick();assert.equal(h.document.querySelector('video'),video);
  assert.equal(el(h,'expand').disabled,false);assert(el(h,'notice').textContent.includes('could not expand'));
}
console.log('PASS optional brief and story editors preserve unsaved changes save explicitly handle retries and stale results and expand existing playback only on supported hosts');

// Cached intake widgets keep their behavior, but only human answers reach the composer.
for(const [purpose,id,option,label,expected] of [
  ['mode','involvement','hands_on','Hands on','Hands on, please.'],
  ['basics','viewing_destination','landscape','Landscape for YouTube','Landscape for YouTube.'],
  ['excerpt_review','excerpt_review','continue','Continue with this','Continue with this direction.'],
  ['excerpt_review','excerpt_review','refine','Refine the sample',"I'd like to refine this sample."],
]){
  const data=brief();data.project_id='private-project-uuid';
  data.widget={...data.widget,id:'private-widget-uuid',purpose,required:[id],questions:[{id,prompt:'Your preference?',options:[{id:option,label}]}]};
  const intake={version:1,mode:'hands_on',phase:'production',next_action:'INTERNAL_NEXT_ACTION '.repeat(200),excerpt_review:{status:'approved',object_id:'private-object-uuid'}};
  const h=host({tool:async input=>({structuredContent:{...data,saved:true,intake,widget:{...data.widget,answers:input.arguments.answers,revision:2},creative:{revision:4}}})});
  h.show(data);choose(h,id,option);await submit(h);
  assert.equal(h.messages[0].content[0].text,expected);
  assert(h.messages[0].content[0].text.length<80,'a large saved state does not expand the human reply');
  for(const internal of ['private-project-uuid','private-widget-uuid','private-object-uuid','INTERNAL_NEXT_ACTION']){
    assert(!JSON.stringify(h.messages).includes(internal));
    assert(JSON.stringify(h.contexts).includes(internal),'background context retains precise saved state');
  }
  assert.equal(el(h,'widget-status').textContent,'Changes saved. Send the prepared reply to continue.','resolved sendMessage is not evidence the user sent the draft');
}
{
  const data=brief();data.widget.purpose='basics';data.widget.required=['audience','mood'];
  const h=host();h.show(data);
  assert.equal(el(h,'widget-submit').textContent,'Continue');
  choose(h);assert.equal(el(h,'widget-submit').disabled,true);
  await submit(h);assert.equal(h.calls.length,0,'required unanswered questions stay local');
  choose(h,'mood','calm');assert.equal(el(h,'widget-submit').disabled,false);
  await submit(h);assert.equal(h.calls.length,1);
}
{
  const data=brief();data.widget.purpose='excerpt_review';data.widget.required=['audience'];
  const intake={version:1,mode:'hands_on',phase:'production',excerpt_review:{status:'approved',object_id:'sample-one'},next_action:'Complete the rest'};
  const h=host({tool:async input=>({structuredContent:{...data,saved:true,intake,widget:{...data.widget,answers:input.arguments.answers,revision:2},creative:{revision:4,intake}}})});
  h.show(data);assert.equal(el(h,'widget-submit').textContent,'Send decision');choose(h);await submit(h);
  assert.equal(h.messages.length,1);
  assert(!JSON.stringify(h.messages).includes('sample-one'));
  assert(!JSON.stringify(h.messages).includes('Complete the rest'));
  assert(JSON.stringify(h.contexts).includes('sample-one'));
  assert(JSON.stringify(h.contexts).includes('Complete the rest'));
  assert(JSON.stringify(h.contexts).includes('approved'),'host receives the saved sample decision');
}
