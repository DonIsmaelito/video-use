"""The browser tool accepts bounded data and reports only captured evidence."""

import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from video_use_mcp.pilot import reference_browser_worker as worker


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    state, evidence = tmp_path / "state", tmp_path / "evidence"
    state.mkdir()
    evidence.mkdir()
    monkeypatch.setattr(worker, "STATE_DIR", state)
    monkeypatch.setattr(worker, "EVIDENCE_DIR", evidence)
    return state, evidence


@pytest.mark.parametrize("payload", [
    {}, {"operations": []}, {"operations": [{"action": "read"}] * 7},
    {"operations": [{"action": "evaluate", "code": "alert(1)"}]},
    {"operations": [{"action": "read", "python": "import os"}]},
    {"operations": [{"action": "press", "key": ["Enter"]}]},
    {"operations": [{"action": "press", "key": "Control+s"}]},
    {"operations": [{"action": "click", "node_id": True}]},
    {"operations": [{"action": "fill", "node_id": 1, "text": "x" * 2001}]},
    {"operations": [{"action": "scroll", "delta_y": 3001}]},
    {"operations": [{"action": "sample_video", "timestamps": [0, 1, 2, 3]}]},
    {"operations": [{"action": "sample_video", "timestamps": [float("nan")]}]},
    {"operations": [{"action": "sample_video", "timestamps": [601]}]},
    {"operations": [{"action": "screenshot"}] * 5},
    {"operations": [{"action": "read"}], "budget_seconds": 46},
    {"operations": [{"action": "read"}], "budget_seconds": float("nan")},
    {"operations": [{"action": "read"}], "profile": "/root/.config/chromium"},
])
def test_invalid_requests_fail_before_browser_start(payload, monkeypatch):
    monkeypatch.setattr(worker, "_ensure_browser", lambda _: pytest.fail("browser started"))
    report = worker.run_request(payload)
    assert report["error"]
    assert report["results"] == report["evidence"] == []


@pytest.mark.parametrize("url", [
    "http://example.com", "file:///etc/passwd", "javascript:alert(1)",
    "https://127.0.0.1", "https://169.254.169.254/latest/meta-data",
    "https://localhost", "https://host.internal", "https://[::1]",
    "https://0177.0.0.1", "https://2130706433", "https://0x7f000001",
    "https://127.1", "https://user:pass@example.com", "https://example.com:9222",
    "https://example.com\\@127.0.0.1", "https://example.com.\n",
])
def test_private_or_executable_urls_are_rejected(url):
    with pytest.raises(ValueError, match="public HTTPS"):
        worker.validate_request({"operations": [{"action": "open", "url": url}]})


