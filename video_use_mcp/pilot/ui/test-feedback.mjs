// Creative feedback belongs in the host chat; the media surface stays minimal.
import {parseHTML} from 'linkedom';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source=fs.readFileSync('app.js','utf8').replace(/^import[^\n]*\n/,'');
const template=fs.readFileSync('template.html','utf8');
const result=(object='video-one',project='project',extra={})=>({structuredContent:{project_id:project,media:{object_id:object,media_type:'video/mp4',url:`https://private.test/${object}?ticket=expired-token`,download_url:`https://private.test/${object}?ticket=expired-token&download=true`,final:true,...extra}}});
function host({tool,capabilities={serverTools:{},openLinks:{}},widgets,context}={}){
  const {document}=parseHTML(template),calls=[],messages=[],links=[],listeners={};let app;
  class App{
    constructor(){app=this}async connect(){}
    getHostCapabilities(){return capabilities}
    getHostContext(){return context}
    async callServerTool(input){calls.push(input);return tool?tool(input):result(input.arguments.object_id,input.arguments.project_id,{url:'https://private.test/fresh?ticket=new',download_url:'https://private.test/fresh?ticket=new&download=true'})}
    async updateModelContext(input){messages.push(input)}async sendMessage(input){messages.push(input)}
    async openLink(input){links.push(input)}
  }
  vm.runInNewContext(source,{document,App,applyDocumentTheme(){},console,URL,setTimeout(){return 1},clearTimeout(){},twttr:widgets?{widgets}:undefined,addEventListener(name,fn){listeners[name]=fn}});
  return {document,app,calls,messages,links,emit(name,event){listeners[name]?.(event)}};
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
  assert.equal(h.links.length,1,'the original pinned download completes despite an unrelated notification');
  assert(h.links[0].url.includes('/video-one?'),'late renewals never open a different project');
  assert.equal(h.document.querySelector('video'),old,'unrelated project results cannot replace a pinned card');
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

const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
{
  const made=[];
  const h=host({widgets:{async createTweet(id,element,options){made.push({id,element,options});const frame=h.document.createElement('iframe');frame.src='https://platform.twitter.com/embed/Tweet.html?id='+id;element.append(frame);return frame;}}});
  const media={media_type:'social/x',post_id:'463440424141459456',source_url:'https://x.com/Interior/status/463440424141459456',title:'The source post',caption:'Source post',html:'<script>ignore me</script>'};
  h.app.ontoolresult({structuredContent:{project_id:'project',follow_project:false,media}});await flush();
  assert.equal(made.length,1);assert.equal(made[0].id,media.post_id);assert.equal(made[0].options.dnt,true);
  assert(h.document.querySelector('.social-post iframe'));
  assert.equal(h.document.querySelector('#media script'),null,'oEmbed HTML is never injected');
  assert.equal(h.document.getElementById('download').hidden,true);assert.equal(h.calls.length,0);assert.equal(h.messages.length,0);
}
{
  const h=host();
  h.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media:{media_type:'social/x',post_id:'463440424141459456',source_url:'https://x.com/Interior/status/463440424141459456'}}});
  const script=h.document.querySelector('head script[src]');assert.equal(script.src,'https://platform.twitter.com/widgets.js');
  script.onerror();await flush();
  assert(h.document.getElementById('notice').textContent.includes('Open the source'));
  assert.equal(h.document.getElementById('source-reference').hidden,false);
}
{
  let called=false;const h=host({widgets:{createTweet(){called=true;}}});
  h.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media:{media_type:'social/x',post_id:'<script>',source_url:'https://x.com'}}});await flush();
  assert.equal(called,false);assert.equal(h.document.querySelector('head script[src]'),null);
}
{
  const h=host();h.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media:{media_type:'text/html',provider:'tiktok',embed_url:'https://www.tiktok.com/player/v1/6718335390845095173',source_url:'https://www.tiktok.com/@scout2015/video/6718335390845095173'}}});
  const frame=h.document.querySelector('iframe');assert.equal(frame.getAttribute('data-provider'),'tiktok');assert(frame.getAttribute('allow').includes('fullscreen'));
}
console.log('PASS official X factory receives only a post ID and TikTok uses its provider player with honest failure links');

