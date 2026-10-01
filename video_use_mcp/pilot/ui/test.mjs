import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync('card.html','utf8');
new vm.Script(html.match(/<script>([\s\S]*)<\/script>/)[1]);
const {document}=parseHTML(fs.readFileSync('template.html','utf8'));
let app,calls=[],requests=[];
let fetch=async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({source:{name:options.headers["X-Filename"]}})}};
class App {constructor(){app=this} async connect(){} async openLink(input){calls.push(input)} getHostCapabilities(){return {serverTools:{},updateModelContext:{text:{}},message:{text:{}}}} async callServerTool(input){calls.push(input);return {structuredContent:{creative:{revision:3,choice_revision:2}}}} async updateModelContext(input){calls.push({context:input})} async sendMessage(input){calls.push({message:input});return {}}}
const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,'');
vm.runInNewContext(source,{document,App,applyDocumentTheme(){},console,fetch});
assert.equal(document.getElementById('visual').hidden,true,'no setup or placeholder UI');
assert.equal(document.querySelector('header'),null);
assert.equal(document.querySelector('h1'),null);
let media={object_id:'frame',url:'https://media.test/frame.png',caption:'<img src=x onerror=alert(1)>',media_type:'image/png'};
app.ontoolresult({structuredContent:{media}});
assert.equal(document.querySelectorAll('img').length,1);
assert.equal(document.querySelector('img').alt,media.caption);
assert.equal(document.getElementById('download').hidden,true);
media={object_id:'final',url:'https://media.test/video.mp4?ticket=x',download_url:'https://media.test/video.mp4?ticket=x&download=true',media_type:'video/mp4'};
app.ontoolresult({structuredContent:{media}});
const video=document.querySelector('video');assert(video);assert.equal(video.controls,true);
app.ontoolresult({structuredContent:{media}});assert.equal(document.querySelector('video'),video,'do not reset playback');
assert.equal(document.getElementById('download').hidden,false);
await document.getElementById('download').onclick();assert.equal(calls[0].url,media.download_url);
assert.equal(calls.length,1,'no background tool calls');
await app.onteardown();console.log('PASS media-only view no placeholders no polling image video download and stable playback');

const options=[{id:'diagram',label:'Diagrams',description:'A visual explanation',url:'https://media.test/a.mp4'},{id:'editorial',label:'Editorial',description:'Motion story',url:'https://media.test/b.mp4'}];
app.ontoolresult({structuredContent:{project_id:'p',choices:{question:'Which style?',revision:1,options}}});
assert.equal(document.getElementById('choices').hidden,false);
assert.equal(calls.length,1,'displaying choices never sends messages');
await document.querySelector('#options button').onclick();
assert.equal(calls[1].name,'choose_video_style');
assert.deepEqual(JSON.parse(JSON.stringify(calls[1].arguments)),{project_id:'p',choice:'diagram',revision:1});
assert.equal(document.querySelector('#options button').getAttribute('aria-pressed'),'true');
assert(calls[2].context && calls[3].message);
assert.equal(document.querySelector('#options button').disabled,false);
app.getHostCapabilities=()=>({});
await document.querySelector('#options button').onclick();
assert.equal(calls.length,4,'unsupported host uses conversational fallback');
assert(document.getElementById('notice').textContent.includes('Tell Claude'));
console.log('PASS optional choices persist only on click and respect host capabilities');

app.getHostCapabilities=()=>({serverTools:{},updateModelContext:{text:{}},message:{text:{}}});
app.ontoolresult({structuredContent:{project_id:'p',source_picker:{accept:'.pdf,.mp4',max_bytes:200000000,studio_url:'https://studio.test/?project=p'}},_meta:{source_upload_url:'https://api.test/source-upload/p',source_upload_token:'scoped-test-token'}});
assert.equal(document.getElementById('sources').hidden,false);
assert.equal(document.getElementById('visual').hidden,true);
const fileInput=document.getElementById('source-files');
fileInput.files=[{name:'brief.pdf',size:30}];
await fileInput.onchange();
assert.equal(requests.length,1);
assert.equal(requests[0].options.credentials,'omit');
assert.equal(requests[0].options.headers['X-Upload-Token'],'scoped-test-token');
assert.equal(document.getElementById('source-status').textContent,'Added brief.pdf.');
assert(!JSON.stringify(calls).includes('scoped-test-token'),'upload capability never enters chat context');
fileInput.files=[{name:'large.mp4',size:200000001}];await fileInput.onchange();
assert.equal(requests.length,1,'oversized uploads rejected before transfer');
console.log('PASS explicit source upload stays outside model context and checks size');