def test_environment_cannot_reuse_cloud_credentials_or_another_browser(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_API_KEY", "do-not-inherit")
    monkeypatch.setenv("BU_NAME", "user-browser")
    monkeypatch.setenv("BU_CDP_WS", "wss://another-browser.example")
    monkeypatch.setenv("PYTHONPATH", "/untrusted/imports")
    env = worker._environment()
    assert not set(env) & {"BROWSER_USE_API_KEY", "BU_NAME", "BU_CDP_WS", "PYTHONPATH"}
    assert env["BU_CDP_URL"] == "http://127.0.0.1:9222"
    assert env["BH_RECORD"] == env["BH_TELEMETRY"] == env["BH_TAB_MARKER"] == "0"


class Harness:
    def __init__(self):
        self.url = "about:blank"
        self.tabs = []
        self.calls = []
        self.video = None

    def list_tabs(self):
        return self.tabs

    def switch_tab(self, target):
        self.calls.append(("switch_tab", target))

    def new_tab(self, url):
        self.url = url
        self.tabs.append({"targetId": "owned-tab"})
        self.calls.append(("new_tab", url))
        return "owned-tab"

    def goto_url(self, url):
        self.url = url
        self.calls.append(("goto_url", url))

    def wait_for_load(self, timeout):
        return True

    def page_info(self):
        return {"url": self.url, "title": "Example reference", "w": 1280, "h": 900}

    def js(self, expression):
        if expression == worker.PAGE_CONTENT_JS:
            return {"text": "Rendered reference content", "links": [
                {"url": "https://artist.example/film", "text": "Film"},
                {"url": "javascript:alert(1)", "text": "Unsafe"},
            ], "videos": [], "embedded_frames": 1, "embedded_players": [
                {"src": "https://player.vimeo.com/video/123456", "title": "Reference film"},
                {"src": "http://127.0.0.1/player", "title": "Private"},
                {"src": "javascript:alert(1)", "title": "Unsafe"},
            ]}
        assert "querySelectorAll('video')" in expression
        return self.video or {"ok": False, "reason": "No top-document HTML5 video is available"}

    def cdp(self, method, **kwargs):
        self.calls.append((method, kwargs))
        if method == "Accessibility.getFullAXTree":
            return {"nodes": [
                {"role": {"value": "button"}, "name": {"value": "Play"}, "backendDOMNodeId": 123},
                {"ignored": True, "role": {"value": "button"}, "name": {"value": "Hidden"}},
            ]}
        if method == "DOM.resolveNode":
            return {"object": {"objectId": str(kwargs["backendNodeId"])}}
        if method == "Runtime.callFunctionOn":
            info = {"editable": True, "type": "password" if kwargs["objectId"] == "999" else "text"}
            return {"result": {"value": info}}
        if method == "DOM.getBoxModel":
            return {"model": {"content": [10, 10, 30, 10, 30, 30, 10, 30]}}
        return {}

    def click_at_xy(self, x, y):
        self.calls.append(("click", x, y))

    def press_key(self, key):
        self.calls.append(("press", key))

    def type_text(self, text):
        self.calls.append(("type", text))

    def scroll(self, x, y, **kwargs):
        self.calls.append(("scroll", kwargs))

    def capture_screenshot(self, path, **kwargs):
        Path(path).write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="))

    def close_tab(self, tab):
        self.calls.append(("close", tab))


def test_one_owned_tab_supports_ax_interaction_and_actual_screenshot(isolated, monkeypatch, capsys):
    harness = Harness()
    monkeypatch.setitem(sys.modules, "browser_harness", SimpleNamespace(helpers=harness))
    worker._harness_dispatch({"budget_seconds": 30, "operations": [
        {"action": "open", "url": "https://example.com/collection"},
        {"action": "click", "node_id": 123},
        {"action": "fill", "node_id": 123, "text": "film"},
        {"action": "press", "key": "Enter"},
        {"action": "screenshot"},
        {"action": "close"},
    ]})
    report, done = worker._parse_events(capsys.readouterr().out)
    assert done and len(report["results"]) == 6
    assert all(result["ok"] for result in report["results"])
    first = report["results"][0]
    assert first["page_url"] == "https://example.com/collection"
    assert first["accessibility"] == [{"role": "button", "name": "Play", "node_id": 123}]
    assert first["links"] == [{"url": "https://artist.example/film", "text": "Film"}]
    assert first["embedded_players"] == [{"src": "https://player.vimeo.com/video/123456", "title": "Reference film"}]
    evidence = report["evidence"][0]
    assert evidence["mime_type"] == "image/png" and evidence["kind"] == "screenshot"
    assert Path(evidence["path"]).parent == isolated[1]
    assert Path(evidence["path"]).read_bytes().startswith(b"\x89PNG")
    assert sum(call[0] == "new_tab" for call in harness.calls) == 1
    assert ("Browser.setDownloadBehavior", {"behavior": "deny"}) in harness.calls
    assert not (isolated[0] / "tab.json").exists()


def test_later_request_reuses_owned_tab(isolated):
    harness = Harness()
    session = worker._Session(harness, worker.time.monotonic() + 30)
    session.perform({"action": "open", "url": "https://example.com/one"})
    restored = worker._Session(harness, worker.time.monotonic() + 30)
    restored.perform({"action": "open", "url": "https://example.com/two"})
    assert ("switch_tab", "owned-tab") in harness.calls
    assert ("goto_url", "https://example.com/two") in harness.calls
    assert sum(call[0] == "new_tab" for call in harness.calls) == 1


def test_credentials_fail_and_stop_later_batch_actions(isolated, monkeypatch, capsys):
    harness = Harness()
    monkeypatch.setitem(sys.modules, "browser_harness", SimpleNamespace(helpers=harness))
    worker._harness_dispatch({"budget_seconds": 30, "operations": [
        {"action": "open", "url": "https://example.com"},
        {"action": "fill", "node_id": 999, "text": "secret"},
        {"action": "press", "key": "Enter"},
    ]})
    report, done = worker._parse_events(capsys.readouterr().out)
    assert done and len(report["results"]) == 2
    assert not report["results"][1]["ok"]
    assert "credentials" in report["results"][1]["error"]
    assert not any(call[0] in {"type", "press"} for call in harness.calls)


@pytest.mark.parametrize("budget,expected_url", [
    (5, "https://example.com/film"), (0.6, "https://example.com/collection")
])
def test_link_snapshot_waits_for_delayed_navigation_within_batch_budget(isolated, monkeypatch, budget, expected_url):
    """A delayed site transition must not silently return the old collection."""
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: setattr(clock, "now", clock.now + seconds))

    class DelayedLinkHarness(Harness):
        pending = None

        def cdp(self, method, **kwargs):
            if method == "Runtime.callFunctionOn":
                return {"result": {"value": {"href": "https://example.com/film"}}}
            return super().cdp(method, **kwargs)

        def click_at_xy(self, x, y):
            self.pending = clock.now + 0.8

        def page_info(self):
            if self.pending is not None and clock.now >= self.pending:
                self.url = "https://example.com/film"
            return super().page_info()

    session = worker._Session(DelayedLinkHarness(), budget)
    session.perform({"action": "open", "url": "https://example.com/collection"})
    result = session.perform({"action": "click", "node_id": 123})
    assert result["page_url"] == expected_url
    assert clock.now <= budget
    if budget < 1:
        assert any("did not finish navigating" in note for note in session.limitations)
    else:
        assert clock.now >= 0.8
        assert not any("did not finish navigating" in note for note in session.limitations)