for(const provider of ['youtube','tiktok','vimeo']){
  const h=host();
  const media={media_type:'text/html',provider,embed_url:`https://source.test/embed/${provider}`,source_url:`https://source.test/${provider}`,description:'A clear visual comparison for the requested explainer.',attribution:'Example creator · 12,345 observed views',evidence_status:'Metadata only · visuals and motion not inspected'};
  h.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media}});
  for(const [id,field] of [['reference-description','description'],['reference-attribution','attribution'],['reference-evidence','evidence_status']]){
    assert.equal(h.document.getElementById(id).textContent,media[field]);
    assert.equal(h.document.getElementById(id).hidden,false);
  }
  assert(h.document.getElementById('source-playback-hint').textContent.includes('If playback'));
  assert.equal(h.document.querySelectorAll('#visual button').length,0);
  const frame=h.document.querySelector('iframe');
  h.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media:{...media,description:'<img src=x onerror=alert(1)>',attribution:null,evidence_status:undefined}}});
  assert.equal(h.document.querySelector('iframe'),frame,'metadata changes preserve the loaded iframe');
  assert.equal(h.document.getElementById('reference-description').textContent,'<img src=x onerror=alert(1)>');
  assert.equal(h.document.getElementById('reference-description').children.length,0,'source descriptions are plain text');
  for(const id of ['reference-attribution','reference-evidence']){
    assert.equal(h.document.getElementById(id).hidden,true);assert.equal(h.document.getElementById(id).textContent,'');
  }
  h.app.ontoolresult(result('sample','p',{final:false,description:'Must not leak into project media'}));
  for(const id of ['reference-description','reference-attribution','reference-evidence','source-playback-hint']){
    assert.equal(h.document.getElementById(id).hidden,true);assert.equal(h.document.getElementById(id).textContent,'');
  }
}
{
  const h=host();
  const media={media_type:'text/html',provider:'tiktok',embed_url:'https://www.tiktok.com/player/v1/6718335390845095173',source_url:'https://www.tiktok.com/@scout2015/video/6718335390845095173'};
  h.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media}});
  const frame=h.document.querySelector('iframe');frame.contentWindow={};
  const event={origin:'https://www.tiktok.com',source:frame.contentWindow,data:{'x-tiktok-player':true,type:'onPlayerError',value:{errorCode:3001,errorType:'PLAYBACK_ERROR'}}};
  const hint=h.document.getElementById('source-playback-hint'),neutral=hint.textContent;
  for(const invalid of [{...event,source:{}},{...event,origin:'https://www.tiktok.com.attacker.test'}, {...event,data:{...event.data,'x-tiktok-player':false}}, {...event,data:{...event.data,value:{errorCode:3002,errorType:'AUTOPLAY_ERROR'}}}, {...event,data:{'x-tiktok-player':true,type:'onPlayerReady'}}]){
    h.emit('message',invalid);assert.equal(hint.textContent,neutral,'only a current authenticated playback error changes the message');
  }
  h.emit('message',event);assert(hint.textContent.includes('TikTok reported'));
  assert.equal(h.document.querySelector('iframe'),frame,'an error preserves provider controls and the source link');
  h.emit('message',{...event,data:{'x-tiktok-player':true,type:'onStateChange',value:1}});assert(hint.hidden);
  h.app.ontoolresult(result('final','p'));
  h.emit('message',event);assert(hint.hidden);assert.equal(hint.textContent,'','old frame messages cannot affect a new player');
  const nextHost=host();nextHost.app.ontoolresult({structuredContent:{project_id:'p',follow_project:false,media}});
  const latest=nextHost.document.querySelector('iframe');latest.contentWindow={};
  await nextHost.app.onteardown();nextHost.emit('message',{...event,source:latest.contentWindow});
  assert(nextHost.document.getElementById('source-playback-hint').textContent.includes('If playback'),'teardown ignores provider messages');
}
console.log('PASS every reference has safe plain descriptions with stale-text clearing and authenticated TikTok playback failures');