// Isolated hosts exercise the optional ChatGPT bridge without a live account.
const chatCapabilities={serverTools:{},updateModelContext:{text:{}},message:{text:{}}};
function sourceHost({extension,capabilities=chatCapabilities,serverTool,upload}={}){
  const {document}=parseHTML(fs.readFileSync('template.html','utf8'));
  const calls=[],requests=[];
  let app;
  class TestApp {
    constructor(){app=this}
    async connect(){}
    getHostCapabilities(){return capabilities}
    async openLink(input){calls.push({open:input})}
    async callServerTool(input){calls.push({tool:input});return serverTool?serverTool(input):{structuredContent:{source:{name:input.arguments.name}}}}
    async updateModelContext(input){calls.push({context:input})}
    async sendMessage(input){calls.push({message:input});return {}}
  }
  const fetch=async(url,options)=>{
    requests.push({url,options});
    if(upload)return upload(url,options);
    return {ok:true,json:async()=>({source:{name:decodeURIComponent(options.headers['X-Filename'])}})};
  };
  const globals={document,App:TestApp,applyDocumentTheme(){},console,fetch};
  if(extension!==undefined)globals.window={openai:extension};
  vm.runInNewContext(source,globals);
  return {document,app,calls,requests};
}
function sourceResult(project='library-project'){
  return {
    structuredContent:{project_id:project,source_picker:{accept:'.pdf,.mp4',max_bytes:200000000,studio_url:`https://studio.test/?project=${project}`}},
    _meta:{source_upload_url:`https://api.test/source-upload/${project}`,source_upload_token:`secret-upload-${project}`},
  };
}
function conversationalCalls(host){return JSON.stringify(host.calls.filter(call=>call.context || call.message))}
function assertPrivateSourceDetails(host,...details){
  for(const detail of details)assert(!conversationalCalls(host).includes(detail),`${detail} must not enter model context or chat`);
}
function plain(value){return JSON.parse(JSON.stringify(value))}

for(const [label,extension,capabilities] of [
  ['no host bridge',undefined,chatCapabilities],
  ['empty bridge',{},chatCapabilities],
  ['missing download method',{async selectFiles(){throw Error('must not run')}},chatCapabilities],
  ['missing selection method',{async getFileDownloadUrl(){throw Error('must not run')}},chatCapabilities],
  ['no tool capability',{async selectFiles(){throw Error('must not run')},async getFileDownloadUrl(){throw Error('must not run')}},{}],
]){
  const host=sourceHost({extension,capabilities});
  host.app.ontoolresult(sourceResult());
  assert.equal(host.document.getElementById('source-library').hidden,true,label);
  assert.equal(host.document.getElementById('source-files').disabled,false,'local upload remains available');
  assert.equal(host.calls.length,0,'feature detection does not start requests or messages');
  await host.document.getElementById('source-fallback').onclick();
  assert.deepEqual(plain(host.calls),[{open:{url:'https://studio.test/?project=library-project'}}]);
}
console.log('PASS unsupported library hosts keep local upload and explicit website fallback');

{
  const bridgeCalls=[];
  const selected=[{fileId:'private-library-file-one',fileName:'shot.mp4'},{fileId:'private-library-file-two',fileName:'résumé 東京.pdf'}];
  const downloadUrls=selected.map((file,index)=>`https://files.test/private/${index}?sig=signed-secret-${index}&expires=9999`);
  const host=sourceHost({extension:{
    async selectFiles(){bridgeCalls.push({select:true});return selected},
    async getFileDownloadUrl(input){bridgeCalls.push({download:input});return {downloadUrl:downloadUrls[selected.findIndex(file=>file.fileId===input.fileId)]}},
  }});
  host.app.ontoolresult(sourceResult());
  const button=host.document.getElementById('source-library');
  assert.equal(button.hidden,false);
  assert.equal(bridgeCalls.length,0,'displaying the picker never opens the host library');
  await button.onclick();
  assert.deepEqual(plain(bridgeCalls),[{select:true},{download:{fileId:selected[0].fileId}},{download:{fileId:selected[1].fileId}}]);
  const imports=host.calls.filter(call=>call.tool);
  assert.deepEqual(plain(imports),selected.map((file,index)=>({tool:{name:'import_video_source',arguments:{project_id:'library-project',url:downloadUrls[index],name:file.fileName}}})));
  assert.equal(host.document.getElementById('source-status').textContent,'Added shot.mp4, résumé 東京.pdf.');
  assert.equal(button.disabled,false);
  assert.equal(host.requests.length,0,'library import passes the granted URL directly to the source tool');
  assert.equal(host.calls.filter(call=>call.context).length,1,'one completion context for the batch');
  assert.equal(host.calls.filter(call=>call.message).length,1,'one user message after explicit selection');
  assertPrivateSourceDetails(host,...downloadUrls,...selected.map(file=>file.fileId),'secret-upload-library-project');
}
console.log('PASS explicit ChatGPT library selection imports files and keeps grants out of chat');

