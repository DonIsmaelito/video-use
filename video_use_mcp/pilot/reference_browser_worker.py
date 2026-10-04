"""Bounded reference browsing in an isolated Linux sandbox using Browser Harness.

The public entry point accepts JSON, never executable Python or JavaScript. The
only script passed to the official CLI imports this trusted dispatcher. Chromium
and its anonymous profile persist for the sandbox lifetime; evidence is returned
as paths so the caller can deliver the actual images separately from page text.
"""

from __future__ import annotations

import base64
import fcntl
import ipaddress
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit
import urllib.request
import uuid


STATE_DIR = Path("/tmp/video-use-reference-browser")
EVIDENCE_DIR = Path("/workspace/reference-evidence")
CHROMIUM = "/usr/bin/chromium"
CDP_URL = "http://127.0.0.1:9222"
MAX_INPUT_BYTES = 32_000
MAX_OUTPUT_BYTES = 1_000_000
EVENT_PREFIX = "VIDEO_USE_REFERENCE_EVENT "
ACTIONS = {
    "open": {"url"}, "read": set(), "click": {"node_id"},
    "fill": {"node_id", "text"}, "press": {"key"},
    "scroll": {"delta_y", "delta_x"}, "screenshot": set(),
    "sample_video": {"timestamps", "video_index", "capture_mode"}, "close": set(),
}
KEYS = {
    "Enter", "Tab", "Escape", "Backspace", "Delete", "Space", " ",
    "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End",
    "PageUp", "PageDown",
}


def _public_url(value):
    if (not isinstance(value, str) or len(value) > 4096 or "\\" in value
            or any(c.isspace() or ord(c) < 32 for c in value)):
        raise ValueError("A public HTTPS URL is required")
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname or "", parsed.port
    except ValueError as exc:
        raise ValueError("A public HTTPS URL is required") from exc
    if (parsed.scheme != "https" or not host or parsed.username is not None
            or parsed.password is not None or port not in (None, 443)
            or "%" in host or host.endswith(".")):
        raise ValueError("A public HTTPS URL is required")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if ("." not in host or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
                or all(c.isdigit() or c == "." for c in host)
                or host.lower().startswith("0x")):
            raise ValueError("A public HTTPS URL is required")
    else:
        if not address.is_global:
            raise ValueError("A public HTTPS URL is required")
    return value


def validate_request(payload):
    """Validate the complete batch before launching or interacting with a browser."""
    if not isinstance(payload, dict) or set(payload) - {"operations", "budget_seconds"}:
        raise ValueError("Use operations and optional budget_seconds only")
    operations = payload.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= 6:
        raise ValueError("Provide between 1 and 6 browser operations")
    budget = payload.get("budget_seconds", 30)
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 5 <= budget <= 45:
        raise ValueError("budget_seconds must be between 5 and 45")
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Each operation must be an object")
        action = operation.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError("Unknown browser action")
        if set(operation) - ({"action"} | ACTIONS[action]):
            raise ValueError(f"Unexpected fields for {action}")
        if action == "open":
            _public_url(operation.get("url"))
        if action in {"click", "fill"}:
            node = operation.get("node_id")
            if isinstance(node, bool) or not isinstance(node, int) or node < 1:
                raise ValueError("node_id must be a positive AX backend node ID")
        if action == "fill" and (not isinstance(operation.get("text"), str) or len(operation["text"]) > 2000):
            raise ValueError("fill needs text of at most 2000 characters")
        if action == "press" and (not isinstance(operation.get("key"), str) or operation["key"] not in KEYS):
            raise ValueError("Unsupported key")
        if action == "scroll":
            for key in ("delta_y", "delta_x"):
                value = operation.get(key, 600 if key == "delta_y" else 0)
                if isinstance(value, bool) or not isinstance(value, int) or abs(value) > 3000:
                    raise ValueError("Scroll deltas must be integers between -3000 and 3000")
        if action == "sample_video":
            stamps = operation.get("timestamps")
            if not isinstance(stamps, list) or not 1 <= len(stamps) <= 3:
                raise ValueError("sample_video needs 1 to 3 timestamps")
            if any(isinstance(t, bool) or not isinstance(t, (int, float))
                   or not math.isfinite(t) or not 0 <= t <= 600 for t in stamps):
                raise ValueError("Video timestamps must be finite seconds between 0 and 600")
            index = operation.get("video_index", 0)
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 20:
                raise ValueError("video_index must be between 0 and 19")
            mode = operation.get("capture_mode", "page")
            if not isinstance(mode, str) or mode not in {"page", "decoded"}:
                raise ValueError("capture_mode must be page or decoded")
    image_count = sum(1 if op["action"] == "screenshot" else len(op["timestamps"])
                      if op["action"] == "sample_video" else 0 for op in operations)
    if image_count > 4:
        raise ValueError("A browser batch may produce at most 4 images")
    return {"operations": operations, "budget_seconds": float(budget)}


