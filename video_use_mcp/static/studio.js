const $ = (id) => document.getElementById(id);
const state = {
  user: null,
  config: null,
  settings: null,
  project: null,
  job: null,
  signup: false,
  poll: null,
  videoJob: null,
  projectRequest: 0,
  jobRequest: 0,
  listRequest: 0,
};
let noticeTimer;
function notice(text, failure = false) {
  $("notice").textContent = text;
  $("notice").classList.toggle("failure", failure);
  $("notice").hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => ($("notice").hidden = true), 8000);
}
async function api(path, options = {}) {
  const headers = {
    "X-CSRF-Token": state.user?.csrf || "",
    ...options.headers,
  };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { ...options, headers });
  const value = await response.json();
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "Please check your inputs and try again.",
    );
  return value;
}
async function guarded(fn, button) {
  if (button) button.disabled = true;
  try {
    return await fn();
  } catch (error) {
    notice(error.message, true);
  } finally {
    if (button)
      button.disabled =
        button.id === "create-button" &&
        ["queued", "running", "cancelling"].includes(state.job?.status);
  }
}
function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function bytes(n) {
  return n < 1024 * 1024
    ? (n / 1024).toFixed(0) + " KB"
    : (n / 1024 / 1024).toFixed(1) + " MB";
}
function dialog(id) {
  $(id).showModal();
}
async function copy(value) {
  try {
    await navigator.clipboard.writeText(value);
    notice("Copied.");
  } catch {
    notice("Select the text and copy it manually.");
  }
}
document
  .querySelectorAll("[data-close]")
  .forEach((b) =>
    b.addEventListener("click", () => $(b.dataset.close).close()),
  );