const youtubeReference={structuredContent:{project_id:'p',follow_project:false,media:{media_type:'text/html',provider:'youtube',embed_url:'https://www.youtube-nocookie.com/embed/9O7Az0qgtuQ?rel=0',source_url:'https://www.youtube.com/watch?v=9O7Az0qgtuQ',title:'The reference',description:'A familiar approach with a clear visual sequence.'}}};
function cspViolation(h,fields={}){
  const event=new h.document.defaultView.Event('securitypolicyviolation');
  Object.defineProperty(event,'isTrusted',{value:true});
  Object.assign(event,{disposition:'enforce',effectiveDirective:'frame-src',blockedURI:'https://www.youtube-nocookie.com',...fields});
  h.document.dispatchEvent(event);
}
{
  const h=host({capabilities:{updateModelContext:{text:{}}}});h.app.ontoolresult(youtubeReference);
  for(const fields of [{disposition:'report'}, {effectiveDirective:'script-src'}, {blockedURI:'https://unrelated.test'}, {blockedURI:'https://www.youtube-nocookie.com/embed/different'}]){
    cspViolation(h,fields);assert.equal(h.document.getElementById('media').hidden,false,'unrelated or report-only CSP does not hide an embed');
  }
  cspViolation(h);
  assert(h.document.getElementById('media').hidden,'a real enforced block collapses the broken frame');
  assert(h.document.getElementById('source-playback-hint').textContent.includes('This chat blocked'));
  assert.equal(h.document.getElementById('reference-description').textContent,youtubeReference.structuredContent.media.description);
  assert.equal(h.document.getElementById('source-reference').hidden,false);
  assert.equal(h.messages.length,1);assert(h.messages[0].content[0].text.includes('playback was not verified'));
  cspViolation(h);assert.equal(h.messages.length,1,'the same block is not repeatedly added to model context');
  h.app.ontoolresult(youtubeReference);assert(h.document.getElementById('source-playback-hint').textContent.includes('This chat blocked'),'a duplicate result retains the verified blocked state');
  h.app.ontoolresult(result());cspViolation(h);
  assert.equal(h.document.getElementById('media').hidden,false);assert(h.document.getElementById('source-playback-hint').hidden);
}
for(const config of [{context:{csp:{frameDomains:[]}}},{capabilities:{sandbox:{csp:{frameDomains:['https://www.tiktok.com']}}}}]){
  const h=host(config);h.app.ontoolresult(youtubeReference);
  assert.equal(h.document.querySelector('iframe').getAttribute('src'),null,'a host-declared denial avoids attempting the iframe request');
  assert(h.document.getElementById('media').hidden);
  assert(h.document.getElementById('source-playback-hint').textContent.includes('This chat blocked'));
}
for(const config of [{}, {context:{csp:{}}}, {capabilities:{sandbox:{csp:{}}}}, {context:{csp:{frameDomains:['https://www.youtube-nocookie.com']}}}, {context:{csp:{frameDomains:['https://*.youtube-nocookie.com']}}}]){
  const h=host(config);h.app.ontoolresult(youtubeReference);
  assert(h.document.querySelector('iframe').src.includes('/embed/9O7Az0qgtuQ'),'missing host information or matching explicit permission preserves playback');
  assert.equal(h.document.getElementById('media').hidden,false);
  assert.equal(h.messages.length,0);
}
{
  const h=host();h.app.ontoolresult(youtubeReference);
  h.app.onhostcontextchanged({csp:{frameDomains:[]}});
  assert(h.document.getElementById('media').hidden,'an explicit host permission update is respected');
}
console.log('PASS enforced iframe CSP failures collapse the broken player but preserve reference descriptions and links');