def _environment():
    # No cloud credentials, user-selected profile, proxy or external CDP endpoint
    # may redirect this anonymous container browser to another session.
    env = {key: os.environ[key] for key in (
        "PATH", "LANG", "LC_ALL", "TZ", "LD_LIBRARY_PATH", "SSL_CERT_FILE", "SSL_CERT_DIR"
    ) if key in os.environ}
    env.update({
        "BU_CDP_URL": CDP_URL, "BH_HOME": str(STATE_DIR / "harness"),
        "BH_AGENT_WORKSPACE": str(STATE_DIR / "harness" / "agent-workspace"),
        "BH_RECORD": "0", "BH_TAB_MARKER": "0", "BH_TELEMETRY": "0",
        "BROWSER_HARNESS_TELEMETRY": "0", "ANONYMIZED_TELEMETRY": "false",
        "BH_DOMAIN_SKILLS": "0", "PYTHONUNBUFFERED": "1",
    })
    return env


def _chrome_ready():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(CDP_URL + "/json/version", timeout=0.3) as response:
            data = json.loads(response.read(16_384))
        return bool(data.get("webSocketDebuggerUrl"))
    except (OSError, ValueError):
        return False


def _owned_browser():
    try:
        pid = int((STATE_DIR / "chromium.pid").read_text())
        args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        return (f"--user-data-dir={STATE_DIR / 'profile'}".encode() in args
                and b"--remote-debugging-port=9222" in args)
    except (OSError, ValueError):
        return False


def _ensure_browser(deadline):
    if sys.platform != "linux" or not Path(CHROMIUM).is_file():
        raise RuntimeError("Reference browsing requires sandbox Linux /usr/bin/chromium")
    if _chrome_ready():
        if not _owned_browser():
            raise RuntimeError("Refusing to attach to a browser outside the isolated reference profile")
        return
    if not _owned_browser():
        (STATE_DIR / "tab.json").unlink(missing_ok=True)
        with (STATE_DIR / "chromium.log").open("ab") as log:
            process = subprocess.Popen([
                CHROMIUM, "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=9222",
                f"--user-data-dir={STATE_DIR / 'profile'}", "--no-first-run",
                "--no-default-browser-check", "--disable-background-networking",
                "--disable-sync", "--disable-extensions", "--disable-notifications",
                "--disable-component-update", "--password-store=basic",
                "--window-size=1280,900", "--mute-audio", "about:blank",
            ], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                env=_environment(), start_new_session=True)
        (STATE_DIR / "chromium.pid").write_text(str(process.pid))
    startup_deadline = min(deadline, time.monotonic() + 8)
    while time.monotonic() < startup_deadline:
        if _chrome_ready():
            return
        time.sleep(0.15)
    raise RuntimeError("Isolated Chromium did not become ready within the browser budget")


def _parse_events(stdout):
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    report = {"results": [], "evidence": [], "limitations": []}
    done = False
    for line in (stdout or "")[:MAX_OUTPUT_BYTES].splitlines():
        if not line.startswith(EVENT_PREFIX):
            continue
        try:
            event = json.loads(line[len(EVENT_PREFIX):])
        except ValueError:
            continue
        if "result" in event:
            report["results"].append(event["result"])
        report["evidence"].extend(event.get("evidence", []))
        report["limitations"].extend(event.get("limitations", []))
        done = done or event.get("done", False)
    return report, done