function setAuthMode() {
  state.signup = !state.signup;
  $("auth-title").textContent = state.signup
    ? "A workspace of your own."
    : "Your next film starts here.";
  $("auth-kicker").textContent = state.signup
    ? "WELCOME TO VIDEO-USE"
    : "WELCOME BACK";
  $("auth-submit").textContent = state.signup
    ? "Create workspace →"
    : "Open workspace →";
  $("auth-toggle").textContent = state.signup
    ? "Sign in instead"
    : "Create an account";
  $("invite-label").hidden = !state.signup || !state.config.invite_required;
  $("password").autocomplete = state.signup
    ? "new-password"
    : "current-password";
}
$("auth-toggle").addEventListener("click", setAuthMode);
$("auth-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    await api(state.signup ? "/api/register" : "/api/login", {
      method: "POST",
      body: {
        username: $("username").value,
        password: $("password").value,
        invite_code: $("invite").value,
      },
    });
    $("password").value = "";
    await enterStudio();
  }, $("auth-submit"));
});
$("logout").addEventListener("click", () =>
  guarded(async () => {
    await api("/api/logout", { method: "POST" });
    location.assign("/");
  }),
);
async function enterStudio() {
  state.user = await api("/api/me");
  state.settings = await api("/api/settings");
  $("auth-screen").hidden = true;
  $("studio").hidden = false;
  $("nav").hidden = false;
  await refreshProjects();
  const consent = new URLSearchParams(location.search).get("authorize");
  if (consent) await showConsent(consent);
}
async function refreshProjects(preferredId = null) {
  const request = ++state.listRequest;
  const projects = await api("/api/projects");
  if (request !== state.listRequest) return;
  const list = $("project-list");
  list.replaceChildren();
  for (const project of projects) {
    const button = node("button", project.title, "project-link");
    button.dataset.id = project.id;
    button.addEventListener("click", () =>
      guarded(() => selectProject(project.id)),
    );
    list.append(button);
  }
  const wanted =
    preferredId ||
    state.project?.id ||
    new URLSearchParams(location.search).get("project");
  if (wanted && projects.some((p) => p.id === wanted)) {
    await selectProject(wanted);
  } else if (projects.length) {
    await selectProject(projects[0].id);
  } else {
    $("project-empty").hidden = false;
    $("project-panel").hidden = true;
  }
}
async function refreshCurrentProject(id) {
  const navigation = state.projectRequest;
  if (state.project?.id !== id) return false;
  const project = await api("/api/projects/" + id);
  if (state.project?.id !== id || navigation !== state.projectRequest)
    return false;
  state.project = project;
  return true;
}
async function selectProject(id) {
  clearTimeout(state.poll);
  const request = ++state.projectRequest;
  ++state.jobRequest;
  const changed = state.project?.id !== id;
  const project = await api("/api/projects/" + id);
  if (request !== state.projectRequest) return;
  state.project = project;
  if (changed) clearPreview();
  $("project-empty").hidden = true;
  $("project-panel").hidden = false;
  $("project-title").textContent = state.project.title;
  $("project-count").textContent =
    state.project.assets.length +
    " source" +
    (state.project.assets.length === 1 ? "" : "s");
  document
    .querySelectorAll(".project-link")
    .forEach((b) => b.classList.toggle("active", b.dataset.id === id));
  const url = new URL(location.href);
  url.searchParams.set("project", id);
  history.replaceState(null, "", url);
  $("key-hint").hidden = state.settings.key_configured;
  $("model-label").textContent = state.settings.key_configured
    ? state.settings.model
    : "Connect a model in Settings.";
  renderMedia();
  renderRevisions();
  const active = state.project.jobs.find((j) =>
    ["queued", "running", "cancelling"].includes(j.status),
  );
  const latest = active || state.project.jobs[0];
  if (latest) {
    await selectJob(latest.id);
  } else {
    state.job = null;
    clearPreview();
    $("job-panel").hidden = true;
    $("create-button").disabled = false;
  }
}
function clearPreview() {
  state.videoJob = null;
  $("player").pause();
  $("player").removeAttribute("src");
  $("player").hidden = true;
  $("preview-empty").hidden = false;
  $("result-actions").hidden = true;
  $("result-summary").textContent = "";
}
function renderMedia() {
  const list = $("media-list");
  list.replaceChildren();
  for (const asset of state.project.assets) {
    const li = node("li");
    const remove = node("button", "Remove", "quiet");
    remove.setAttribute("aria-label", "Remove " + asset.name);
    remove.addEventListener("click", () =>
      guarded(async () => {
        const pid = state.project.id;
        await api("/api/projects/" + pid + "/media/" + asset.id, {
          method: "DELETE",
        });
        if (!(await refreshCurrentProject(pid))) return;
        renderMedia();
        $("project-count").textContent =
          state.project.assets.length + " sources";
      }),
    );
    li.append(
      node("span", asset.name),
      node("span", bytes(asset.size)),
      remove,
    );
    list.append(li);
  }
}
$("delete-project").addEventListener("click", () =>
  guarded(async () => {
    if (
      !confirm(
        "Delete this project, its uploaded media, and all revisions? This cannot be undone.",
      )
    )
      return;
    await api("/api/projects/" + state.project.id, { method: "DELETE" });
    clearTimeout(state.poll);
    state.project = null;
    state.job = null;
    await refreshProjects();
    notice("Project deleted.");
  }),
);
function renderRevisions() {
  $("revisions-panel").hidden = !state.project.jobs.length;
  const list = $("revision-list");
  list.replaceChildren();
  [...state.project.jobs].reverse().forEach((job, i) => {
    const button = node(
      "button",
      "Revision " + (i + 1) + " · " + job.status,
      "revision-button",
    );
    button.dataset.id = job.id;
    button.addEventListener("click", () => guarded(() => selectJob(job.id)));
    list.append(button);
  });
}
async function selectJob(id) {
  clearTimeout(state.poll);
  const projectId = state.project.id;
  const request = ++state.jobRequest;
  let job;
  try {
    job = await api("/api/jobs/" + id);
  } catch (error) {
    if (state.project?.id === projectId && request === state.jobRequest)
      state.poll = setTimeout(() => guarded(() => selectJob(id)), 8000);
    throw error;
  }
  if (state.project?.id !== projectId || request !== state.jobRequest) return;
  state.job = job;
  renderJob(job);
  if (["queued", "running", "cancelling"].includes(job.status)) {
    state.poll = setTimeout(() => guarded(() => selectJob(id)), 4000);
  } else {
    if (
      !(await refreshCurrentProject(projectId)) ||
      request !== state.jobRequest
    )
      return;
    renderRevisions();
    document
      .querySelectorAll(".revision-button")
      .forEach((b) => b.classList.toggle("active", b.dataset.id === id));
  }
}
function renderJob(job) {
  $("job-panel").hidden = false;
  $("job-status").textContent =
    job.status === "succeeded" ? "Ready to watch" : job.status;
  $("cancel-job").hidden = !["queued", "running"].includes(job.status);
  $("create-button").disabled = ["queued", "running", "cancelling"].includes(
    job.status,
  );
  $("job-events").replaceChildren(
    ...job.events.slice(-12).map((e) => node("p", e.message)),
  );
  $("job-events").scrollTop = $("job-events").scrollHeight;
  $("job-error").hidden = !job.error;
  $("job-error").textContent = job.error || "";
  if (job.status === "succeeded") {
    const r = job.result;
    $("preview-empty").hidden = true;
    $("player").hidden = false;
    if (state.videoJob !== job.id) {
      $("player").src = r.video_url;
      state.videoJob = job.id;
    }
    $("result-actions").hidden = false;
    $("download-video").href = r.video_url;
    $("download-source").href = r.source_url;
    $("result-summary").textContent = r.summary;
  }
  document
    .querySelectorAll(".revision-button")
    .forEach((b) => b.classList.toggle("active", b.dataset.id === job.id));
}
function newProject() {
  $("new-title").value = "";
  dialog("project-dialog");
}
$("new-project").addEventListener("click", newProject);
$("first-project").addEventListener("click", newProject);
$("project-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    const p = await api("/api/projects", {
      method: "POST",
      body: { title: $("new-title").value.trim() },
    });
    ++state.projectRequest;
    ++state.jobRequest;
    state.project = p;
    $("project-dialog").close();
    $("brief").value = "";
    await refreshProjects(p.id);
  }, event.submitter);
});
$("brief-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    if (!state.settings.key_configured) {
      await openSettings();
      return;
    }
    const pid = state.project.id;
    const job = await api("/api/projects/" + pid + "/jobs", {
      method: "POST",
      body: { prompt: $("brief").value, request_id: crypto.randomUUID() },
    });
    if (!(await refreshCurrentProject(pid))) {
      notice("Production started. Open that project to follow its progress.");
      return;
    }
    renderRevisions();
    await selectJob(job.id);
    notice(
      "Your film is in production. You can leave this page and come back.",
    );
  }, event.submitter);
});
$("cancel-job").addEventListener("click", () =>
  guarded(async () => {
    const jid = state.job.id;
    await api("/api/jobs/" + jid + "/cancel", { method: "POST" });
    if (state.job?.id === jid) await selectJob(jid);
  }),
);
async function uploadFiles(files) {
  if (!state.project) return;
  const pid = state.project.id;
  $("upload-progress").hidden = false;
  try {
    for (const file of files) {
      $("upload-progress").textContent = "Uploading " + file.name + "…";
      if (file.size > state.config.max_upload_mb * 1024 * 1024)
        throw new Error(
          "Files must be smaller than " + state.config.max_upload_mb + " MB.",
        );
      const data = new FormData();
      data.append("file", file);
      await api("/api/projects/" + pid + "/media", {
        method: "POST",
        body: data,
      });
    }
    if (await refreshCurrentProject(pid)) {
      renderMedia();
      $("project-count").textContent = state.project.assets.length + " sources";
    }
    notice("Material added. Describe what you want to make.");
  } finally {
    $("upload-progress").hidden = true;
    $("media-input").value = "";
  }
}
$("media-input").addEventListener("change", (e) =>
  guarded(() => uploadFiles([...e.target.files])),
);
for (const name of ["dragenter", "dragover"])
  $("dropzone").addEventListener(name, (e) => {
    e.preventDefault();
    $("dropzone").classList.add("dragging");
  });