def test_video_without_real_decoded_frame_cannot_create_evidence(isolated):
    session = worker._Session(Harness(), worker.time.monotonic() + 30)
    session.perform({"action": "open", "url": "https://example.com"})
    result = session.perform({"action": "sample_video", "timestamps": [0, 1]})
    assert result["sampled_frames"] == 0
    assert result["ok"] is False and result["availability"] == "unavailable"
    assert not result["playback_verified"]
    assert session.evidence == []
    assert any("HTML5 video" in note for note in session.limitations)


def test_unavailable_sampling_keeps_earlier_evidence_and_stops_dependent_actions(isolated, monkeypatch, capsys):
    harness = Harness()
    monkeypatch.setitem(sys.modules, "browser_harness", SimpleNamespace(helpers=harness))
    worker._harness_dispatch({"budget_seconds": 30, "operations": [
        {"action": "open", "url": "https://example.com"},
        {"action": "screenshot"},
        {"action": "sample_video", "timestamps": [0]},
        {"action": "screenshot"},
    ]})
    report, done = worker._parse_events(capsys.readouterr().out)
    assert done and len(report["results"]) == 3
    assert report["results"][-1]["availability"] == "unavailable"
    assert report["results"][-1]["ok"] is False
    assert "No decoded video frames" in report["results"][-1]["error"]
    assert len(report["evidence"]) == 1
    assert any("HTML5 video" in note for note in report["limitations"])


def test_partial_sampling_retains_real_frame_without_claiming_all_samples(isolated):
    class PartialHarness(Harness):
        def js(self, expression):
            if expression == worker.PAGE_CONTENT_JS:
                return super().js(expression)
            if not self.video:
                self.video = True
                return {"ok": True, "timestamp_seconds": 0, "duration_seconds": 1}
            return {"ok": False, "reason": "The requested timestamp is outside the video duration."}

    session = worker._Session(PartialHarness(), worker.time.monotonic() + 30)
    session.perform({"action": "open", "url": "https://example.com"})
    result = session.perform({"action": "sample_video", "timestamps": [0, 2]})
    assert result["ok"] and result["availability"] == "partial"
    assert result["sampled_frames"] == len(session.evidence) == 1
    assert not result["playback_verified"]
    assert any("outside the video duration" in note for note in session.limitations)


def test_sampled_frame_records_requested_and_actual_time(isolated):
    harness = Harness()
    harness.video = {"ok": True, "timestamp_seconds": 2.01, "duration_seconds": 12}
    session = worker._Session(harness, worker.time.monotonic() + 30)
    session.perform({"action": "open", "url": "https://example.com"})
    result = session.perform({"action": "sample_video", "timestamps": [2]})
    assert result["sampled_frames"] == 1
    frame = session.evidence[0]
    assert frame["kind"] == "video_frame"
    assert frame["requested_timestamp_seconds"] == 2 and frame["timestamp_seconds"] == 2.01
    assert Path(frame["path"]).is_file()
    assert any("continuous playback" in note for note in session.limitations)


