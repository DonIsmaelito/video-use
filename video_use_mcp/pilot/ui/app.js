import { App, applyDocumentTheme } from "@modelcontextprotocol/ext-apps";
const app = new App({ name: "Video preview", version: "2.0.0" });
const $ = (id) => document.getElementById(id);
let media, shown;
function unpack(result) {
  if (result.isError) throw Error("This preview could not be loaded.");
  const data = result.structuredContent;
  if (data?.media) return data.media;
  // Previously opened conversations can still supply the older result shape.
  const project = data?.project_card || data;
  if (project) {
    const values = (project.updates || []).filter(u => u.preview && u.stage !== "review").map(u => ({...u.preview, at:u.at, caption:u.note}));
    for (const r of project.revisions || []) values.push({object_id:r.video, media_type:"video/mp4",url:r.video_url,download_url:r.download_url,at:r.created});
    values.sort((a,b) => new Date(a.at)-new Date(b.at));
    if (values.length) return values.at(-1);
  }
  return null;
}
function render(next) {
  if (!next) return;
  media = next;
  const key = next.object_id || next.url;
  if (shown !== key) {
    const video = next.media_type === "video/mp4";
    const element = document.createElement(video ? "video" : "img");
    element.src = next.url;
    if (video) {element.controls=true; element.playsInline=true; element.preload="metadata";}
    else element.alt = next.caption || "Proposed video frame";
    element.onerror = () => {$("notice").textContent="The preview link expired. Ask Claude to show it again.";};
    $("media").replaceChildren(element);
    shown=key;
  }
  $("visual").hidden=false;
  $("download").hidden=next.media_type !== "video/mp4";
  $("notice").textContent="";
}
$("download").onclick=async()=>{
  if (media) await app.openLink({url:media.download_url || media.url + "&download=true"});
};
app.ontoolresult=(result)=>{
  try {render(unpack(result));} catch(e){$("notice").textContent=e.message;}
};
app.onhostcontextchanged=(context)=>{if(context.theme)applyDocumentTheme(context.theme);};
app.onteardown=async()=>({});
app.connect().catch(()=>{$("notice").textContent="Ask Claude to show this preview again.";});