const xReference={structuredContent:{project_id:'p',follow_project:false,media:{media_type:'social/x',post_id:'463440424141459456',source_url:'https://x.com/Interior/status/463440424141459456',description:'A specific visual approach from the source post.'}}};
for(const origin of ['https://platform.twitter.com','https://platform.x.com']){
  const h=host({widgets:{async createTweet(id,element){
    const frame=h.document.createElement('iframe');frame.src=`${origin}/embed/Tweet.html?id=${id}`;element.append(frame);return frame;
  }}});
  h.app.ontoolresult(xReference);await flush();
  const container=h.document.querySelector('.social-post');
  const unrelated=h.document.createElement('iframe');unrelated.src='https://unrelated.test/frame';container.append(unrelated);
  cspViolation(h,{blockedURI:'https://unrelated.test'});assert.equal(h.document.getElementById('media').hidden,false,'an unrelated descendant cannot identify an X player failure');
  cspViolation(h,{blockedURI:origin,effectiveDirective:'child-src'});
  assert(h.document.getElementById('media').hidden,'an official current X descendant iframe is covered by CSP recovery');
  assert.equal(h.document.getElementById('reference-description').textContent,xReference.structuredContent.media.description);
  assert.equal(h.document.getElementById('source-reference').hidden,false);
  h.app.ontoolresult(xReference);assert(h.document.getElementById('source-playback-hint').textContent.includes('This chat blocked'),'X retains a proven failure on duplicate results');
  h.app.ontoolresult(result());cspViolation(h,{blockedURI:origin});
  assert.equal(h.document.getElementById('media').hidden,false);assert(h.document.getElementById('source-playback-hint').hidden,'an old X frame does not alter new project media');
}
{
  const h=host({context:{csp:{frameDomains:[]}},widgets:{async createTweet(id,element){
    const frame=h.document.createElement('iframe');frame.src=`https://platform.twitter.com/embed/Tweet.html?id=${id}`;element.append(frame);return frame;
  }}});
  h.app.ontoolresult(xReference);await flush();
  assert(h.document.getElementById('media').hidden,'explicit X permission is checked after the official factory reveals its frame origin');
  assert(h.document.getElementById('source-playback-hint').textContent.includes('This chat blocked'));
}
{
  let finish,oldFrame;
  const h=host({context:{csp:{frameDomains:[]}},widgets:{createTweet(id,element){
    oldFrame=h.document.createElement('iframe');oldFrame.src=`https://platform.twitter.com/embed/Tweet.html?id=${id}`;element.append(oldFrame);
    return new Promise(resolve=>{finish=resolve});
  }}});
  h.app.ontoolresult(xReference);await flush();h.app.ontoolresult(result());finish(oldFrame);await flush();
  assert.equal(h.document.getElementById('media').hidden,false,'a stale X factory result cannot hide another player');
  assert(h.document.getElementById('source-playback-hint').hidden);
  assert.equal(h.document.getElementById('notice').textContent,'');
}
console.log('PASS X descendant iframe CSP detection validates official origins and preserves current-player race guards');