@pytest.mark.parametrize("loads", [True, False])
def test_sampling_waits_for_lazy_metadata_and_first_decoded_frame_within_budget(isolated, loads):
    """Execute the real page expression across loadedmetadata then loadeddata."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to execute the browser JavaScript regression")

    class LoadingHarness(Harness):
        diagnostics = None

        def js(self, expression):
            if expression == worker.PAGE_CONTENT_JS:
                return super().js(expression)
            setup = """
              const listeners=new Map(); let loadCalls=0;
              const emit=name=>[...(listeners.get(name)||[])].forEach(f=>f());
              const video={duration:NaN,readyState:0,currentTime:0,
                pause(){},scrollIntoView(){},
                load(){
                  loadCalls++;
                  if(LOADS) {
                    setTimeout(()=>{this.duration=12;this.readyState=1;emit('loadedmetadata');},30);
                    setTimeout(()=>{this.readyState=4;emit('loadeddata');},60);
                  }
                },
                addEventListener(name,fn){if(!listeners.has(name)) listeners.set(name,new Set());listeners.get(name).add(fn);},
                removeEventListener(name,fn){listeners.get(name)?.delete(fn);},
                getBoundingClientRect(){return {width:200,height:100,bottom:200,right:300,top:100,left:100};},
                checkVisibility(){return true;}
              };
              global.document={querySelectorAll:()=>[video]};
              global.innerWidth=1280;global.innerHeight=900;
              global.requestAnimationFrame=callback=>callback();
              const started=performance.now();
            """.replace("LOADS", json.dumps(loads))
            program = setup + "\nPromise.resolve(" + expression + ").then(result=>process.stdout.write(JSON.stringify({result,loadCalls,elapsed:performance.now()-started})));"
            completed = subprocess.run([node, "-e", program], capture_output=True, text=True, timeout=2, check=True)
            self.diagnostics = json.loads(completed.stdout)
            return self.diagnostics["result"]

    harness = LoadingHarness()
    session = worker._Session(harness, worker.time.monotonic() + 0.8)
    session.perform({"action": "open", "url": "https://example.com"})
    result = session.perform({"action": "sample_video", "timestamps": [0]})
    assert result["sampled_frames"] == int(loads)
    assert result["ok"] == loads
    assert harness.diagnostics["loadCalls"] == 1
    assert harness.diagnostics["elapsed"] < 750
    if loads:
        assert harness.diagnostics["elapsed"] >= 50
        assert session.evidence[0]["timestamp_seconds"] == 0
    else:
        assert any("metadata is unavailable" in note for note in session.limitations)


@pytest.mark.parametrize("visible", [False, True])
def test_video_sampling_checks_css_visibility_before_emitting_frame(isolated, visible):
    """Execute the trusted page expression: geometry alone cannot prove visibility."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to execute the browser JavaScript regression")

    class VideoHarness(Harness):
        def js(self, expression):
            if expression == worker.PAGE_CONTENT_JS:
                return super().js(expression)
            setup = """
              const video={duration:12,readyState:4,currentTime:2,
                pause(){},scrollIntoView(){},addEventListener(){},removeEventListener(){},
                getBoundingClientRect(){return {width:200,height:100,bottom:200,right:300,top:100,left:100};},
                checkVisibility(options){
                  if(!options.checkOpacity||!options.checkVisibilityCSS) throw Error('Missing CSS visibility checks');
                  return VISIBLE;
                }};
              global.document={querySelectorAll:()=>[video]};
              global.innerWidth=1280;global.innerHeight=900;
              global.requestAnimationFrame=callback=>callback();
            """.replace("VISIBLE", json.dumps(visible))
            program = setup + "\nPromise.resolve(" + expression + ").then(result=>process.stdout.write(JSON.stringify(result)));"
            completed = subprocess.run([node, "-e", program], capture_output=True, text=True, timeout=5, check=True)
            return json.loads(completed.stdout)

    session = worker._Session(VideoHarness(), worker.time.monotonic() + 30)
    session.perform({"action": "open", "url": "https://example.com"})
    result = session.perform({"action": "sample_video", "timestamps": [2]})
    assert result["sampled_frames"] == int(visible)
    assert len(session.evidence) == int(visible)
    if not visible:
        assert any("CSS-hidden" in note for note in session.limitations)


