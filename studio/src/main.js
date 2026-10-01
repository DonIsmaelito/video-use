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
  selectedVersion: null,
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
  return `<header><a class="brand" href="/"><span class="brand-mark">◈</span> video-use</a><nav>${state.member ? button("Creations", "projects", "quiet") + button("Connect", "connect", "quiet") : ""}${state.user ? `<details class="account-menu"><summary aria-label="Account menu">•••</summary><div>${state.member?.is_owner ? button("Manage access", "admin", "quiet") : ""}${button("Sign out", "signout", "quiet")}</div></details>` : ""}</nav></header>`;
}
function welcome() {
  return `<section class="welcome"><div><span class="eyebrow">Video, by conversation</span><h1>Your ideas.<br><em>In motion.</em></h1><p class="intro">Create with Claude or ChatGPT. Watch it here.</p></div><form id="signin" class="card signin"><h2>${state.otpEmail ? "Check your inbox" : "Welcome back"}</h2>${state.otpEmail ? `<p>Enter the code sent to ${esc(state.otpEmail)}.</p><label class="sr-only" for="otp">Email code</label><input id="otp" name="otp" placeholder="Six-digit code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" required autofocus>` : '<label class="sr-only" for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" placeholder="Your email" required>'}<button ${state.busy ? "disabled" : ""}>${state.busy ? "Please wait…" : state.otpEmail ? "Continue" : "Continue with email"}</button>${state.otpEmail ? button("Use another email", "reset-email", "quiet") : ""}</form></section>`;
}
function invite() {
  return `<section class="narrow card"><h1>You're invited.</h1><p>Enter the shared code from your host.</p><form id="join"><label class="sr-only" for="invite-code">Invitation code</label><input id="invite-code" name="code" type="password" placeholder="Invitation code" required autocomplete="off"><button ${state.busy ? "disabled" : ""}>Open Studio</button></form></section>`;
}
function connect() {
  const url = state.config?.mcp_url || API + "/mcp";
  return `<section class="narrow connect"><div class="page-heading"><span class="eyebrow">One connection. Every creation.</span><h1>Choose your assistant.</h1></div><div class="card"><div class="copyline"><code>${esc(url)}</code>${button("Copy link", "copy-url", "small")}</div><div class="connection-grid"><details><summary>Claude <span>↗</span></summary><ol><li>Open Customize → Connectors.</li><li>Add a custom connector with the link above.</li><li>Sign in to video-use and allow access.</li></ol><a href="https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp" target="_blank" rel="noreferrer">Setup guide ↗</a></details><details><summary>ChatGPT <span>↗</span></summary><ol><li>Enable developer mode in Settings → Security and login.</li><li>In Plugins, add the link above with OAuth.</li><li>Sign in to video-use and allow access.</li><li>Choose video-use in a new chat.</li></ol><a href="https://developers.openai.com/plugins/deploy/connect-chatgpt" target="_blank" rel="noreferrer">Setup guide ↗</a></details></div></div></section>`;
}
function dashboard() {
  return `<section><div class="page-heading"><span class="eyebrow">Your studio</span><h1>Creations</h1></div>${state.projects.length ? `<div class="project-grid">${state.projects.map((p) => `<button class="project-card" data-project="${esc(p.id)}"><div class="project-cover">${p.cover_url ? `<video muted playsinline preload="metadata" src="${esc(p.cover_url)}#t=0.2" tabindex="-1"></video>` : '<span class="project-symbol">▷</span>'}<span class="play-symbol">↗</span></div><div class="project-caption"><h2>${esc(p.title)}</h2><span>${new Date(p.created).toLocaleDateString()}</span></div></button>`).join("")}</div>` : `<div class="empty"><span class="empty-symbol">◈</span><h2>Your next idea belongs here.</h2><p>Ask your assistant to make a video.</p>${button("Connect your assistant", "connect")}</div>`}<details class="new-project-disclosure"><summary>New project +</summary><form class="new-project" id="new-project"><label class="sr-only" for="title">Project title</label><input id="title" name="title" placeholder="Project name" maxlength="120" required><button ${state.busy ? "disabled" : ""}>Create</button></form></details></section>`;
}
function versions(p) {
  return [
    ...(p.previews || []).map((v) => ({
      id: v.id,
      url: v.preview.url,
      type: v.preview.media_type,
      label: v.stage,
      created: v.at,
    })),
    ...p.revisions.map((r, i) => ({
      id: r.id,
      url: r.video_url,
      type: "video/mp4",
      label: i === 0 ? "Final" : "Version " + (p.revisions.length - i),
      source: r.source_url,
      created: r.created,
    })),
  ].sort((a, b) => new Date(b.created) - new Date(a.created));
}
function project() {
  const p = state.project,
    items = versions(p);
  const chosen = items.find((v) => v.id === state.selectedVersion) || items[0];
  const active = p.tasks.find((t) => ["running", "queued"].includes(t.status));
  return `<section class="project-page"><div class="page-heading"><span class="eyebrow">${active ? "Creating" : "Your creation"}</span><h1>${esc(p.title)}</h1></div><div class="hero-player">${chosen ? (chosen.type.startsWith("image/") ? `<img src="${esc(chosen.url)}" alt="${esc(chosen.label)} preview">` : `<video controls playsinline preload="metadata" src="${esc(chosen.url)}"></video>`) : `<div class="empty"><span class="empty-symbol">▷</span><p>${active ? "Your preview is on its way." : "Your creation will appear here."}</p></div>`}</div><div class="player-bar"><div class="versions">${items.map((v) => `<button class="quiet small ${v.id === chosen?.id ? "selected" : ""}" data-version="${esc(v.id)}">${esc(v.label)}</button>`).join("")}</div>${chosen ? `<a class="download-link" href="${esc(chosen.url)}" target="_blank" rel="noreferrer">${chosen.type.startsWith("image/") ? "Open image" : "Download video"} ↓</a>` : ""}</div><div class="project-options"><details class="drawer"><summary>Files <span>${p.media.length || "+"}</span></summary><form id="upload"><label class="upload-zone"><span>Media, documents, data or 3D assets · up to 200 MB</span><input name="file" type="file" accept="${esc((state.config?.source_extensions || []).join(","))}" required></label><button ${state.busy ? "disabled" : ""}>${state.busy ? "Uploading…" : "Upload"}</button></form><ul class="media-list">${p.media.map((m) => `<li>${esc(m.name)}<small>${bytes(m.size)}</small></li>`).join("")}</ul>${chosen?.source ? `<a class="source-link" href="${esc(chosen.source)}">Editable source ↓</a>` : ""}</details><details class="drawer"><summary>Activity <span>${active ? "In progress" : p.tasks.length}</span></summary>${
    p.tasks
      .slice(0, 10)
      .map(
        (t) =>
          `<details class="task" data-task="${esc(t.id)}"><summary>${esc(t.operation)}<span class="status ${esc(t.status)}">${esc(t.status)}</span></summary>${t.error ? `<p class="error">${esc(t.error)}</p>` : ""}<pre class="logs">Loading…</pre>${["queued", "running"].includes(t.status) ? `<button class="quiet" data-cancel="${esc(t.id)}">Cancel task</button>` : ""}</details>`,
      )
      .join("") || "<p>No activity yet.</p>"
  }</details></div></section>`;
}
function admin() {
  return `<section class="narrow"><p class="eyebrow">Owner controls</p><h1>Manage the pilot</h1><div class="card"><h2>Access and usage</h2><div class="actions">${button("Rotate invitation code", "rotate", "quiet")}${button(state.admin.paused ? "Resume execution" : "Pause new execution", "pause", "quiet")}</div>${state.admin.code ? `<p class="notice">New code: <code>${esc(state.admin.code)}</code><br>Copy it now. It is only displayed once.</p>` : ""}${state.admin.members.map((m) => `<div class="member"><span>${esc(m.email)}<small>${m.is_owner ? "Owner" : m.active ? "Active" : "Revoked"}</small></span>${!m.is_owner && m.active ? `<button class="quiet" data-revoke="${esc(m.id)}">Revoke</button>` : ""}</div>`).join("")}<h2>Current usage</h2><pre>${esc(JSON.stringify(state.admin.usage, null, 2))}</pre></div></section>`;
}
function render() {
  root.innerHTML =
    header() +
    `<main>${state.error ? `<div class="notice error" role="alert">${esc(state.error)}</div>` : ""}${!state.user ? welcome() : !state.member ? invite() : state.admin ? admin() : query.has("connect") ? connect() : state.project ? project() : dashboard()}</main>`;
  bind();
}
function bind() {
  root.querySelectorAll("[data-version]").forEach(
    (el) =>
      (el.onclick = () => {
        state.selectedVersion = el.dataset.version;
        render();
      }),
  );
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
          state.selectedVersion = null;
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
        [...root.querySelectorAll("video")].some(
          (v) => !v.paused && !v.ended,
        ) ||
        state.busy ||
        !state.member ||
        query.has("authorize") ||
        document.activeElement?.closest("form") ||
        root.querySelector('input[type="file"]')?.files?.length
      )
        return;
      try {
        if (!state.project) {
          if (state.admin || query.has("connect")) return;
          const projects = await api("/api/projects");
          const signature = rows => JSON.stringify(rows.map(p => [p.id, p.title, p.cover]));
          if (signature(projects) !== signature(state.projects)) {
            state.projects = projects;
            render();
          }
          return;
        }
        const signature = (p) =>
          JSON.stringify([
            p.tasks.map((t) => [t.id, t.status, t.updated]),
            p.revisions.map((r) => r.id),
            p.media.map((m) => m.id),
            (p.previews || []).map((v) => v.id),
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