const withPoster=(extra={})=>({structuredContent:{...youtubeReference.structuredContent,media:{...youtubeReference.structuredContent.media,poster_url:'https://i.ytimg.com/vi/9O7Az0qgtuQ/hqdefault.jpg',attribution:'Source creator · observed engagement unavailable',...extra}}});
{
  const h=host();h.app.ontoolresult(withPoster());
  assert.equal(h.document.querySelector('#reference-poster img'),null,'a working or untested provider iframe is not replaced by a thumbnail');
  const frame=h.document.querySelector('iframe');cspViolation(h);
  const link=h.document.getElementById('reference-poster'),image=link.querySelector('img');
  assert(image);assert(link.hidden,'the poster does not occupy a blank container while its image is loading');
  assert.equal(h.document.querySelector('iframe'),frame,'the CSP state stays tied to the original iframe');
  image.onload();assert.equal(link.hidden,false);assert(h.document.getElementById('media').hidden);
  assert.equal(h.document.getElementById('media-status').textContent,'Video thumbnail');
  assert.equal(link.querySelector('span').textContent,'Watch on YouTube ↗');
  assert(link.getAttribute('aria-label').includes('opens YouTube'));
  assert.equal(h.document.getElementById('reference-description').textContent,youtubeReference.structuredContent.media.description);
  assert.equal(h.document.getElementById('reference-attribution').textContent,'Source creator · observed engagement unavailable');
  assert(h.document.getElementById('source-playback-hint').textContent.includes('This chat blocked'));
  let prevented=false;await link.onclick({preventDefault(){prevented=true}});
  assert(prevented);assert.equal(h.links[0].url,youtubeReference.structuredContent.media.source_url);
  assert.equal(h.messages.length,0,'opening the exact source is not a chat message or generation request');
  h.app.ontoolresult(withPoster());assert.equal(link.querySelector('img'),image,'duplicate results preserve a loaded poster');assert.equal(link.hidden,false);
  assert.equal(h.document.getElementById('media-status').textContent,'Video thumbnail','duplicate results retain the honest thumbnail label');
  h.app.ontoolresult(youtubeReference);assert(link.hidden);assert.equal(link.children.length,0,'removing poster data clears the old thumbnail');
}
{
  const h=host({context:{csp:{frameDomains:[]}}});h.app.ontoolresult(withPoster());
  const image=h.document.querySelector('#reference-poster img');assert(image);image.onload();
  assert.equal(h.document.getElementById('reference-poster').hidden,false,'explicit host denial has the same source thumbnail fallback');
  assert.equal(h.document.querySelector('iframe').getAttribute('src'),null);
}
{
  const h=host({capabilities:{}});h.app.ontoolresult(withPoster({media_type:'source_link',embed_url:undefined}));
  assert.equal(h.document.querySelector('iframe'),null);
  const link=h.document.getElementById('reference-poster');link.querySelector('img').onload();assert.equal(link.hidden,false);
  let prevented=false;await link.onclick({preventDefault(){prevented=true}});
  assert.equal(prevented,false,'without the host link API the ordinary target blank anchor remains active');
  assert.equal(link.href,youtubeReference.structuredContent.media.source_url);assert.equal(link.target,'_blank');
  assert.equal(h.links.length,0);assert.equal(h.messages.length,0);
  assert(h.document.getElementById('source-playback-hint').hidden,'a nonembeddable provider result is not mislabeled as a proven host block');
}
{
  const h=host();h.app.ontoolresult(withPoster());cspViolation(h);
  const link=h.document.getElementById('reference-poster'),image=link.querySelector('img');image.onerror();
  assert(link.hidden);assert.equal(link.children.length,0,'a failed thumbnail leaves no broken image box');
  assert.equal(h.document.getElementById('source-reference').hidden,false);assert(h.document.getElementById('reference-description').textContent);
  h.app.ontoolresult(withPoster());assert.equal(link.children.length,0,'repeated tool results do not create an automatic failed-image retry loop');
}
{
  const h=host();h.app.ontoolresult(withPoster());cspViolation(h);
  const link=h.document.getElementById('reference-poster'),old=link.querySelector('img'),lateLoad=old.onload,lateError=old.onerror;
  h.app.ontoolresult(withPoster({media_type:'source_link',embed_url:undefined,source_url:'https://www.youtube.com/watch?v=jk6sz25OZgw',poster_url:'https://i.ytimg.com/vi/jk6sz25OZgw/hqdefault.jpg'}));
  const current=link.querySelector('img');assert.notEqual(current,old);lateLoad();lateError();
  assert(link.hidden,'an old poster completion cannot reveal a new loading image');assert.equal(link.querySelector('img'),current);
  current.onload();assert.equal(link.hidden,false);
  const finalLateLoad=current.onload,finalLateError=current.onerror;
  h.app.ontoolresult(result('final','p'));finalLateLoad();finalLateError();
  assert(link.hidden);assert.equal(link.children.length,0);assert.equal(link.getAttribute('href'),null);
  assert.equal(h.document.getElementById('media').hidden,false);assert(h.document.querySelector('video'));
}
for(const extra of [
  {poster_url:'https://i.ytimg.com/vi/jk6sz25OZgw/hqdefault.jpg'},
  {poster_url:'https://i.ytimg.com.attacker.test/vi/9O7Az0qgtuQ/hqdefault.jpg'},
  {poster_url:'https://attacker@i.ytimg.com/vi/9O7Az0qgtuQ/hqdefault.jpg'},
  {poster_url:'http://i.ytimg.com/vi/9O7Az0qgtuQ/hqdefault.jpg'},
  {poster_url:'https://i.ytimg.com/vi/9O7Az0qgtuQ/other.svg'},
  {poster_url:'https://i.ytimg.com/vi_webp/9O7Az0qgtuQ/hqdefault.jpg'},
  {poster_url:'https://i.ytimg.com:8443/vi/9O7Az0qgtuQ/hqdefault.jpg'},
  {provider:'tiktok'},
  {source_url:'https://youtube.com.attacker.test/watch?v=9O7Az0qgtuQ'},
]){
  const h=host();h.app.ontoolresult(withPoster({media_type:'source_link',embed_url:undefined,...extra}));
  assert.equal(h.document.querySelector('#reference-poster img'),null,'untrusted or mismatched thumbnails are not requested');
  assert(h.document.getElementById('reference-poster').hidden);
}
console.log('PASS blocked YouTube embeds retain exact-source clickable thumbnails with honest labels and image failure race guards');