def run_request(payload):
    started = time.monotonic()
    report = {"results": [], "evidence": [], "limitations": []}
    try:
        request = validate_request(payload)
        deadline = started + request["budget_seconds"]
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        EVIDENCE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (STATE_DIR / "worker.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("This reference browser already has an active batch") from exc
            _ensure_browser(deadline)
            cli = shutil.which("browser-harness")
            if not cli:
                raise RuntimeError("browser-harness==0.1.13 is not installed")
            request["budget_seconds"] = max(0.1, deadline - time.monotonic())
            encoded = base64.b64encode(json.dumps(request).encode()).decode("ascii")
            root = str(Path(__file__).resolve().parents[2])
            script = (
                "import sys, json, base64\n"
                f"sys.path.insert(0, {root!r})\n"
                "from video_use_mcp.pilot.reference_browser_worker import _harness_dispatch\n"
                f"_harness_dispatch(json.loads(base64.b64decode({encoded!r})))\n"
            )
            timed_out = False
            try:
                completed = subprocess.run([cli], input=script, text=True, capture_output=True,
                                           timeout=max(0.1, deadline - time.monotonic()) + 1,
                                           env=_environment(), cwd=STATE_DIR)
                stdout, returncode = completed.stdout, completed.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, returncode, timed_out = exc.stdout, -1, True
            report, done = _parse_events(stdout)
            if timed_out:
                report["limitations"].append("Browser batch reached its time budget; only completed results are evidence.")
            elif returncode or not done:
                report["limitations"].append("Browser Harness did not complete the batch; retry or inspect the sandbox browser setup.")
            if len(report["results"]) < len(request["operations"]):
                report["incomplete_operations"] = len(request["operations"]) - len(report["results"])
    except (ValueError, RuntimeError, OSError) as exc:
        report["error"] = str(exc)[:500]
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return report


# All page JavaScript below is application-owned. Request fields are supplied
# only as JSON literals or CDP arguments, never as executable source.
PAGE_CONTENT_JS = """(() => ({
  text: (document.body?.innerText || '').slice(0,6000),
  links: Array.from(document.querySelectorAll('a[href]')).slice(0,60).map(a =>
    ({url:a.href.slice(0,4096),text:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,180)})),
  videos: Array.from(document.querySelectorAll('video')).slice(0,20).map((v,index) =>
    ({index,src:(v.currentSrc||v.src||'').slice(0,2048),duration_seconds:Number.isFinite(v.duration)?v.duration:null,
      visible:v.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}),
      post_id:v.closest('[id^="xgwrapper-"]')?.id.match(/^xgwrapper-[0-9]+-([0-9]+)$/)?.[1]||null,
      current_time_seconds:v.currentTime,paused:v.paused,loop:v.loop,ready_state:v.readyState,width:v.videoWidth,height:v.videoHeight})),
  embedded_frames: document.querySelectorAll('iframe').length,
  embedded_players: Array.from(document.querySelectorAll('iframe[src]')).slice(0,12).map(f =>
    ({src:f.src.slice(0,2048),title:(f.title||'').slice(0,160)})),
  password_field: !!document.querySelector('input[type=password]')
}))()"""

# Only public post fields: never read cookies, account APIs or hydration state.
# InteractionCounter semantics: https://schema.org/InteractionCounter
SOCIAL_METADATA_JS = r"""(() => {
  const bounded=(v,n=240)=>typeof v==='string'?v.trim().slice(0,n):'';
  const identity=value=>{
    try {
      const u=new URL(value,location.href),h=u.hostname.toLowerCase();
      if(u.protocol!=='https:'||u.username||u.password) return null;
      let m,id;
      if(['www.youtube.com','youtube.com','m.youtube.com','www.youtube-nocookie.com','youtu.be'].includes(h)) {
        id=h==='youtu.be'?u.pathname.slice(1):u.pathname==='/watch'?u.searchParams.get('v'):(u.pathname.match(/^\/(?:shorts|embed|live)\/([\w-]{11})\/?$/)||[])[1];
        if(/^[\w-]{11}$/.test(id||'')) return {platform:'youtube',post_id:id,canonical_url:'https://www.youtube.com/watch?v='+id};
      }
      if(['www.tiktok.com','tiktok.com','m.tiktok.com'].includes(h)&&(m=u.pathname.match(/^\/@([^/]+)\/video\/(\d+)\/?$/)))
        return {platform:'tiktok',post_id:m[2],canonical_url:'https://www.tiktok.com/@'+m[1]+'/video/'+m[2]};
      if(['x.com','www.x.com','twitter.com','www.twitter.com','mobile.twitter.com'].includes(h)&&(m=u.pathname.match(/^\/([^/]+)\/status\/(\d+)(?:\/.*)?$/)))
        return {platform:'x',post_id:m[2],canonical_url:'https://x.com/'+m[1]+'/status/'+m[2]};
    } catch {}
    return null;
  };
  const current=identity(location.href);
  if(!current) return null;
  const same=value=>{const p=identity(value);return p&&p.platform===current.platform&&p.post_id===current.post_id;};
  const one=(selector,root=document)=>{
    const items=Array.from(root.querySelectorAll(selector)).slice(0,3);
    return items.length===1?items[0]:null;
  };
  const meta=key=>bounded(one('meta[property="'+key+'"],meta[name="'+key+'"]')?.content);
  const canonical=one('link[rel="canonical"]')?.href||meta('og:url');
  const result={...current,page_url:location.href,post_verified:false,title:'',creator:'',published_at:'',duration:null,
    metrics:{views:null,likes:null,comments:null,shares:null},visible_text:'',limitations:[]};
  if(canonical&&!same(canonical)) {
    result.limitations.push('Page canonical identity differs from the requested post; engagement was not attributed.');
    return result;
  }
  const canonicalBound=!!canonical&&same(canonical);
  if(canonicalBound) {result.title=meta('og:title');result.published_at=meta('article:published_time');}
  const visible=e=>!!e&&typeof e.checkVisibility==='function'&&e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
  const evidenceLines=[],conflicts=new Set();
  let durationConflict=false,durationLive=false;
  const putDuration=entry=>{
    const publications=Array.isArray(entry.publication)?entry.publication:[entry.publication];
    if(entry.isLiveBroadcast===true||publications.slice(0,8).some(event=>
      event?.isLiveBroadcast===true&&(!Number.isFinite(Date.parse(event.endDate))||Date.parse(event.endDate)>Date.now()))) {
      durationLive=true;result.duration=null;return;
    }
    if(durationConflict||durationLive)return;
    const raw=entry.duration;
    if(typeof raw!=='string'||raw.length>64||raw.endsWith('T'))return;
    const match=raw.match(/^P(?:([0-9]{1,6})D)?(?:T(?:([0-9]{1,6})H)?(?:([0-9]{1,6})M)?(?:([0-9]{1,6}(?:\.[0-9]{1,6})?)S)?)?$/);
    if(!match||match[0]!==raw||!match.slice(1).some(part=>part!==undefined))return;
    const seconds=match.slice(1).reduce((sum,part,index)=>sum+Number(part||0)*[86400,3600,60,1][index],0);
    if(!Number.isFinite(seconds)||seconds<=0||seconds>604800)return;
    if(result.duration&&result.duration.seconds!==seconds) {
      result.duration=null;durationConflict=true;
      result.limitations.push('Conflicting public video durations; left unknown.');return;
    }
    result.duration={seconds,source:'json_ld',evidence:'VideoObject.duration: '+raw};
  };
  const ranks={meta:0,json_ld:1,visible_text:2};
  const put=(name,raw,evidence,source)=>{
    if(!(name in result.metrics)||conflicts.has(name)) return;
    const display=bounded(String(raw),40);
    if(!/^\d[\d,. ]*\s?[KMB]?$/i.test(display)) return;
    let value=null;
    if(/^\d+$/.test(display)||/^\d{1,3}(,\d{3})+$/.test(display)) {
      const n=Number(display.replaceAll(',',''));if(Number.isSafeInteger(n)&&n>=0)value=n;
    }
    const previous=result.metrics[name];
    if(previous&&ranks[previous.source]>ranks[source])return;
    if(previous&&previous.source===source&&previous.display!==display) {
      result.metrics[name]=null;conflicts.add(name);result.limitations.push('Conflicting public '+name+' counts; left unknown.');return;
    }
    result.metrics[name]={value,display,evidence:bounded(evidence,300),source};
    if(source==='visible_text'&&evidenceLines.length<12)evidenceLines.push(bounded(evidence,200));
  };
  const readLabel=(element,name)=>{
    if(!visible(element))return;
    const label=bounded(element.getAttribute?.('aria-label')||element.innerText||'',300);
    const words={views:'views?',likes:'likes?',comments:'comments?|replies',shares:'reposts?|shares?'}[name];
    const count=label.match(new RegExp('(?:^|\\s)(\\d[\\d,.]*\\s?[KMB]?)\\s+(?:'+words+')(?:\\b|$)','i'));
    if(count)put(name,count[1],label,'visible_text');
  };
  let visited=0;
  const visit=(entry,depth=0)=>{
    if(!entry||depth>4||++visited>60)return;
    if(Array.isArray(entry)){entry.slice(0,12).forEach(x=>visit(x,depth+1));return;}
    if(typeof entry!=='object')return;
    const types=[entry['@type']].flat();
    const urls=[entry.url,entry['@id'],entry.embedUrl,
      typeof entry.mainEntityOfPage==='string'?entry.mainEntityOfPage:entry.mainEntityOfPage?.['@id']];
    if(types.some(t=>['VideoObject','SocialMediaPosting'].includes(t))&&urls.some(u=>typeof u==='string'&&same(u))) {
      result.post_verified=true;
      result.title=result.title||bounded(entry.name||entry.headline);
      const author=Array.isArray(entry.author)?entry.author[0]:entry.author;
      result.creator=result.creator||bounded(typeof author==='string'?author:author?.name,160);
      result.published_at=result.published_at||bounded(entry.datePublished||entry.uploadDate,80);
      if(types.includes('VideoObject')&&urls.every(u=>typeof u!=='string'||!identity(u)||same(u)))putDuration(entry);
      const counters=Array.isArray(entry.interactionStatistic)?entry.interactionStatistic:[entry.interactionStatistic];
      counters.slice(0,8).forEach(counter=>{
        if(!counter||typeof counter!=='object')return;
        const type=typeof counter.interactionType==='string'?counter.interactionType:counter.interactionType?.['@type'];
        const action=String(type||'').split('/').pop();
        const name={WatchAction:'views',ViewAction:'views',LikeAction:'likes',CommentAction:'comments',ShareAction:'shares'}[action];
        if(name&&counter.userInteractionCount!==undefined)put(name,counter.userInteractionCount,action+': '+counter.userInteractionCount,'json_ld');
      });
      if(entry.commentCount!==undefined)put('comments',entry.commentCount,'commentCount: '+entry.commentCount,'json_ld');
    }
    // Traverse only schema containers, never recommendation/hydration graphs.
    if(entry['@graph'])visit(entry['@graph'],depth+1);
    if(entry.mainEntity)visit(entry.mainEntity,depth+1);
  };
  Array.from(document.querySelectorAll('script[type="application/ld+json"]')).slice(0,8).forEach(script=>{
    const raw=script.textContent||'';if(raw.length>65536)return;
    try{visit(JSON.parse(raw));}catch{}
  });
  if(current.platform==='youtube'&&canonicalBound) {
    const scope=one('ytd-watch-metadata');
    if(visible(scope)) {
      const view=one('#view-count',scope)||one('.view-count',scope);
      readLabel(view,'views');
      Array.from(scope.querySelectorAll('button[aria-label]')).slice(0,30).forEach(button=>{
        const label=bounded(button.getAttribute('aria-label'),300);
        if(!visible(button)||/dislike/i.test(label))return;
        if(/\blikes?\b/i.test(label)) {
          const match=label.match(/along with ([\d,]+) other people/i);
          if(match)put('likes',match[1],label,'visible_text');else readLabel(button,'likes');
        }
      });
      const author=one('#owner a[href]',scope);
      if(visible(author)&&bounded(author.innerText,160)) {
        result.creator=result.creator||bounded(author.innerText,160);result.post_verified=true;
      }
    }
    const comments=one('ytd-comments-header-renderer #count');readLabel(comments,'comments');
    // Explicit page-level counts only, not generic interactionCount metadata.
    for(const [field,name] of [['video:views','views'],['video:likes','likes'],['video:comments','comments']]) {
      const value=meta(field);if(value)put(name,value,field+': '+value,'meta');
    }
  } else if(current.platform==='tiktok'&&canonicalBound) {
    for(const [field,name] of [['browse-like-count','likes'],['browse-comment-count','comments'],['browse-share-count','shares']]) {
      const element=one('[data-e2e="'+field+'"]');
      if(visible(element))put(name,bounded(element.innerText,40),field+': '+bounded(element.innerText,40),'visible_text');
    }
    const author=one('[data-e2e="browse-username"]');
    if(visible(author)&&bounded(author.innerText,160)) {
      result.creator=result.creator||bounded(author.innerText,160);result.post_verified=true;
    }
  } else if(current.platform==='x') {
    const articles=Array.from(document.querySelectorAll('article[data-testid="tweet"]')).slice(0,20).filter(article=>{
      const time=article.querySelector('time');return time&&same(time.closest('a[href]')?.href||'');
    });
    if(articles.length===1&&visible(articles[0])) {
      const article=articles[0];result.published_at=result.published_at||bounded(article.querySelector('time')?.dateTime,80);
      const body=one('[data-testid="tweetText"]',article),author=one('[data-testid="User-Name"]',article);
      if((visible(body)&&bounded(body.innerText))||(visible(author)&&bounded(author.innerText))||visible(one('video',article))) {
        result.post_verified=true;result.title=result.title||bounded(body?.innerText);
        result.creator=result.creator||bounded(author?.innerText,160);
      }
      for(const [field,name] of [['like','likes'],['unlike','likes'],['reply','comments'],['retweet','shares'],['unretweet','shares']]) {
        const e=one('[data-testid="'+field+'"]',article);
        if(visible(e)&&e.closest('article')===article) {
          const raw=bounded(e.innerText,40);if(raw)put(name,raw,field+': '+raw,'visible_text');
        }
      }
      for(const a of Array.from(article.querySelectorAll('a[href]')).slice(0,30)) {
        if(visible(a)&&a.href.includes('/status/'+current.post_id+'/analytics'))readLabel(a,'views');
      }
    }
  }
  if(!result.post_verified) {
    for(const name of Object.keys(result.metrics))result.metrics[name]=null;
    evidenceLines.length=0;
    result.limitations.push('Post content could not be verified on the public page; login walls or unavailable posts were not bypassed.');
  }
  result.visible_text=evidenceLines.join('\n').slice(0,1800);
  if(!Object.values(result.metrics).some(Boolean))result.limitations.push('No unambiguous public engagement counts for this post were available; missing counts are unknown, not zero.');
  result.limitations.push('Counts are public page claims observed at capture time; login walls and hidden data were not bypassed.');
  return result;
})()"""

NODE_INFO_JS = """function() {
  const link=this.closest?.('a[href]');
  return {tag:this.tagName,type:this.type||'',autocomplete:this.autocomplete||'',
    href:link?.href||'',target:link?.target||'',download:!!link?.hasAttribute('download'),
    editable:this.isContentEditable||this.tagName==='INPUT'||this.tagName==='TEXTAREA'};
}"""


class _Session:
    def __init__(self, harness, deadline):
        self.h = harness
        self.deadline = deadline
        self.tab = None
        self.evidence = []
        self.limitations = []
        path = STATE_DIR / "tab.json"
        if path.exists():
            target = json.loads(path.read_text()).get("target_id")
            if target and any(t["targetId"] == target for t in self.h.list_tabs()):
                self.h.switch_tab(target)
                self.tab = target
        self.h.cdp("Browser.setDownloadBehavior", behavior="deny")

    def _page(self):
        if not self.tab:
            raise ValueError("Open a reference URL before inspecting or interacting")
        info = self.h.page_info()
        if info.get("dialog"):
            raise ValueError("A browser dialog blocks inspection; no automatic consent is given")
        _public_url(info.get("url"))
        return {"page_url": info["url"], "title": str(info.get("title", ""))[:300],
                "viewport": {k: info.get(k) for k in ("w", "h", "sx", "sy")}}

    def snapshot(self):
        page = self._page()
        content = self.h.js(PAGE_CONTENT_JS) or {}
        nodes = self.h.cdp("Accessibility.getFullAXTree", depth=8).get("nodes", [])
        compact = []
        for node in nodes:
            role = node.get("role", {}).get("value", "")
            name = str(node.get("name", {}).get("value", ""))
            if node.get("ignored") or role in {"none", "generic", "InlineTextBox"}:
                continue
            item = {"role": str(role)[:50], "name": name[:220]}
            if node.get("backendDOMNodeId"):
                item["node_id"] = node["backendDOMNodeId"]
            compact.append(item)
            if len(compact) >= 120:
                break
        if content.get("password_field"):
            self.limitations.append("This page includes a login form; this anonymous browser cannot use account credentials.")
        if content.get("embedded_frames"):
            self.limitations.append("Text and video metadata cover the top document; embedded players may require visual inspection.")
        links = []
        for link in content.get("links", []):
            try:
                _public_url(link.get("url"))
                links.append(link)
            except ValueError:
                pass
        players = []
        for player in content.get("embedded_players", []):
            try:
                _public_url(player.get("src"))
                players.append(player)
            except ValueError:
                pass
        result = page | {"text": content.get("text", ""), "links": links,
                       "accessibility": compact, "videos": content.get("videos", []),
                       "embedded_players": players,
                       "snapshot_limits": {"text_characters": 6000, "links": 60, "ax_nodes": 120, "ax_depth": 8}}
        host = urlsplit(page["page_url"]).hostname
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
                    "www.youtube-nocookie.com", "tiktok.com", "www.tiktok.com", "m.tiktok.com",
                    "x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
            try:
                social = self.h.js(SOCIAL_METADATA_JS)
                if isinstance(social, dict):
                    result["social_metadata"] = social | {"observed_at": time.time()}
            except Exception:
                self.limitations.append("Public social metadata was unavailable; no engagement counts were inferred.")
        return result

    def _node(self, node_id):
        resolved = self.h.cdp("DOM.resolveNode", backendNodeId=node_id)["object"]["objectId"]
        try:
            result = self.h.cdp("Runtime.callFunctionOn", objectId=resolved,
                                functionDeclaration=NODE_INFO_JS, returnByValue=True)
            if result.get("exceptionDetails"):
                raise ValueError("The requested node is no longer available")
            return result.get("result", {}).get("value", {})
        finally:
            self.h.cdp("Runtime.releaseObject", objectId=resolved)

    def _click(self, node_id):
        info = self._node(node_id)
        if info.get("download"):
            raise ValueError("Automatic downloads are disabled")
        if info.get("href"):
            _public_url(info["href"])
            if info.get("target") == "_blank":
                self.h.goto_url(info["href"])
                return info["href"]
        self.h.cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=node_id)
        quad = self.h.cdp("DOM.getBoxModel", backendNodeId=node_id)["model"]["content"]
        x, y = sum(quad[0::2]) / 4, sum(quad[1::2]) / 4
        viewport = self.h.page_info()
        if not (0 <= x < viewport.get("w", 0) and 0 <= y < viewport.get("h", 0)):
            raise ValueError("The requested node is outside the browser viewport")
        self.h.click_at_xy(x, y)
        return info.get("href")

    def _settle_link(self, previous_url, href):
        """Wait for an asynchronous link navigation, within this batch's budget."""
        if not href or href == previous_url:
            return
        deadline = min(self.deadline, time.monotonic() + 3)
        while time.monotonic() < deadline:
            current = self.h.page_info().get("url", "")
            if current and current not in {previous_url, "about:blank"}:
                remaining = deadline - time.monotonic()
                if remaining > 0 and not self.h.wait_for_load(timeout=remaining):
                    self.limitations.append("The linked page is still loading; the snapshot reflects its current rendered state.")
                return
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        self.limitations.append("The link did not finish navigating within the browser budget; inspect the returned page URL before reusing node IDs.")

    def _capture(self, kind="screenshot", **metadata):
        page = self._page()
        path = EVIDENCE_DIR / f"{uuid.uuid4().hex}.png"
        self.h.capture_screenshot(str(path), max_dim=1600)
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Browser screenshot produced no image")
        evidence = {"path": str(path), "mime_type": "image/png", "kind": kind,
                    "page_url": page["page_url"], **metadata}
        self.evidence.append(evidence)
        return evidence

    def _sample_video(self, operation):
        frames = []
        index = operation.get("video_index", 0)
        capture_mode = operation.get("capture_mode", "page")
        for requested in operation["timestamps"]:
            remaining = self.deadline - time.monotonic()
            if remaining < 0.5:
                self.limitations.append("Video sampling stopped at the browser time budget.")
                break
            # The timeout is below Browser Harness's Runtime.evaluate timeout.
            # Successful seeking is evidence of these frames, not full playback.
            expression = """(async () => {
              const deadline=performance.now()+WAIT_MS;
              const remaining=()=>Math.max(0,deadline-performance.now());
              const decoded=DECODED;
              const v=document.querySelectorAll('video')[INDEX];
              if(!v) return {ok:false,reason:'No top-document HTML5 video is available; embedded or custom players cannot be sampled here.'};
              const tiktokPost=['www.tiktok.com','tiktok.com','m.tiktok.com'].includes(location.hostname)&&location.pathname.match(/[/]@[^/]+[/]video[/]([0-9]+)/)?.[1];
              if(decoded&&tiktokPost) {
                const wrapper=v.closest('[id^="xgwrapper-"]');
                const bound=wrapper?.id.match(/^xgwrapper-[0-9]+-([0-9]+)$/)?.[1];
                if(bound!==tiktokPost)return {ok:false,reason:'The selected TikTok video is not bound to this post in the rendered player. Inspect the video_index and post_id before sampling; no related clip was substituted.'};
              }
              const showingAd=()=>{
                const player=v.closest?.('.html5-video-player');
                return player?.classList.contains('ad-showing')||player?.classList.contains('ad-interrupting');
              };
              const adUnavailable={ok:false,reason:'The selected YouTube player is showing an ad; use its visible controls or wait for the ad to finish before sampling source-video frames.'};
              if(showingAd())return adUnavailable;
              if(!decoded&&!v.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}))
                return {ok:false,reason:'The chosen video is CSS-hidden. For a custom canvas player use capture_mode=decoded with this explicit video_index, or reveal the player. No different video was substituted.'};
              // Keep the exact selected element. Do not fall back to a visible
              // related clip when the requested player is hidden or unavailable.
              if(!decoded)v.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});
              await new Promise(resolve=>requestAnimationFrame(resolve));
              if(!Number.isFinite(v.duration)||v.readyState<1) {
                await new Promise(resolve => {
                  let timer; const events=['loadedmetadata','error'];
                  const done=()=>{clearTimeout(timer);events.forEach(event=>v.removeEventListener(event,done));resolve();};
                  timer=setTimeout(done,Math.min(1500,remaining()));
                  events.forEach(event=>v.addEventListener(event,done,{once:true}));
                  // Lazy video elements may not request metadata until asked.
                  // Loading does not play audio or grant page permissions.
                  if(v.readyState===0) {v.preload='auto';v.load();}
                  if(Number.isFinite(v.duration)&&v.readyState>=1) done();
                });
              }
              if(!Number.isFinite(v.duration)||v.readyState<1) return {ok:false,reason:'Video metadata is unavailable or the stream is not seekable.'};
              if(showingAd())return adUnavailable;
              const target=STAMP;
              if(target>=v.duration) return {ok:false,reason:'The requested timestamp is outside the video duration.'};
              v.pause(); v.muted=true;
              const settled=await new Promise(resolve => {
                let timer; const events=['seeked','loadeddata'];
                const finish=ok=>{clearTimeout(timer);events.forEach(event=>v.removeEventListener(event,done));resolve(ok);};
                const done=()=>{if(v.readyState>=2&&Math.abs(v.currentTime-target)<0.03) finish(true);};
                timer=setTimeout(()=>finish(false),remaining());
                events.forEach(event=>v.addEventListener(event,done));
                if(Math.abs(v.currentTime-target)<0.03 && v.readyState>=2) finish(true);
                else v.currentTime=target;
              });
              const r=v.getBoundingClientRect();
              const visible=v.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})
                &&r.width>0&&r.height>0&&r.bottom>0&&r.right>0&&r.top<innerHeight&&r.left<innerWidth;
              if(!settled||Math.abs(v.currentTime-target)>0.25) return {ok:false,reason:'Video did not decode the requested frame before the seek timeout.'};
              if(!decoded&&!visible) return {ok:false,reason:'Video is hidden or outside the viewport; make it visible before sampling.'};
              await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
              if(showingAd())return adUnavailable;
              let frame_data;
              if(decoded) {
                if(!v.videoWidth||!v.videoHeight)return {ok:false,reason:'The selected video has no decoded picture.'};
                const scale=Math.min(1,1600/v.videoWidth,1600/v.videoHeight);
                const canvas=document.createElement('canvas');
                canvas.width=Math.max(1,Math.round(v.videoWidth*scale));
                canvas.height=Math.max(1,Math.round(v.videoHeight*scale));
                try {
                  canvas.getContext('2d').drawImage(v,0,0,canvas.width,canvas.height);
                  frame_data=canvas.toDataURL('image/png');
                } catch(e) {
                  return {ok:false,reason:'The browser does not permit reading this decoded frame. Use visible page capture or another accessible reference; no media access restriction was bypassed.'};
                }
                if(frame_data.length>4000000)return {ok:false,reason:'Decoded frame exceeds the inspection image limit.'};
              }
              return {ok:true,timestamp_seconds:v.currentTime,duration_seconds:v.duration,
                video_src:(v.currentSrc||v.src||'').slice(0,2048),frame_data};
            })()""".replace("INDEX", json.dumps(index)).replace("STAMP", json.dumps(requested)).replace(
                "WAIT_MS", json.dumps(max(1, int(min(3, remaining - 0.25) * 1000)))).replace(
                "DECODED", json.dumps(capture_mode == "decoded"))
            sampled = self.h.js(expression) or {}
            if not sampled.get("ok"):
                self.limitations.append(str(sampled.get("reason", "Video frame is unavailable"))[:400])
                continue
            metadata = dict(requested_timestamp_seconds=requested,
                            timestamp_seconds=sampled["timestamp_seconds"], video_index=index,
                            video_src=sampled.get("video_src", ""), capture_mode=capture_mode)
            if capture_mode == "decoded":
                data = sampled.get("frame_data", "")
                if not data.startswith("data:image/png;base64,") or len(data) > 4_000_000:
                    raise ValueError("Invalid decoded video frame")
                path = EVIDENCE_DIR / f"{uuid.uuid4().hex}.png"
                path.write_bytes(base64.b64decode(data.split(",", 1)[1], validate=True))
                evidence = dict(path=str(path), mime_type="image/png", kind="video_frame",
                                page_url=self._page()["page_url"], **metadata)
                self.evidence.append(evidence)
            else:
                evidence = self._capture("video_frame", **metadata)
            frames.append(evidence)
        self.limitations.append("Video evidence contains only the returned decoded frame screenshots; audio and continuous playback were not inspected.")
        result = {"ok": bool(frames), "page_url": self._page()["page_url"],
                  "frames": frames, "sampled_frames": len(frames), "playback_verified": False,
                  "video_index": index,
                  "availability": "available" if len(frames) == len(operation["timestamps"]) else "partial" if frames else "unavailable"}
        if not frames:
            result["error"] = "No decoded video frames were captured; inspect the limitations or a page screenshot before retrying."
        return result

    def perform(self, operation):
        action = operation["action"]
        if action == "open":
            if self.tab:
                self.h.goto_url(operation["url"])
            else:
                self.tab = self.h.new_tab(operation["url"])
                (STATE_DIR / "tab.json").write_text(json.dumps({"target_id": self.tab}))
            loaded = self.h.wait_for_load(timeout=max(0.1, min(6, self.deadline - time.monotonic())))
            if not loaded:
                self.limitations.append("The page did not finish loading; the snapshot reflects its current rendered state.")
            return self.snapshot()
        if action == "close":
            if self.tab:
                self.h.close_tab(self.tab)
            self.tab = None
            (STATE_DIR / "tab.json").unlink(missing_ok=True)
            return {"closed": True}
        self._page()
        if action == "read":
            return self.snapshot()
        if action == "screenshot":
            return {"page_url": self._page()["page_url"], "image": self._capture()}
        if action == "sample_video":
            return self._sample_video(operation)
        if action == "click":
            previous_url = self._page()["page_url"]
            href = self._click(operation["node_id"])
            self._settle_link(previous_url, href)
        elif action == "fill":
            node_id = operation["node_id"]
            info = self._node(node_id)
            if (not info.get("editable") or info.get("type") == "password"
                    or info.get("autocomplete") in {"username", "current-password", "new-password", "one-time-code"}):
                raise ValueError("Only ordinary editable fields are supported; credentials are not accepted")
            self.h.cdp("DOM.focus", backendNodeId=node_id)
            self.h.cdp("Input.dispatchKeyEvent", type="rawKeyDown", key="a", code="KeyA",
                       modifiers=2, windowsVirtualKeyCode=65, commands=["SelectAll"])
            self.h.cdp("Input.dispatchKeyEvent", type="keyUp", key="a", code="KeyA", modifiers=2)
            self.h.press_key("Backspace")
            self.h.type_text(operation["text"])
        elif action == "press":
            self.h.press_key(" " if operation["key"] == "Space" else operation["key"])
        elif action == "scroll":
            viewport = self.h.page_info()
            self.h.scroll(viewport.get("w", 1280) / 2, viewport.get("h", 900) / 2,
                          dy=operation.get("delta_y", 600), dx=operation.get("delta_x", 0))
        time.sleep(min(0.35, max(0, self.deadline - time.monotonic())))
        return self.snapshot()