def test_failed_sampling_still_closes_but_never_runs_later_page_interactions(isolated, monkeypatch, capsys):
    harness = Harness()
    monkeypatch.setitem(sys.modules, "browser_harness", SimpleNamespace(helpers=harness))
    worker._harness_dispatch({"budget_seconds": 30, "operations": [
        {"action": "open", "url": "https://example.com"},
        {"action": "sample_video", "timestamps": [0]},
        {"action": "click", "node_id": 123}, {"action": "close"},
    ]})
    report, done = worker._parse_events(capsys.readouterr().out)
    assert done and [item["action"] for item in report["results"]] == ["open", "sample_video", "close"]
    assert report["results"][1]["ok"] is False
    assert report["results"][2] == {"action": "close", "ok": True, "closed": True}
    assert ("close", "owned-tab") in harness.calls
    assert not any(item[0] == "click" for item in harness.calls)
    assert not (isolated[0] / "tab.json").exists()


def test_sample_in_new_session_explicitly_requires_open(isolated, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "browser_harness", SimpleNamespace(helpers=Harness()))
    worker._harness_dispatch({"budget_seconds": 30, "operations": [{"action": "sample_video", "timestamps": [0]}]})
    report, _ = worker._parse_events(capsys.readouterr().out)
    assert report["results"][0]["requires_open"] is True
    assert report["results"][0]["ok"] is False


@pytest.mark.parametrize("visible", [True, False])
def test_sampling_scrolls_only_selected_video_and_never_substitutes_related_clip(isolated, visible):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for browser JavaScript regression")

    class OffscreenHarness(Harness):
        diagnostics = None

        def js(self, expression):
            if expression == worker.PAGE_CONTENT_JS:
                return super().js(expression)
            setup = """
              let scrolled=0;
              const related={checkVisibility(){throw Error('Wrong video selected');}};
              const selected={duration:12,readyState:4,currentTime:2,currentSrc:'https://cdn.example/chosen.webm',
                pause(){},addEventListener(){},removeEventListener(){},
                checkVisibility(){return VISIBLE;},
                scrollIntoView(options){if(options.block!=='center')throw Error('Wrong alignment');scrolled++;},
                getBoundingClientRect(){const top=scrolled?100:2000;return {width:200,height:100,top,bottom:top+100,right:300,left:100};}};
              global.document={querySelectorAll:()=>[related,selected]};
              global.innerWidth=1280;global.innerHeight=900;global.requestAnimationFrame=cb=>cb();
            """.replace("VISIBLE", json.dumps(visible))
            program = setup + "\nPromise.resolve(" + expression + ").then(result=>process.stdout.write(JSON.stringify({result,scrolled})));"
            completed = subprocess.run([node, "-e", program], capture_output=True, text=True, check=True, timeout=5)
            self.diagnostics = json.loads(completed.stdout)
            return self.diagnostics["result"]

    harness = OffscreenHarness()
    session = worker._Session(harness, worker.time.monotonic() + 30)
    session.perform({"action": "open", "url": "https://example.com"})
    result = session.perform({"action": "sample_video", "timestamps": [2], "video_index": 1})
    assert result["sampled_frames"] == int(visible)
    assert harness.diagnostics["scrolled"] == int(visible)
    if visible:
        assert session.evidence[0]["video_index"] == 1
        assert session.evidence[0]["video_src"] == "https://cdn.example/chosen.webm"


def test_cli_gets_only_fixed_dispatch_and_encoded_data(isolated, monkeypatch):
    monkeypatch.setattr(worker, "_ensure_browser", lambda _: None)
    monkeypatch.setattr(worker.shutil, "which", lambda _: "/trusted/browser-harness")
    calls = []
    attack_text = "'); __import__('os').system('bad'); #"

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=worker.EVENT_PREFIX + '{"done":true}\n', stderr="")

    monkeypatch.setattr(worker.subprocess, "run", runner)
    result = worker.run_request({"operations": [{"action": "fill", "node_id": 123, "text": attack_text}]})
    assert "error" not in result
    command, options = calls[0]
    assert command == ["/trusted/browser-harness"]
    assert attack_text not in options["input"]
    assert "_harness_dispatch(json.loads(base64.b64decode(" in options["input"]
    assert options["timeout"] <= 31
    assert options["env"]["BU_CDP_URL"] == worker.CDP_URL