for (const name of ["dragleave", "drop"])
  $("dropzone").addEventListener(name, (e) => {
    e.preventDefault();
    $("dropzone").classList.remove("dragging");
  });
$("dropzone").addEventListener("drop", (e) =>
  guarded(() => uploadFiles([...e.dataTransfer.files])),
);
async function openSettings() {
  state.settings = await api("/api/settings");
  const s = state.settings;
  $("provider").value = s.provider;
  $("model").value = s.model;
  $("api-key").value = "";
  $("eleven-key").value = "";
  $("eleven-voice").value = s.elevenlabs_voice;
  $("key-state").textContent = s.key_configured ? "· saved securely" : "";
  $("eleven-state").textContent = s.elevenlabs_configured
    ? "· saved securely"
    : "";
  dialog("settings-dialog");
}
$("settings-button").addEventListener("click", () => guarded(openSettings));
$("key-settings").addEventListener("click", () => guarded(openSettings));
$("provider").addEventListener("change", () => {
  $("model").value = state.config.providers[$("provider").value].model;
  $("key-state").textContent =
    $("provider").value === state.settings.provider &&
    state.settings.key_configured
      ? "· saved securely"
      : "· new key needed";
});
$("settings-form").addEventListener("submit", (e) => {
  e.preventDefault();
  guarded(async () => {
    await api("/api/settings", {
      method: "PUT",
      body: {
        provider: $("provider").value,
        model: $("model").value.trim(),
        key: $("api-key").value.trim(),
        elevenlabs_key: $("eleven-key").value.trim(),
        elevenlabs_voice: $("eleven-voice").value.trim(),
      },
    });
    $("api-key").value = "";
    $("eleven-key").value = "";
    state.settings = await api("/api/settings");
    $("settings-dialog").close();
    if (state.project) {
      $("key-hint").hidden = true;
      $("model-label").textContent = state.settings.model;
    }
    notice("Toolkit saved. You’re ready to create.");
  }, e.submitter);
});
$("password-form").addEventListener("submit", (e) => {
  e.preventDefault();
  guarded(async () => {
    await api("/api/password", {
      method: "PUT",
      body: { password: $("new-password").value },
    });
    $("new-password").value = "";
    notice(
      "Password saved. Use your username and password to sign in next time.",
    );
  }, e.submitter);
});
$("remove-keys").addEventListener("click", () =>
  guarded(async () => {
    if (
      !confirm(
        "Remove all saved provider keys? Active provider requests may still complete.",
      )
    )
      return;
    await api("/api/settings/keys", { method: "DELETE" });
    $("settings-dialog").close();
    state.settings = await api("/api/settings");
    if (state.project) $("key-hint").hidden = false;
    notice("Saved keys removed.");
  }),
);
$("connect-button").addEventListener("click", () => {
  $("mcp-url").value = state.config.mcp_url;
  $("claude-command").textContent =
    "claude mcp add --transport http video-use " + state.config.mcp_url;
  dialog("connect-dialog");
});
$("copy-url").addEventListener("click", () => copy(state.config.mcp_url));
$("copy-command").addEventListener("click", () =>
  copy($("claude-command").textContent),
);
let consentId;
async function showConsent(id) {
  const info = await api("/api/consent/" + id);
  consentId = id;
  $("consent-title").textContent = "Connect " + info.client_name + "?";
  dialog("consent-dialog");
}
async function consent(allow) {
  const data = await api("/api/consent/" + consentId, {
    method: "POST",
    body: { allow },
  });
  location.assign(data.redirect_url);
}
$("allow-consent").addEventListener("click", () =>
  guarded(() => consent(true), $("allow-consent")),
);
$("deny-consent").addEventListener("click", () =>
  guarded(() => consent(false), $("deny-consent")),
);
async function init() {
  state.config = await api("/api/config");
  const setup = new URLSearchParams(location.hash.slice(1)).get("setup");
  if (setup) {
    history.replaceState(null, "", location.pathname + location.search);
    await api("/api/bootstrap", { method: "POST", body: { token: setup } });
    await enterStudio();
    await openSettings();
    $("settings-dialog").querySelector("details").open = true;
    notice(
      "Your existing keys are connected. Set a password below to keep access to this workspace.",
    );
    return;
  }
  try {
    await enterStudio();
  } catch (error) {
    if (error.message !== "Sign in to your video-use workspace")
      notice(error.message, true);
  }
}
guarded(init);
