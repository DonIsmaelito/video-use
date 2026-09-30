import { createClient } from "@insforge/sdk";
import "./style.css";
const client = createClient({
  baseUrl: window.location.origin,
  anonKey: import.meta.env.VITE_INSFORGE_ANON_KEY,
});
const API = import.meta.env.VITE_API_URL;
const root = document.querySelector("#app");
const esc = (s = "") =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const state = {
  user: null,
  member: null,
  projects: [],
  project: null,
  config: null,
  otpEmail: null,
  error: "",
  busy: false,
  admin: null,
  usage: [],
  generation: 0,
};
const query = new URLSearchParams(location.search);
let timer = null;
async function api(path, options = {}) {
  const token = await client.getHttpClient().getValidAccessToken();
  const r = await fetch(API + path, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...options.headers,
    },
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(data.detail || "Something went wrong. Please try again.");
  return data;
}
async function action(fn) {
  state.error = "";
  state.busy = true;
  render();
  try {
    await fn();
  } catch (e) {
    state.error = e.message;
  } finally {
    state.busy = false;
    render();
    if (query.has("authorize") && state.member) {
      try {
        await consentIfNeeded();
      } catch (e) {
        state.error = e.message;
        render();
      }
    }
  }
}
function bytes(n) {
  return n > 1e9 ? (n / 1e9).toFixed(1) + " GB" : (n / 1e6).toFixed(1) + " MB";
}
function navigate(pid) {
  query.delete("connect");
  if (pid) query.set("project", pid);
  else query.delete("project");
  history.replaceState(
    {},
    "",
    location.pathname + (query.size ? "?" + query : ""),
  );
}
async function loadProject(pid) {
  const generation = ++state.generation;
  const p = await api("/api/projects/" + encodeURIComponent(pid));
  if (generation === state.generation) state.project = p;
}
async function refresh() {
  const me = await api("/api/me");
  state.member = me.member;
  if (!me.member) return;
  state.projects = await api("/api/projects");
  state.usage = await api("/api/usage");
  if (query.get("project")) await loadProject(query.get("project"));
}
function button(label, action, klass = "") {
  return `<button type="button" data-action="${action}" class="${klass}" ${state.busy ? "disabled" : ""}>${label}</button>`;
}
function header() {
  return `<header><a class="brand" href="/">video-use<span>studio</span></a><nav>${state.member ? button("Connect your assistant", "connect", "quiet") + button("Projects", "projects", "quiet") : ""}${state.member?.is_owner ? button("Manage pilot", "admin", "quiet") : ""}${state.user ? button("Sign out", "signout", "quiet") : ""}<span class="badge">Private pilot</span></nav></header>`;
}
function welcome() {
  return `<section class="welcome"><div><p class="eyebrow">Your ideas. Your assistant. Your video.</p><h1>Make something<br><em>worth watching.</em></h1><p class="intro">Create and edit videos from your Claude or ChatGPT conversation. Keep your footage, previews, and finished work here.</p><div class="steps"><p><b>01</b> Sign in with your invitation</p><p><b>02</b> Connect your assistant</p><p><b>03</b> Make, review, and refine</p></div></div><form id="signin" class="card signin"><span class="eyebrow">Welcome to your workspace</span><h2>${state.otpEmail ? "Check your inbox" : "A place for your next idea"}</h2><p>${state.otpEmail ? "Enter the six-digit code sent to " + esc(state.otpEmail) + "." : "Use your email to get started. You’ll enter your invitation code after signing in."}</p>${state.otpEmail ? '<label>Email code<input name="otp" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" required autofocus></label>' : '<label>Email address<input name="email" type="email" autocomplete="email" placeholder="you@company.com" required></label>'}<button ${state.busy ? "disabled" : ""}>${state.busy ? "Please wait…" : state.otpEmail ? "Open workspace" : "Send sign-in code"} <span>↗</span></button>${state.otpEmail ? button("Use another email", "reset-email", "quiet") : ""}<small>Your assistant account stays yours. Compute and speech are provided for this pilot.</small></form></section>`;
}
function invite() {
  return `<section class="narrow card"><span class="eyebrow">One more step</span><h1>Your invitation</h1><p>Signed in as ${esc(state.user.email)}. Enter the shared code from your host.</p><form id="join"><label>Invitation code<input name="code" type="password" required autocomplete="off"></label><button ${state.busy ? "disabled" : ""}>Join the pilot ↗</button></form></section>`;
}
function connect() {
  const url = state.config?.mcp_url || API + "/mcp";
  return `<section class="narrow"><p class="eyebrow">Bring your own assistant</p><h1>Connect once.<br><em>Keep creating.</em></h1><div class="card"><label>Connector URL</label><div class="copyline"><code>${esc(url)}</code>${button("Copy", "copy-url", "small")}</div><div class="connection-grid"><div><h2>Claude</h2><ol><li>Open Customize → Connectors.</li><li>Add a custom connector and paste the URL.</li><li>Sign in here and allow access.</li><li>Enable video-use in your conversation.</li></ol><a href="https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp" target="_blank" rel="noreferrer">Claude setup guide ↗</a></div><div><h2>ChatGPT</h2><ol><li>Enable developer mode in Settings → Security and login.</li><li>Open Plugins and add the connector URL using OAuth.</li><li>Sign in here and allow access.</li><li>Select video-use in a new chat.</li></ol><a href="https://developers.openai.com/plugins/deploy/connect-chatgpt" target="_blank" rel="noreferrer">ChatGPT setup guide ↗</a></div></div><p class="muted">Availability depends on your assistant’s account and workspace policies. No API key is needed.</p></div><div class="card starter"><span class="eyebrow">Your first prompt</span><p id="starter-prompt">Using video-use, create a project and make an eight-second typographic introduction for a coffee brand called Still Morning. Inspect the rendered frames before exporting.</p>${button("Copy prompt", "copy-prompt", "quiet")}</div></section>`;
}
function dashboard() {
  return `<section><div class="section-heading"><div><p class="eyebrow">Your workspace</p><h1>Projects</h1></div></div><form class="new-project card" id="new-project"><label class="sr-only" for="title">Project title</label><input id="title" name="title" placeholder="Give your next video a name" maxlength="120" required><button ${state.busy ? "disabled" : ""}>New project +</button></form>${state.projects.length ? `<div class="project-grid">${state.projects.map((p) => `<button class="project-card" data-project="${esc(p.id)}"><span class="project-symbol">▷</span><h2>${esc(p.title)}</h2><span>${new Date(p.created).toLocaleDateString()} <b>↗</b></span></button>`).join("")}</div>` : '<div class="empty"><span>▷</span><h2>Your first video starts here.</h2><p>Create a project, upload footage if you have it, and continue in your assistant.</p>' + button("Connect your assistant", "connect", "quiet") + "</div>"}<p class="muted">${state.usage.map((u) => `${esc(u.kind)}: ${u.kind === "storage" ? bytes(Number(u.amount)) : u.kind === "compute" ? Math.ceil(Number(u.amount) / 60) + " / 60 minutes" : u.amount}`).join(" · ") || "Your pilot allowance is ready."}</p></section>`;
}
function project() {
  const p = state.project;
  return `<section><div class="section-heading"><div><p class="eyebrow">Project workspace</p><h1>${esc(p.title)}</h1></div>${button("Copy editing prompt", "project-prompt", "quiet")}</div><div class="workspace-grid"><div><div class="card"><h2>Source material</h2><p>Upload footage, audio, or images. Your assistant can see these files in this project.</p><form id="upload"><label class="upload-zone">Choose a file<input name="file" type="file" accept="video/*,audio/*,image/png,image/jpeg,image/webp" required></label><button ${state.busy ? "disabled" : ""}>${state.busy ? "Working…" : "Upload file"}</button></form><small>Up to 200 MB per file. Original footage stays separate from your edits.</small><ul class="media-list">${p.media.map((m) => `<li><span>${esc(m.name)}</span><small>${bytes(m.size)}</small></li>`).join("")}</ul></div><div class="card"><h2>Activity</h2>${
    p.tasks.length
      ? p.tasks
          .slice(0, 10)
          .map(
            (t) =>
              `<details class="task" data-task="${esc(t.id)}"><summary><span>${esc(t.operation)}</span><span class="status ${esc(t.status)}">${esc(t.status)}</span></summary>${t.error ? `<p class="error">${esc(t.error)}</p>` : ""}<pre>${esc(JSON.stringify(t.result || {}, null, 2))}</pre><pre class="logs">Open to load task logs</pre>${["queued", "running"].includes(t.status) ? `<button class="quiet" data-cancel="${esc(t.id)}">Cancel task</button>` : ""}</details>`,
          )
          .join("")
      : '<p class="muted">Your assistant’s work will appear here.</p>'
  }</div></div><div class="outputs"><h2>Finished work</h2>${p.revisions.length ? p.revisions.map((r, i) => `<article class="card output"><div class="output-title"><span class="eyebrow">${i === 0 ? "Latest version" : "Earlier version"}</span><small>${new Date(r.created).toLocaleString()}</small></div><video controls preload="metadata" src="${esc(r.video_url)}"></video><p>${esc(r.summary)}</p><div class="downloads"><a href="${esc(r.video_url)}" target="_blank" rel="noreferrer">Open MP4 ↗</a><a href="${esc(r.source_url)}">Editable source ↓</a></div></article>`).join("") : '<div class="empty card"><span>▷</span><h2>From conversation to video.</h2><p>Ask your assistant to create, inspect, and export. Finished versions appear here.</p></div>'}</div></div></section>`;
}
function admin() {
  return `<section class="narrow"><p class="eyebrow">Owner controls</p><h1>Manage the pilot</h1><div class="card"><h2>Access and usage</h2><div class="actions">${button("Rotate invitation code", "rotate", "quiet")}${button(state.admin.paused ? "Resume execution" : "Pause new execution", "pause", "quiet")}</div>${state.admin.code ? `<p class="notice">New code: <code>${esc(state.admin.code)}</code><br>Copy it now. It is only displayed once.</p>` : ""}${state.admin.members.map((m) => `<div class="member"><span>${esc(m.email)}<small>${m.is_owner ? "Owner" : m.active ? "Active" : "Revoked"}</small></span>${!m.is_owner && m.active ? `<button class="quiet" data-revoke="${esc(m.id)}">Revoke</button>` : ""}</div>`).join("")}<h2>Current usage</h2><pre>${esc(JSON.stringify(state.admin.usage, null, 2))}</pre></div></section>`;
}
function render() {
  root.innerHTML =
    header() +
    `<main>${state.error ? `<div class="notice error" role="alert">${esc(state.error)}</div>` : ""}${!state.user ? welcome() : !state.member ? invite() : state.admin ? admin() : query.has("connect") ? connect() : state.project ? project() : dashboard()}</main><footer><span>video-use</span><span>Built for the conversation. Made for the screen.</span></footer>`;
  bind();
}
function bind() {
  root.querySelector("#signin")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    action(async () => {
      if (!state.otpEmail) {
        const email = form.get("email");
        const { error } = await client.auth.signInWithOtp({ email });
        if (error) throw error;
        state.otpEmail = email;
      } else {
        const { data, error } = await client.auth.verifyOtp({
          email: state.otpEmail,
          otp: form.get("otp"),
        });
        if (error) throw error;
        state.user = data.user;
        await refresh();
      }
    });
  });
  root.querySelector("#join")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const code = new FormData(e.target).get("code");
    action(async () => {
      await api("/api/join", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      await refresh();
      if (!query.has("authorize")) query.set("connect", "1");
    });
  });
  root.querySelector("#new-project")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const title = new FormData(e.target).get("title");
    action(async () => {
      const p = await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      navigate(p.id);
      await refresh();
    });
  });
  root.querySelector("#upload")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    const pid = state.project.id;
    action(async () => {
      if (data.get("file").size > 200000000)
        throw Error("Files must be at most 200 MB");
      await api("/api/projects/" + pid + "/upload", {
        method: "POST",
        body: data,
      });
      await loadProject(pid);
    });
  });
  root.querySelectorAll("[data-project]").forEach(
    (el) =>
      (el.onclick = () =>
        action(async () => {
          navigate(el.dataset.project);
          await loadProject(el.dataset.project);
        })),
  );
  root.querySelectorAll("[data-cancel]").forEach(
    (el) =>
      (el.onclick = () =>
        action(async () => {
          await api("/api/tasks/" + el.dataset.cancel + "/cancel", {
            method: "POST",
          });
          await loadProject(state.project.id);
        })),
  );
  root.querySelectorAll("[data-revoke]").forEach(
    (el) =>
      (el.onclick = () =>
        action(async () => {
          await api("/api/admin/members/" + el.dataset.revoke + "/revoke", {
            method: "POST",
          });
          state.admin = await api("/api/admin");
        })),
  );
  root.querySelectorAll("[data-task]").forEach(
    (el) =>
      (el.ontoggle = async () => {
        if (!el.open) return;
        try {
          const t = await api("/api/tasks/" + el.dataset.task);
          el.querySelector(".logs").textContent = t.events
            .map((x) => x.message)
            .reverse()
            .join("\n");
        } catch (e) {
          el.querySelector(".logs").textContent = e.message;
        }
      }),
  );
  root.querySelectorAll("[data-action]").forEach(
    (el) =>
      (el.onclick = () =>
        action(async () => {
          switch (el.dataset.action) {
            case "reset-email":
              state.otpEmail = null;
              break;
            case "signout":
              await client.auth.signOut();
              state.user = null;
              state.member = null;
              state.project = null;
              state.admin = null;
              break;
            case "connect":
              state.project = null;
              state.admin = null;
              navigate(null);
              query.set("connect", "1");
              break;
            case "projects":
              state.project = null;
              state.admin = null;
              navigate(null);
              await refresh();
              break;
            case "copy-url":
              await navigator.clipboard.writeText(state.config.mcp_url);
              break;
            case "copy-prompt":
              await navigator.clipboard.writeText(
                "Using video-use, create a project and make an eight-second typographic introduction for a coffee brand called Still Morning. Inspect the rendered frames before exporting.",
              );
              break;
            case "project-prompt":
              await navigator.clipboard.writeText(
                `Using video-use project ${state.project.id}, inspect my uploaded material and help me create an edit. Read the harness guidance, review the encoded frames, and export the result.`,
              );
              break;
            case "admin":
              state.admin = await api("/api/admin");
              break;
            case "rotate": {
              const { code } = await api("/api/admin/rotate-invite", {
                method: "POST",
              });
              state.admin.code = code;
              break;
            }
            case "pause":
              await api("/api/admin/pause", {
                method: "POST",
                body: JSON.stringify({ paused: !state.admin.paused }),
              });
              state.admin = await api("/api/admin");
              break;
          }
        })),
  );
}
async function consentIfNeeded() {
  if (!query.has("authorize") || !state.member) return;
  const rid = query.get("authorize");
  const info = await api("/api/consent/" + encodeURIComponent(rid));
  root.innerHTML =
    header() +
    `<main><section class="narrow card"><p class="eyebrow">Connect your assistant</p><h1>Allow ${esc(info.client_name)}?</h1><p>This connector can read your video projects and run editing tools using your pilot allowance.</p><div class="actions"><button id="allow">Allow access</button><button id="deny" class="quiet">Cancel</button></div><p id="consent-error" role="alert"></p></section></main>`;
  for (const [id, allow] of [
    ["allow", true],
    ["deny", false],
  ])
    document.getElementById(id).onclick = async () => {
      try {
        const { redirect_url } = await api(
          "/api/consent/" + encodeURIComponent(rid),
          { method: "POST", body: JSON.stringify({ allow }) },
        );
        location.assign(redirect_url);
      } catch (e) {
        document.querySelector("#consent-error").textContent = e.message;
      }
    };
}
async function boot() {
  root.innerHTML = '<main class="loading">Opening your workspace…</main>';
  try {
    state.config = await api("/api/config");
    const { data } = await client.auth.getCurrentUser();
    state.user = data?.user || null;
    if (state.user) await refresh();
    render();
    await consentIfNeeded();
    timer = setInterval(async () => {
      if (
        document.hidden ||
        state.busy ||
        !state.project ||
        query.has("authorize") ||
        document.activeElement?.closest("form") ||
        root.querySelector('input[type="file"]')?.files.length
      )
        return;
      try {
        const signature = (p) =>
          JSON.stringify([
            p.tasks.map((t) => [t.id, t.status, t.updated]),
            p.revisions.map((r) => r.id),
            p.media.map((m) => m.id),
          ]);
        const before = signature(state.project);
        await loadProject(state.project.id);
        if (before !== signature(state.project)) render();
      } catch (e) {
        state.error = e.message;
        render();
      }
    }, 8000);
  } catch (e) {
    state.error = e.message;
    render();
  }
}
boot();