def test_hard_timeout_retains_only_completed_results(isolated, monkeypatch):
    monkeypatch.setattr(worker, "_ensure_browser", lambda _: None)
    monkeypatch.setattr(worker.shutil, "which", lambda _: "/trusted/browser-harness")
    partial = (worker.EVENT_PREFIX + json.dumps({"result": {
        "action": "open", "ok": True, "page_url": "https://example.com"
    }}) + "\n").encode()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=30, output=partial)

    monkeypatch.setattr(worker.subprocess, "run", timeout)
    report = worker.run_request({"operations": [
        {"action": "open", "url": "https://example.com"}, {"action": "screenshot"}
    ]})
    assert len(report["results"]) == 1 and report["evidence"] == []
    assert report["incomplete_operations"] == 1
    assert any("time budget" in note for note in report["limitations"])


def test_large_unicode_snapshot_is_bounded_without_losing_evidence(capsys):
    evidence = {"path": "/workspace/reference-evidence/frame.png", "mime_type": "image/png"}
    worker._emit_event({"result": {"text": "影" * 500_000, "links": []}, "evidence": [evidence]})
    output = capsys.readouterr().out
    assert len(output.encode()) < worker.MAX_OUTPUT_BYTES // 7 + 100
    report, _ = worker._parse_events(output)
    assert report["results"][0]["output_truncated"]
    assert report["evidence"] == [evidence]