const imageBytes='data:image/jpeg;base64,/9j/4A==';
function withInlinePoster(changes={}){
  const result=withPoster();
  result._meta={reference_poster:{source_url:result.structuredContent.media.poster_url,post_id:'9O7Az0qgtuQ',data_uri:imageBytes,...changes}};
  return result;
}
{
  const h=host(),payload=withInlinePoster();h.app.ontoolresult(payload);
  assert.equal(h.document.querySelector('#reference-poster img'),null,'inline thumbnail bytes do not replace an allowed or untested iframe');
  cspViolation(h);
  const image=h.document.querySelector('#reference-poster img');assert.equal(image.src,imageBytes);
  assert(h.document.getElementById('reference-poster-status').textContent.includes('Loading'));
  image.onload();assert.equal(h.document.getElementById('reference-poster').hidden,false);
  assert.equal(h.document.getElementById('reference-poster-status').textContent,'');
  assert.equal(payload.structuredContent.media.inline_poster_data_uri,undefined,'private image data never enters the original structured content');
  await h.document.getElementById('reference-poster').onclick();assert.equal(h.links[0].url,youtubeReference.structuredContent.media.source_url);
  assert.equal(h.messages.length,0,'displaying an image and opening its source never posts chat messages');
  h.app.ontoolresult(result());assert(h.document.getElementById('reference-poster').hidden);
}
for(const changes of [
  {post_id:'jk6sz25OZgw'}, {source_url:'https://i.ytimg.com/vi/jk6sz25OZgw/hqdefault.jpg'},
  {data_uri:'data:image/svg+xml;base64,PHN2Zz4='}, {data_uri:'data:image/png;base64,AAAA'},
  {data_uri:'data:image/jpeg;base64,A==='}, {data_uri:'data:image/jpeg;base64,AAAA=='},
  {data_uri:'data:image/jpeg;base64,%%%'}, {data_uri:'https://attacker.test/image'},
  {data_uri:'data:image/jpeg;base64,'+Buffer.alloc(131073).toString('base64')},
]){
  const h=host({context:{csp:{frameDomains:[]}}});h.app.ontoolresult(withInlinePoster(changes));
  assert.equal(h.document.querySelector('#reference-poster img').src,withPoster().structuredContent.media.poster_url,'invalid private image payload falls back to the validated official image URL');
}
for(const type of ['jpeg','webp']){
  const data_uri=`data:image/${type};base64,`+Buffer.alloc(131072).toString('base64');
  const h=host({context:{csp:{frameDomains:[]}}});h.app.ontoolresult(withInlinePoster({data_uri}));
  assert.equal(h.document.querySelector('#reference-poster img').src,data_uri,'exactly 128 KiB remains supported');
}
{
  const h=host({context:{csp:{frameDomains:[]}}});h.app.ontoolresult(withPoster({inline_poster_data_uri:imageBytes}));
  assert.equal(h.document.querySelector('#reference-poster img').src,withPoster().structuredContent.media.poster_url,'image bytes must arrive in the verified private metadata slot');
}
{
  const h=host({capabilities:{updateModelContext:{text:{}}}});h.app.ontoolresult(withPoster());cspViolation(h);
  const image=h.document.querySelector('#reference-poster img'),failed=image.onerror;
  for(const fields of [{effectiveDirective:'img-src',disposition:'report',blockedURI:'https://i.ytimg.com'}, {effectiveDirective:'img-src',blockedURI:'https://unrelated.test'}, {effectiveDirective:'img-src',blockedURI:'https://i.ytimg.com/vi/jk6sz25OZgw/hqdefault.jpg'}]){
    cspViolation(h,fields);assert(h.document.getElementById('reference-poster-status').textContent.includes('Loading'),'report-only and unrelated image failures are ignored');
  }
  cspViolation(h,{effectiveDirective:'img-src',blockedURI:'https://i.ytimg.com'});
  assert(h.document.getElementById('reference-poster-status').textContent.includes('blocked the source thumbnail'));
  failed();assert(h.document.getElementById('reference-poster-status').textContent.includes('blocked the source thumbnail'),'a later generic load error preserves the known CSP cause');
  const reports=h.messages.filter(message=>message.content?.[0]?.text.startsWith('Reference thumbnail display:'));
  assert.equal(reports.length,1);assert(reports[0].content[0].text.includes('UI version 3.3.0'));
  assert(!JSON.stringify(reports).includes('base64'));
  h.app.ontoolresult(result());assert.equal(h.document.getElementById('reference-poster-status').textContent,'');
}
{
  const h=host({context:{csp:{frameDomains:[]}},capabilities:{updateModelContext:{text:{}}}});
  h.app.ontoolresult(withPoster());h.document.querySelector('#reference-poster img').onerror();
  assert(h.document.getElementById('reference-poster-status').textContent.includes('could not load'));
  const reports=h.messages.filter(message=>message.content?.[0]?.text.startsWith('Reference thumbnail display:'));
  assert.equal(reports.length,1);assert(reports[0].content[0].text.includes('cause is not established'));
  h.app.ontoolresult(withInlinePoster());const image=h.document.querySelector('#reference-poster img');
  assert.equal(image.src,imageBytes,'new verified inline bytes can recover a previously failed external poster');image.onload();
  assert.equal(h.document.getElementById('reference-poster').hidden,false);
}
for(const blockedURI of ['data','data:']){
  const h=host({context:{csp:{frameDomains:[]}}});h.app.ontoolresult(withInlinePoster());
  cspViolation(h,{effectiveDirective:'img-src',blockedURI});
  assert(h.document.getElementById('reference-poster-status').textContent.includes('blocked the source thumbnail'));
  assert(h.document.getElementById('reference-poster').hidden,'data image policy remains authoritative too');
}
console.log('PASS verified bounded private thumbnails render under image restrictions and failures report truthful deduplicated diagnostics');