{
  const host=sourceHost({extension:{async selectFiles(){return []},async getFileDownloadUrl(){throw Error('must not run')}}});
  host.app.ontoolresult(sourceResult());
  await host.document.getElementById('source-library').onclick();
  assert.equal(host.document.getElementById('source-status').textContent,'No files selected.');
  assert.equal(host.calls.length,0,'cancelled selection sends neither tools nor messages');
  assert.equal(host.document.getElementById('source-library').disabled,false);
}

{
  const host=sourceHost({
    extension:{async selectFiles(){return [{fileId:'private-file',fileName:'blocked.mp4'}]},async getFileDownloadUrl(){return {downloadUrl:'https://files.test/blocked?sig=private-signature'}}},
    serverTool:async()=>({isError:true,content:[{type:'text',text:'Source transfer failed. Try again.'}]}),
  });
  host.app.ontoolresult(sourceResult());
  await host.document.getElementById('source-library').onclick();
  assert.equal(host.document.getElementById('source-status').textContent,'Source transfer failed. Try again.');
  assert.equal(host.calls.filter(call=>call.context || call.message).length,0,'failed imports never claim a source was added');
  assert.equal(host.document.getElementById('source-library').disabled,false);
}
console.log('PASS cancelled and failed library transfers do not report false completion');

{
  const host=sourceHost();
  host.app.ontoolresult(sourceResult());
  const input=host.document.getElementById('source-files');
  const filename='résumé 東京.pdf';
  input.files=[{name:filename,size:30}];
  await input.onchange();
  const headers=host.requests[0].options.headers;
  assert.equal(headers['X-Filename'],encodeURIComponent(filename));
  assert(/^[\x20-\x7e]+$/.test(headers['X-Filename']),'HTTP upload headers remain ASCII');
  assert.equal(decodeURIComponent(headers['X-Filename']),filename,'one decode preserves Unicode and spaces');
  assert.equal(host.document.getElementById('source-status').textContent,`Added ${filename}.`);
  assert(conversationalCalls(host).includes(filename),'model sees the human filename');
  assert(!conversationalCalls(host).includes(encodeURIComponent(filename)),'model does not see header transport encoding');
  assertPrivateSourceDetails(host,'secret-upload-library-project');
}
console.log('PASS Unicode filenames use ASCII percent-encoded headers and readable completion text');

{
  const host=sourceHost({upload:async(_url,options)=>({ok:true,json:async()=>({source:{name:decodeURIComponent(options.headers['X-Filename']).normalize('NFC')}})})});
  host.app.ontoolresult(sourceResult());
  const filename='re\u0301sume\u0301 東京.pdf';
  const input=host.document.getElementById('source-files');input.files=[{name:filename,size:30}];
  await input.onchange();
  assert.equal(decodeURIComponent(host.requests[0].options.headers['X-Filename']),filename,'transport preserves decomposed filenames');
  assert.equal(host.document.getElementById('source-status').textContent,`Added ${filename.normalize('NFC')}.`,'display uses the server-normalized filename');
  assert(conversationalCalls(host).includes(filename.normalize('NFC')));
}

function deferred(){let resolve;const promise=new Promise(done=>{resolve=done});return {promise,resolve}}
{
  const firstResponse=deferred();
  let uploads=0;
  const host=sourceHost({upload:async(_url,options)=>{
    if(++uploads===1)await firstResponse.promise;
    return {ok:true,json:async()=>({source:{name:decodeURIComponent(options.headers['X-Filename'])}})};
  }});
  host.app.ontoolresult(sourceResult('original-project'));
  const input=host.document.getElementById('source-files');
  input.files=[{name:'one.pdf',size:10},{name:'two.pdf',size:10}];
  const pending=input.onchange();
  assert.equal(host.requests.length,1);
  host.app.ontoolresult(sourceResult('new-project'));
  const latestStatus=host.document.getElementById('source-status').textContent;
  firstResponse.resolve();
  await pending;
  assert.equal(host.requests.length,2);
  for(const request of host.requests){
    assert.equal(request.url,'https://api.test/source-upload/original-project','every file uses the captured destination');
    assert.equal(request.options.headers['X-Upload-Token'],'secret-upload-original-project');
  }
  assert.equal(host.document.getElementById('source-status').textContent,latestStatus,'previous upload does not overwrite the new project status');
  assert(conversationalCalls(host).includes('video project original-project'));
  assert(!conversationalCalls(host).includes('new-project'));
  assertPrivateSourceDetails(host,'secret-upload-original-project','secret-upload-new-project');
}