def social_metadata_fixture(*, url, canonical=None, schemas=(), meta=None, tiktok=None, tweets=()):
    """Execute production extraction against bounded, post-scoped DOM fixtures."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for public social metadata regression")
    payload = {"url": url, "canonical": canonical if canonical is not None else url,
               "schemas": list(schemas), "meta": meta or {}, "tiktok": tiktok or {}, "tweets": list(tweets)}
    setup = r"""
      const f=FIXTURE;
      const element=(text,attrs={})=>({innerText:text,content:text,textContent:text,...attrs,
        checkVisibility(){return attrs.visible!==false;},getAttribute(key){return attrs[key]||null;}});
      const articles=f.tweets.map(tweet=>{
        const article=element('');
        const time=element('',{dateTime:'2026-01-01T00:00:00Z',closest:()=>({href:tweet.url})});
        article.querySelector=selector=>selector==='time'?time:null;
        article.querySelectorAll=selector=>{
          const match=selector.match(/^\[data-testid="([^"]+)"\]$/);
          if(match&&tweet[match[1]]!==undefined){const item=element(tweet[match[1]],{closest:()=>article});return[item];}
          return [];
        };
        return article;
      });
      global.location={href:f.url};
      global.document={querySelectorAll(selector){
        if(selector==='link[rel="canonical"]')return f.canonical?[element('',{href:f.canonical})]:[];
        if(selector==='script[type="application/ld+json"]')return f.schemas.map(value=>element(typeof value==='string'?value:JSON.stringify(value)));
        if(selector==='article[data-testid="tweet"]')return articles;
        const meta=selector.match(/^meta\[property="([^"]+)"\]/);
        if(meta&&f.meta[meta[1]]!==undefined)return[element(f.meta[meta[1]])];
        const tik=selector.match(/^\[data-e2e="([^"]+)"\]$/);
        if(tik&&f.tiktok[tik[1]]!==undefined)return[].concat(f.tiktok[tik[1]]).map(value=>element(value));
        return [];
      }};
      Object.defineProperty(document,'cookie',{get(){throw Error('Cookies must not be read');}});
      global.fetch=()=>{throw Error('No network requests are allowed');};
    """.replace("FIXTURE", json.dumps(payload))
    completed = subprocess.run([node, "-e", setup + "\nprocess.stdout.write(JSON.stringify(" + worker.SOCIAL_METADATA_JS + "));"],
                               capture_output=True, text=True, check=True, timeout=5)
    return json.loads(completed.stdout)


def test_social_json_ld_counts_require_exact_post_identity_and_preserve_abbreviations():
    page = "https://www.youtube.com/watch?v=abcdefghijk"
    result = social_metadata_fixture(url=page, schemas=[{"@graph": [
        {"@type": "VideoObject", "url": "https://www.youtube.com/watch?v=ABCDEFGHIJK", "interactionStatistic": {
            "interactionType": "https://schema.org/WatchAction", "userInteractionCount": 999999}},
        {"@type": "VideoObject", "url": page, "name": "Actual post", "author": {"name": "Actual creator"},
         "uploadDate": "2026-01-01", "interactionStatistic": [
             {"interactionType": {"@type": "WatchAction"}, "userInteractionCount": 12345},
             {"interactionType": "https://schema.org/LikeAction", "userInteractionCount": "1.2K"},
         ]},
    ]}])
    assert result["platform"] == "youtube" and result["post_id"] == "abcdefghijk"
    assert result["post_verified"] is True
    assert result["title"] == "Actual post" and result["creator"] == "Actual creator"
    assert result["metrics"]["views"]["value"] == 12345
    assert result["metrics"]["views"]["source"] == "json_ld"
    assert result["metrics"]["likes"]["value"] is None
    assert result["metrics"]["likes"]["display"] == "1.2K"
    assert result["metrics"]["comments"] is None


def test_social_metadata_rejects_canonical_mismatch_instead_of_stale_post_counts():
    result = social_metadata_fixture(url="https://www.youtube.com/watch?v=abcdefghijk",
                                     canonical="https://www.youtube.com/watch?v=ABCDEFGHIJK",
                                     meta={"video:views": "12345"})
    assert all(value is None for value in result["metrics"].values())
    assert result["post_verified"] is False
    assert any("canonical identity differs" in note for note in result["limitations"])


def test_social_metadata_ignores_large_schema_and_unsupported_listing_pages():
    assert social_metadata_fixture(url="https://www.youtube.com/results?search_query=motion") is None
    page = "https://www.tiktok.com/@artist/video/1234567890"
    schema = {"@type": "VideoObject", "url": page, "description": "x" * 65536,
              "interactionStatistic": {"interactionType": "WatchAction", "userInteractionCount": 99999}}
    result = social_metadata_fixture(url=page, schemas=[schema])
    assert all(value is None for value in result["metrics"].values())
    assert any("unknown, not zero" in note for note in result["limitations"])


def test_tiktok_counts_use_unique_public_post_controls_and_do_not_infer_views():
    result = social_metadata_fixture(url="https://www.tiktok.com/@artist/video/1234567890", tiktok={
        "browse-like-count": "1.2K", "browse-comment-count": "45", "browse-share-count": ["12", "998"],
        "browse-username": "artist",
    })
    assert result["post_verified"] is True
    assert result["metrics"]["likes"]["display"] == "1.2K"
    assert result["metrics"]["likes"]["value"] is None
    assert result["metrics"]["comments"]["value"] == 45
    assert result["metrics"]["shares"] is None  # More than one candidate is ambiguous.
    assert result["metrics"]["views"] is None
    assert "browse-like-count" in result["visible_text"]


def test_x_counts_belong_to_exact_post_not_recommended_tweet():
    result = social_metadata_fixture(url="https://x.com/artist/status/1234567890", tweets=[
        {"url": "https://x.com/other/status/9999999999", "like": "99000", "reply": "100"},
        {"url": "https://x.com/artist/status/1234567890", "tweetText": "Our new film", "like": "14", "reply": "2", "retweet": "3"},
    ])
    assert result["post_verified"] is True
    assert result["metrics"]["likes"]["value"] == 14
    assert result["metrics"]["comments"]["value"] == 2
    assert result["metrics"]["shares"]["value"] == 3
    assert result["metrics"]["views"] is None
    assert result["published_at"] == "2026-01-01T00:00:00Z"


@pytest.mark.parametrize("url,fields", [
    ("https://www.youtube.com/watch?v=abcdefghijk", {"meta": {"video:views": "12345"}}),
    ("https://www.tiktok.com/@artist/video/1234567890", {"tiktok": {"browse-like-count": "998"}}),
    ("https://x.com/artist/status/1234567890", {"tweets": [
        {"url": "https://x.com/artist/status/1234567890", "like": "99"},
    ]}),
])
def test_social_post_url_and_counts_do_not_verify_missing_post_content(url, fields):
    result = social_metadata_fixture(url=url, **fields)
    assert result["post_verified"] is False
    assert all(value is None for value in result["metrics"].values())
    assert result["visible_text"] == ""
    assert any("Post content could not be verified" in note for note in result["limitations"])