for(const media_type of ['source_link','text/html','video/mp4','video/webm','social/x']){
  const h=host({context:{csp:{frameDomains:[]}}}),payload=withInlinePoster();
  Object.assign(payload.structuredContent.media,{reference_display:'thumbnail',media_type,url:'https://source.test/never-load.mp4',post_id:'463440424141459456',truncated:true,duration:5,source_duration:600});
  h.app.ontoolresult(payload);
  assert.equal(h.document.querySelector('#media video,#media iframe,#media img,.social-post,head script[src]'),null,'thumbnail mode never mounts or requests any source player');
  assert(h.document.getElementById('media').hidden);
  const link=h.document.getElementById('reference-poster'),image=link.querySelector('img');
  assert.equal(image.src,imageBytes,'verified thumbnail is requested immediately without an iframe failure');
  image.onload();assert.equal(link.hidden,false);
  assert.equal(h.document.getElementById('media-status').textContent,'Video thumbnail');
  assert.equal(h.document.getElementById('source-playback-hint').textContent,'');
  assert(h.document.getElementById('source-playback-hint').hidden);
  assert(h.document.getElementById('excerpt').hidden,'a thumbnail is not labeled as a playable source excerpt');
  assert(h.document.getElementById('download').hidden);
  assert.equal(h.document.getElementById('source-reference').textContent,payload.structuredContent.media.title);
  assert.equal(h.document.getElementById('reference-description').textContent,payload.structuredContent.media.description);
  assert.equal(h.document.querySelectorAll('#visual button').length,0);
  h.app.onhostcontextchanged({csp:{frameDomains:[]}});
  cspViolation(h);
  assert.equal(h.document.getElementById('source-playback-hint').textContent,'','host frame restrictions are irrelevant to thumbnail presentation');
  await link.onclick();assert.equal(h.links[0].url,payload.structuredContent.media.source_url);
  assert.equal(h.messages.length,0);assert.equal(h.calls.length,0);
}
{
  const h=host(),payload=withInlinePoster();
  h.app.ontoolresult(payload);assert(h.document.querySelector('#media iframe'));
  payload.structuredContent.media.reference_display='thumbnail';
  h.app.ontoolresult(payload);assert.equal(h.document.querySelector('#media iframe'),null,'changing only presentation mode tears down an existing iframe');
  const image=h.document.querySelector('#reference-poster img');image.onload();
  h.app.ontoolresult(payload);assert.equal(h.document.querySelector('#reference-poster img'),image,'repeat thumbnail results preserve the same decoded image');
  delete payload.structuredContent.media.reference_display;
  h.app.ontoolresult(payload);assert(h.document.querySelector('#media iframe'),'legacy playback still works after leaving thumbnail mode');
  assert(h.document.getElementById('reference-poster').hidden);
}
for(const media of [
  {media_type:'social/x',provider:'x',post_id:'463440424141459456',source_url:'https://x.com/Interior/status/463440424141459456'},
  {media_type:'text/html',provider:'tiktok',embed_url:'https://www.tiktok.com/player/v1/6718335390845095173',source_url:'https://www.tiktok.com/@scout2015/video/6718335390845095173'},
  {...withPoster().structuredContent.media,poster_url:'https://unverified.test/poster.jpg'},
]){
  const h=host();h.app.ontoolresult({structuredContent:{project_id:'p',media:{...media,reference_display:'thumbnail',title:'Original reference'}}});
  assert.equal(h.document.querySelector('#media video,#media iframe,#media img,head script[src],#reference-poster img'),null);
  assert(h.document.getElementById('media').hidden);assert(h.document.getElementById('reference-poster').hidden);
  assert.equal(h.document.getElementById('source-reference').textContent,'Original reference');
  assert.equal(h.document.getElementById('source-playback-hint').textContent,'');
  assert.equal(h.document.getElementById('media-status').textContent,'Source reference');
}
{
  const h=host(),payload=withInlinePoster();
  Object.assign(payload.structuredContent.media,{media_type:'video/mp4',embed_url:undefined,url:'https://source.test/legacy.mp4'});
  h.app.ontoolresult(payload);const source=h.document.querySelector('#media video');source.paused=false;source.ended=false;
  payload.structuredContent.media.reference_display='thumbnail';h.app.ontoolresult(payload);
  assert.equal(h.document.querySelector('#media video'),null,'thumbnail presentation immediately replaces even an already-playing legacy source video');
  assert(h.document.querySelector('#reference-poster img'));
}
{
  const h=host(),payload=withInlinePoster();payload.structuredContent.media.reference_display='thumbnail';h.app.ontoolresult(payload);
  cspViolation(h,{effectiveDirective:'img-src',blockedURI:'data:'});
  assert.equal(h.document.getElementById('reference-poster-status').textContent,'This chat blocked the source thumbnail. Open the original source.');
  assert.equal(h.document.getElementById('source-playback-hint').textContent,'');
  assert.equal(h.document.getElementById('source-reference').hidden,false);
  h.app.ontoolresult(result('generated','p',{final:false,reference_display:'thumbnail'}));
  const sample=h.document.querySelector('#media video');assert(sample?.controls,'the reference flag does not affect generated media without a source URL');
  assert.equal(h.document.getElementById('media').hidden,false);assert(h.document.getElementById('reference-poster').hidden);
  assert.equal(h.document.getElementById('reference-poster-status').textContent,'');
  assert.equal(h.document.getElementById('media-status').textContent,'Sample');
  h.app.ontoolresult(result('final','p'));assert.equal(h.document.querySelector('#media video'),sample);
  assert.equal(h.document.getElementById('media-status').textContent,'Sample');
  const finalHost=host();finalHost.app.ontoolresult(result('final','p'));
  assert(finalHost.document.querySelector('#media video')?.controls);
  assert.equal(finalHost.document.getElementById('media-status').textContent,'Final video');
}
console.log('PASS explicit thumbnail references skip every source player and preserve generated sample and final playback');