def _emit_event(event):
    """Keep six streamed operation events together below the output ceiling."""
    limit = MAX_OUTPUT_BYTES // 7
    encoded = json.dumps(event, ensure_ascii=False)
    while len(encoded.encode("utf-8")) > limit:
        result = event.get("result", {})
        candidates = [(key, result.get(key)) for key in ("accessibility", "links", "text")]
        candidates = [(key, value) for key, value in candidates if isinstance(value, (str, list)) and len(value) > 1]
        if not candidates:
            raise RuntimeError("Browser evidence exceeded the output size limit")
        key, value = max(candidates, key=lambda pair: len(json.dumps(pair[1])))
        result[key] = value[:len(value) // 2]
        result["output_truncated"] = True
        encoded = json.dumps(event, ensure_ascii=False)
    print(EVENT_PREFIX + encoded, flush=True)


def _harness_dispatch(payload):
    from browser_harness import helpers

    deadline = time.monotonic() + payload["budget_seconds"]
    session = _Session(helpers, deadline)
    halted = False
    for operation in payload["operations"]:
        if (halted or time.monotonic() >= deadline) and operation["action"] != "close":
            continue
        evidence_start, limits_start = len(session.evidence), len(session.limitations)
        try:
            result = {"action": operation["action"], "ok": True, **session.perform(operation)}
        except Exception as exc:
            result = {"action": operation["action"], "ok": False, "error": str(exc)[:500]}
            if not session.tab:
                result["requires_open"] = True
        _emit_event({"result": result, "evidence": session.evidence[evidence_start:],
                     "limitations": session.limitations[limits_start:]})
        if not result["ok"]:
            halted = True  # Only explicit cleanup may follow a failed action.
    _emit_event({"done": True})


def main():
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    try:
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("Browser request exceeds the input size limit")
        request = json.loads(raw)
        report = run_request(request)
    except (ValueError, UnicodeError) as exc:
        report = {"results": [], "evidence": [], "elapsed_seconds": 0,
                  "limitations": [], "error": str(exc)[:500]}
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