{
  const enteredImport=deferred(),continueImport=deferred();
  let selections=0,imports=0;
  const host=sourceHost({
    extension:{
      async selectFiles(){selections++;return [{fileId:'one',fileName:'one.mp4'},{fileId:'two',fileName:'two.mp4'}]},
      async getFileDownloadUrl({fileId}){return {downloadUrl:`https://files.test/${fileId}?sig=library-grant-${fileId}`}},
    },
    serverTool:async(input)=>{
      if(++imports===1){enteredImport.resolve();await continueImport.promise}
      return {structuredContent:{source:{name:input.arguments.name}}};
    },
  });
  host.app.ontoolresult(sourceResult('original-project'));
  const button=host.document.getElementById('source-library');
  const pending=button.onclick();
  await enteredImport.promise;
  assert.equal(button.disabled,true);
  await button.onclick();
  assert.equal(selections,1,'concurrent clicks cannot duplicate imports');
  host.app.ontoolresult(sourceResult('new-project'));
  const latestStatus=host.document.getElementById('source-status').textContent;
  continueImport.resolve();
  await pending;
  assert.equal(imports,2);
  for(const call of host.calls.filter(call=>call.tool))assert.equal(call.tool.arguments.project_id,'original-project');
  assert.equal(host.document.getElementById('source-status').textContent,latestStatus);
  assert(conversationalCalls(host).includes('video project original-project'));
  assert(!conversationalCalls(host).includes('new-project'));
  assertPrivateSourceDetails(host,'library-grant-one','library-grant-two','secret-upload-original-project');
}
console.log('PASS uploads and library batches stay on their original project across new tool results');

{
  let imports=0;
  const host=sourceHost({
    extension:{async selectFiles(){return [{fileId:'one',fileName:'saved.mp4'},{fileId:'two',fileName:'failed.mp4'}]},async getFileDownloadUrl({fileId}){return {downloadUrl:`https://files.test/${fileId}?sig=private-grant`}}},
    serverTool:async()=>++imports===1?{structuredContent:{source:{name:'saved.mp4'}}}:{isError:true,content:[{type:'text',text:'Transfer timed out.'}]},
  });
  host.app.ontoolresult(sourceResult());
  await host.document.getElementById('source-library').onclick();
  assert.equal(host.document.getElementById('source-status').textContent,'Added saved.mp4. Transfer timed out.');
  assert(conversationalCalls(host).includes('saved.mp4'));
  assert(!conversationalCalls(host).includes('failed.mp4'),'partial failure only announces the successful transfer');
  assertPrivateSourceDetails(host,'private-grant');
}

{
  const host=sourceHost();
  const result=sourceResult();delete result._meta;
  host.app.ontoolresult(result);
  const input=host.document.getElementById('source-files');input.files=[{name:'brief.pdf',size:30}];
  await input.onchange();
  assert.equal(host.requests.length,0,'missing upload access does not attempt an unauthenticated transfer');
  assert.equal(host.calls.length,0);
  assert(host.document.getElementById('source-status').textContent.includes('Use the upload page'));
}
console.log('PASS partial imports and missing upload grants provide truthful recovery');

{
  const firstChoice=deferred();
  let choicesSaved=0;
  const host=sourceHost({serverTool:async()=>{
    if(++choicesSaved===1)await firstChoice.promise;
    return {structuredContent:{creative:{revision:10,choice_revision:9}}};
  }});
  host.app.ontoolresult({structuredContent:{project_id:'first-choice-project',choices:{question:'First choice?',revision:1,options}}});
  const pending=host.document.querySelector('#options button').onclick();
  host.app.ontoolresult({structuredContent:{project_id:'second-choice-project',choices:{question:'Second choice?',revision:4,options}}});
  firstChoice.resolve();await pending;
  assert.equal(host.document.getElementById('question').textContent,'Second choice?');
  assert.equal(host.document.querySelector('#options button').getAttribute('aria-pressed'),'false','new project choice remains untouched');
  assert.equal(host.document.getElementById('notice').textContent,'','previous choice completion does not claim the new choice was saved');
  assert(conversationalCalls(host).includes('video project first-choice-project'));
  assert(!conversationalCalls(host).includes('second-choice-project'));
  await host.document.querySelector('#options button').onclick();
  assert.deepEqual(plain(host.calls.filter(call=>call.tool).map(call=>call.tool.arguments)),[
    {project_id:'first-choice-project',choice:'diagram',revision:1},
    {project_id:'second-choice-project',choice:'diagram',revision:4},
  ]);
}
console.log('PASS style selection snapshots its project and revision across new choices');
