import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync('card.html','utf8');
new vm.Script(html.match(/<script>([\s\S]*)<\/script>/)[1]);
const {document}=parseHTML(fs.readFileSync('template.html','utf8'));
let app,calls=[],pending,fail=false;
class App {
 constructor(){app=this}
 async connect(){}
 getHostContext(){return {theme:'light'}}
 async callServerTool(input){calls.push(input);if(fail)throw Error('offline');return {structuredContent:structuredClone(pending)}}
 async openLink(input){calls.push(input)}
}
const source=fs.readFileSync('app.js','utf8').replace(/^import[\s\S]*?from ["']@modelcontextprotocol\/ext-apps["'];\n/,'');
const context={document,App,applyDocumentTheme(){},applyHostStyleVariables(){},console,setTimeout(){return 1},clearTimeout(){},Date};
vm.runInNewContext(source,context);
const flush=()=>new Promise(r=>setTimeout(r,10));
pending={id:'p',title:'<img src=x onerror=alert(1)>',workspace_url:'https://studio.test/?project=p',next_action:'Render motion',stage:'style',tasks:[],revisions:[],updates:[{id:'first',stage:'style',at:new Date().toISOString(),note:'Cream title',preview:{url:'https://media.test/style.png',media_type:'image/png'}}]};
app.ontoolresult({structuredContent:structuredClone(pending)});await flush();
assert.equal(document.querySelector('h1 img'),null);
assert.equal(document.querySelector('#media img').getAttribute('src'),'https://media.test/style.png');
assert.equal(calls[0].name,'video_project_updates');
pending.updates.push({id:'second',stage:'motion',at:new Date().toISOString(),note:'First motion',preview:{url:'https://media.test/draft.mp4',media_type:'video/mp4'}});
await document.getElementById('refresh').onclick();await flush();
const video=document.querySelector('video');assert(video);assert.equal(video.src,'https://media.test/draft.mp4');
app.ontoolresult({structuredContent:structuredClone(pending)});await flush();assert.equal(document.querySelector('video'),video,'polling must not restart playback');
document.querySelector('#history button').onclick();assert(document.querySelector('#media img'),'earlier preview remains selectable');
fail=true;await document.getElementById('refresh').onclick();await flush();assert.match(document.getElementById('notice').textContent,/Unable to refresh/);
await app.onteardown();console.log('PASS: compiled bundle syntax, safe text, image and video updates, app-only polling, stable playback, revision selection, reconnect error');
