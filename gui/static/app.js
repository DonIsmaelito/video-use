const grid = document.querySelector("#lane-grid");
const template = document.querySelector("#lane-template");
const connection = document.querySelector("#connection");
const laneDetail = document.querySelector("#lane-detail-dialog");
const laneDetailTitle = laneDetail.querySelector(".lane-detail-title");
const laneDetailContext = laneDetail.querySelector(".lane-detail-context");
const laneDetailQuery = laneDetail.querySelector(".lane-detail-query");
const laneDetailTrace = laneDetail.querySelector(".lane-detail-trace");
const laneDetailClose = laneDetail.querySelector(".lane-detail-close");
const historyGrid = document.querySelector("#history-grid");
const historyCount = document.querySelector("#history-count");
const historyEmpty = document.querySelector("#history-empty");
const historyError = document.querySelector("#history-error");
const historyDialog = document.querySelector("#history-dialog");
const historyDialogTitle = historyDialog.querySelector(".history-dialog-title");
const historyDialogClose = historyDialog.querySelector(".history-dialog-close");
const historyVideo = historyDialog.querySelector("video");
const historyArtifacts = historyDialog.querySelector(".history-artifacts");
const historyQuery = historyDialog.querySelector(".history-query");
const lanes = new Map();
const historyRuns = new Map();
const historyCards = new Map();
let catalog = null;
let activeHistoryRunId = null;

const terminalStates = new Set(["idle", "ready", "failed"]);
const runningStates = new Set(["queued", "uploading", "running", "waiting"]);

function setConnection(online) {
  connection.textContent = online ? "local · modal ready" : "reconnecting";
  connection.classList.toggle("online", online);
}

function timeLabel(value) {
  if (!value) return "--:--:--";
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function timestampValue(value) {
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function elapsedLabel(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const clock = [minutes, seconds]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return hours > 0 ? `${String(hours).padStart(2, "0")}:${clock}` : clock;
}

function setHistoryError(message = "") {
  historyError.textContent = message;
  historyError.hidden = !message;
}

function historyTimestamp(item) {
  const value = Date.parse(item.completed_at || "");
  return Number.isFinite(value) ? value : 0;
}

function updateHistoryEmptyState() {
  historyCount.textContent = String(historyRuns.size);
  historyEmpty.hidden = historyRuns.size > 0;
}

function selectHistoryArtifact(item, artifact) {
  if (!artifact?.video_url) return;
  for (const button of historyArtifacts.querySelectorAll("button")) {
    button.classList.toggle("selected", button.dataset.artifactId === artifact.id);
  }
  if (historyVideo.dataset.url === artifact.video_url) return;
  historyVideo.dataset.url = artifact.video_url;
  historyVideo.poster = item.poster_url || "";
  historyVideo.src = artifact.video_url;
  historyVideo.load();
}

function openHistory(item) {
  activeHistoryRunId = item.run_id;
  historyDialogTitle.textContent = new Date(item.completed_at).toLocaleString();
  historyQuery.textContent = item.query || "no query recorded";
  historyArtifacts.replaceChildren();
  for (const artifact of item.artifacts || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.artifactId = artifact.id;
    button.textContent = artifact.label || artifact.id;
    button.addEventListener("click", () => selectHistoryArtifact(item, artifact));
    historyArtifacts.append(button);
  }
  if (!historyDialog.open) historyDialog.showModal();
  const primary = item.artifacts.find((artifact) => artifact.primary) || item.artifacts[0];
  selectHistoryArtifact(item, primary);
}

function closeHistory() {
  historyVideo.pause();
  historyVideo.removeAttribute("src");
  historyVideo.removeAttribute("poster");
  delete historyVideo.dataset.url;
  historyVideo.load();
  activeHistoryRunId = null;
  if (historyDialog.open) historyDialog.close();
}

async function deleteHistory(item, button) {
  const confirmed = window.confirm(
    "Delete this run from R2, Modal, and local history? This cannot be undone.",
  );
  if (!confirmed) return;
  button.disabled = true;
  setHistoryError();
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(item.run_id)}`, {
      method: "DELETE",
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "could not delete run");
    historyRuns.delete(item.run_id);
    historyCards.get(item.run_id)?.remove();
    historyCards.delete(item.run_id);
    if (activeHistoryRunId === item.run_id) closeHistory();
    updateHistoryEmptyState();
  } catch (error) {
    button.disabled = false;
    setHistoryError(error.message);
  }
}

function createHistoryCard(item) {
  const card = document.createElement("article");
  card.className = "history-card";
  card.dataset.runId = item.run_id;
  card.dataset.completedAt = String(historyTimestamp(item));

  const openButton = document.createElement("button");
  openButton.type = "button";
  openButton.className = "history-open";
  openButton.setAttribute("aria-label", `Play run: ${item.query || "untitled"}`);
  const posterShell = document.createElement("span");
  posterShell.className = "history-poster";
  if (item.poster_url) {
    const poster = document.createElement("img");
    poster.src = item.poster_url;
    poster.alt = "";
    poster.loading = "lazy";
    posterShell.append(poster);
  } else {
    posterShell.textContent = "no poster";
  }
  const query = document.createElement("span");
  query.className = "history-card-query";
  query.textContent = item.query || "no query recorded";
  openButton.append(posterShell, query);
  openButton.addEventListener("click", () => openHistory(item));

  const footer = document.createElement("footer");
  const completed = document.createElement("time");
  completed.dateTime = item.completed_at || "";
  completed.textContent = item.completed_at
    ? new Date(item.completed_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })
    : "completed";
  const outputs = document.createElement("span");
  outputs.textContent = `${item.artifacts.length} output${item.artifacts.length === 1 ? "" : "s"}`;
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "history-delete";
  remove.textContent = "delete";
  remove.addEventListener("click", () => deleteHistory(item, remove));
  footer.append(completed, outputs, remove);
  card.append(openButton, footer);
  return card;
}

function upsertHistory(item) {
  if (!item?.run_id || !Array.isArray(item.artifacts) || item.artifacts.length === 0) return;
  historyRuns.set(item.run_id, item);
  historyCards.get(item.run_id)?.remove();
  const card = createHistoryCard(item);
  historyCards.set(item.run_id, card);
  const completedAt = historyTimestamp(item);
  const next = [...historyGrid.children].find(
    (candidate) => Number(candidate.dataset.completedAt || 0) < completedAt,
  );
  historyGrid.insertBefore(card, next || null);
  updateHistoryEmptyState();
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history");
    if (!response.ok) throw new Error("run history unavailable");
    const items = await response.json();
    for (const item of items) upsertHistory(item);
  } catch (error) {
    setHistoryError(error.message);
  }
}

function renderTimer(lane, now = Date.now()) {
  if (lane.startedAt === null) {
    lane.timer.textContent = "00:00";
    lane.timer.dateTime = "PT0S";
    return;
  }
  const end = lane.finishedAt ?? now;
  const elapsedMilliseconds = Math.max(0, end - lane.startedAt);
  const elapsedSeconds = Math.floor(elapsedMilliseconds / 1000);
  lane.timer.textContent = elapsedLabel(elapsedMilliseconds);
  lane.timer.dateTime = `PT${elapsedSeconds}S`;
}

function updateTimerBounds(lane, state) {
  if (Object.hasOwn(state, "started_at")) {
    lane.startedAt = timestampValue(state.started_at);
  }
  if (Object.hasOwn(state, "finished_at")) {
    lane.finishedAt = timestampValue(state.finished_at);
  }
  renderTimer(lane);
}

function syncExpandedLane(lane, resetScroll = false) {
  if (!laneDetail.open || laneDetail.dataset.laneId !== String(lane.id)) return;
  const wasNearBottom = (
    laneDetailTrace.scrollHeight
    - laneDetailTrace.scrollTop
    - laneDetailTrace.clientHeight
  ) < 48;
  const previousScroll = laneDetailTrace.scrollTop;
  laneDetailTitle.textContent = `lane ${String(lane.id).padStart(2, "0")}`;
  laneDetailContext.textContent = [
    lane.taskContext.textContent,
    lane.card.dataset.state,
  ].filter(Boolean).join(" · ");
  laneDetailQuery.textContent = lane.prompt.value || "no query";
  laneDetailTrace.replaceChildren(
    ...[...lane.log.children].map((item) => item.cloneNode(true)),
  );
  if (resetScroll) {
    laneDetailTrace.scrollTop = 0;
  } else if (wasNearBottom) {
    laneDetailTrace.scrollTop = laneDetailTrace.scrollHeight;
  } else {
    laneDetailTrace.scrollTop = previousScroll;
  }
}

function openExpandedLane(lane) {
  const previousLane = lanes.get(Number(laneDetail.dataset.laneId));
  if (previousLane) previousLane.expandButton.setAttribute("aria-expanded", "false");
  laneDetail.dataset.laneId = String(lane.id);
  lane.expandButton.setAttribute("aria-expanded", "true");
  if (!laneDetail.open) laneDetail.showModal();
  syncExpandedLane(lane, true);
}

function closeExpandedLane() {
  if (laneDetail.open) laneDetail.close();
}

function appendEvent(lane, event) {
  if (!event.message) return;
  const eventId = event.event_id || null;
  let item = eventId ? lane.eventItems.get(eventId) : null;
  let kind;
  let message;
  if (!item) {
    item = document.createElement("li");
    kind = document.createElement("span");
    kind.className = "event-kind";
    message = document.createElement("span");
    message.className = "event-message";
    item.append(kind, message);
    lane.log.append(item);
    if (eventId) lane.eventItems.set(eventId, item);
  } else {
    kind = item.querySelector(".event-kind");
    message = item.querySelector(".event-message");
  }
  item.dataset.kind = event.type || "trace";

  const kindLabels = {
    agent_started: "agent",
    agent_trace: event.agent_event || "agent",
    agent_decision: "decision",
    agent_completed: "agent",
    approval_required: "approval",
    approval_resolved: "approval",
  };
  kind.textContent = kindLabels[event.type] || event.type || "trace";
  message.textContent = `${timeLabel(event.timestamp)}  ${event.message}`;
  lane.log.scrollTop = lane.log.scrollHeight;
  syncExpandedLane(lane);
}

function autoApprovalKey(runId) {
  return `video-use:auto-approve:${runId}`;
}

function autoApprovalPreferenceKey(laneId) {
  return `video-use:auto-approve-lane:${laneId}`;
}

function rememberLaneApproval(lane) {
  if (!lane.runId) return;
  lane.autoApprovalRunId = lane.runId;
  window.localStorage.setItem(autoApprovalKey(lane.runId), "1");
}

function hydrateLaneApproval(lane, state) {
  if (!state.run_id) return;
  if (lane.runId !== state.run_id) {
    lane.runId = state.run_id;
    lane.autoApprovalRunId = window.localStorage.getItem(
      autoApprovalKey(state.run_id),
    ) === "1" ? state.run_id : null;
  }
  const wasAllowedForLane = (state.events || []).some(
    (event) => event.type === "approval_resolved"
      && event.message === "approval allowed for this lane",
  );
  if (wasAllowedForLane) rememberLaneApproval(lane);
}

function showApproval(lane, approval) {
  if (!approval) return;
  lane.approval = approval;
  lane.approvalPanel.hidden = false;
  lane.approvalKind.textContent = approval.kind || "request";
  lane.approvalSummary.textContent = approval.summary || "Agent approval requested";
  lane.approvalCommand.textContent = approval.command || approval.cwd || "";
  lane.approvalCommand.hidden = !lane.approvalCommand.textContent;
  lane.approvalReason.textContent = approval.reason || "";
  lane.approvalReason.hidden = !lane.approvalReason.textContent;
  for (const button of lane.approvalButtons) button.disabled = false;
  lane.approvalShortcut.disabled = false;
  if (lane.autoApprovalRunId === lane.runId && !lane.resolvingApproval) {
    window.queueMicrotask(() => resolveApproval(lane, "accept"));
  }
}

function hideApproval(lane) {
  lane.approval = null;
  lane.approvalPanel.hidden = true;
  lane.approvalShortcut.disabled = true;
}

function selectArtifact(lane, artifact) {
  if (!artifact?.url || lane.video.dataset.url === artifact.url) return;
  lane.video.dataset.url = artifact.url;
  lane.video.src = `${artifact.url}?v=${Date.now()}`;
  lane.videoShell.classList.add("has-video");
  lane.video.load();
}

function renderArtifacts(lane) {
  lane.artifactLinks.replaceChildren();
  for (const artifact of lane.artifacts.values()) {
    const link = document.createElement("a");
    link.href = artifact.url;
    link.textContent = artifact.label || artifact.id;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      selectArtifact(lane, artifact);
    });
    lane.artifactLinks.append(link);
  }
}

function mergeArtifact(lane, artifact) {
  if (!artifact?.id || !artifact?.url) return;
  lane.artifacts.set(artifact.id, artifact);
  renderArtifacts(lane);
}

function renderTaskContext(lane, context) {
  const operation = String(context?.operation || "").replaceAll("_", " ");
  const workflow = String(context?.workflow || "").replaceAll("_", " ");
  const label = [operation, workflow].filter(Boolean).join(" · ");
  lane.taskContext.textContent = label;
  lane.taskContext.hidden = !label;
  lane.taskContext.title = context?.summary || label;
}

function updateLane(lane, state) {
  const status = state.status || lane.card.dataset.state || "idle";
  hydrateLaneApproval(lane, state);
  lane.card.dataset.state = status;
  lane.status.textContent = status;
  if (Object.hasOwn(state, "prompt")) {
    lane.prompt.value = state.prompt || "";
    lane.prompt.classList.toggle(
      "submitted",
      Boolean(state.prompt) && status !== "idle",
    );
  }
  const busy = !terminalStates.has(status);
  lane.button.disabled = busy;
  lane.model.disabled = busy;
  lane.reasoning.disabled = busy;
  lane.autoApprove.disabled = busy;
  if (Object.hasOwn(state, "task_context")) {
    renderTaskContext(lane, state.task_context);
  }
  updateTimerBounds(lane, state);
  const progress = Math.max(0, Math.min(1, Number(state.progress || 0)));
  lane.progress.style.width = `${Math.round(progress * 100)}%`;

  if (state.video_url && lane.video.dataset.url !== state.video_url) {
    lane.video.dataset.url = state.video_url;
    lane.video.src = `${state.video_url}?v=${Date.now()}`;
    lane.videoShell.classList.add("has-video");
    lane.video.load();
  }
  if (Array.isArray(state.artifacts)) {
    lane.artifacts.clear();
    for (const artifact of state.artifacts) mergeArtifact(lane, artifact);
  }
  if (Object.hasOwn(state, "trace_url")) {
    if (state.trace_url) {
      lane.traceDownload.href = state.trace_url;
      lane.traceDownload.hidden = false;
    } else {
      lane.traceDownload.removeAttribute("href");
      lane.traceDownload.hidden = true;
    }
  }

  if (!lane.selectionHydrated && state.model) {
    const available = catalog.models.some((model) => model.id === state.model);
    if (available) {
      lane.model.value = state.model;
      updateReasoningOptions(lane, state.reasoning_effort);
    }
    lane.selectionHydrated = true;
  }
  if (state.approval) showApproval(lane, state.approval);
  syncExpandedLane(lane);
}

function handleEvent(lane, event) {
  if (event.type === "snapshot") {
    lane.log.replaceChildren();
    lane.eventItems.clear();
    updateLane(lane, event.state || {});
    for (const historyEvent of event.state?.events || []) {
      appendEvent(lane, historyEvent);
    }
    if (!event.state?.approval) hideApproval(lane);
    return;
  }

  if (event.type === "history_added" && event.history) {
    upsertHistory(event.history);
  }

  const statusByType = {
    queued: "queued",
    uploading: "uploading",
    agent_started: "running",
    agent_trace: "running",
    agent_decision: "running",
    agent_completed: "running",
    approval_required: "waiting",
    approval_resolved: "running",
    task_context: "running",
    started: "running",
    trace: "running",
    decision: "running",
    completed: "ready",
    failed: "failed",
  };
  const timing = {};
  if (event.type === "queued") {
    timing.started_at = event.timestamp;
    timing.finished_at = null;
    timing.trace_url = null;
  } else if (["completed", "failed"].includes(event.type)) {
    timing.finished_at = event.timestamp;
  }
  updateLane(lane, {
    status: statusByType[event.type] || lane.card.dataset.state,
    run_id: event.run_id,
    progress: event.progress,
    video_url: event.video_url,
    ...(Object.hasOwn(event, "task_context")
      ? { task_context: event.task_context }
      : {}),
    ...(Object.hasOwn(event, "trace_url")
      ? { trace_url: event.trace_url }
      : {}),
    ...timing,
  });
  if (event.artifact_url) {
    mergeArtifact(lane, {
      id: event.artifact_id || "preview",
      label: event.artifact_label || event.artifact_id || "preview",
      url: event.artifact_url,
      primary: Boolean(event.primary),
    });
  }
  if (event.type === "approval_required") showApproval(lane, event.approval);
  if (["approval_resolved", "completed", "failed"].includes(event.type)) {
    hideApproval(lane);
  }
  appendEvent(lane, event);
}

async function submitLane(lane) {
  const prompt = lane.prompt.value.trim();
  if (!prompt) return;

  lane.button.disabled = true;
  try {
    const response = await fetch(`/api/lanes/${lane.id}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        project_path: lane.project.value.trim() || null,
        model: lane.model.value,
        reasoning_effort: lane.reasoning.value,
        auto_approve: lane.autoApprove.checked,
      }),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.detail || "could not start lane");
    }
    lane.prompt.classList.add("submitted");
  } catch (error) {
    handleEvent(lane, {
      type: "failed",
      message: error.message,
      progress: 1,
      timestamp: new Date().toISOString(),
    });
  }
}

async function resolveApproval(lane, decision) {
  if (!lane.approval || lane.resolvingApproval) return;
  if (decision === "acceptForSession") rememberLaneApproval(lane);
  const approvalId = lane.approval.id;
  lane.resolvingApproval = true;
  for (const button of lane.approvalButtons) button.disabled = true;
  try {
    const response = await fetch(
      `/api/lanes/${lane.id}/approvals/${approvalId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      },
    );
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "could not resolve approval");
  } catch (error) {
    appendEvent(lane, {
      type: "approval_error",
      message: error.message,
      timestamp: new Date().toISOString(),
    });
    for (const button of lane.approvalButtons) button.disabled = false;
  } finally {
    lane.resolvingApproval = false;
  }
}

function updateReasoningOptions(lane, preferredEffort = null) {
  const model = catalog.models.find((item) => item.id === lane.model.value);
  lane.reasoning.replaceChildren();
  if (!model) return;

  for (const effort of model.reasoning_efforts) {
    const option = document.createElement("option");
    option.value = effort.id;
    option.textContent = effort.id;
    option.title = effort.description || effort.id;
    lane.reasoning.append(option);
  }
  const supported = model.reasoning_efforts.some(
    (effort) => effort.id === preferredEffort,
  );
  lane.reasoning.value = supported
    ? preferredEffort
    : model.default_reasoning_effort;
}

function populateModelOptions(lane) {
  lane.model.replaceChildren();
  for (const model of catalog.models) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.display_name;
    option.title = model.description || model.display_name;
    lane.model.append(option);
  }
  lane.model.value = catalog.default_model;
  updateReasoningOptions(lane);
}

function connectLane(lane) {
  const source = new EventSource(`/api/lanes/${lane.id}/events`);
  source.onopen = () => setConnection(true);
  source.onmessage = (message) => {
    setConnection(true);
    handleEvent(lane, JSON.parse(message.data));
  };
  source.onerror = () => setConnection(false);
  lane.source = source;
}

function createLane(id) {
  const fragment = template.content.cloneNode(true);
  const card = fragment.querySelector("[data-lane]");
  const lane = {
    id,
    card,
    status: fragment.querySelector("[data-status]"),
    taskContext: fragment.querySelector(".task-context"),
    timer: fragment.querySelector(".lane-timer"),
    videoShell: fragment.querySelector(".video-shell"),
    video: fragment.querySelector("video"),
    artifactLinks: fragment.querySelector(".artifact-links"),
    artifacts: new Map(),
    progress: fragment.querySelector(".progress-fill"),
    form: fragment.querySelector(".run-form"),
    project: fragment.querySelector(".project-input"),
    prompt: fragment.querySelector(".prompt-input"),
    model: fragment.querySelector(".model-select"),
    reasoning: fragment.querySelector(".reasoning-select"),
    autoApprove: fragment.querySelector(".auto-approve"),
    button: fragment.querySelector(".run-button"),
    expandButton: fragment.querySelector(".expand-button"),
    approvalShortcut: fragment.querySelector(".approval-shortcut"),
    approvalPanel: fragment.querySelector(".approval-panel"),
    approvalKind: fragment.querySelector(".approval-kind"),
    approvalSummary: fragment.querySelector(".approval-summary"),
    approvalCommand: fragment.querySelector(".approval-command"),
    approvalReason: fragment.querySelector(".approval-reason"),
    approvalButtons: [...fragment.querySelectorAll("[data-decision]")],
    approval: null,
    runId: null,
    autoApprovalRunId: null,
    resolvingApproval: false,
    log: fragment.querySelector(".event-log"),
    traceDownload: fragment.querySelector(".trace-download"),
    eventItems: new Map(),
    selectionHydrated: false,
    startedAt: null,
    finishedAt: null,
  };
  fragment.querySelector(".lane-name").textContent = `lane ${String(id).padStart(2, "0")}`;
  card.dataset.state = "idle";
  lane.autoApprove.checked = window.localStorage.getItem(
    autoApprovalPreferenceKey(id),
  ) !== "0";
  populateModelOptions(lane);
  lane.model.addEventListener("change", () => updateReasoningOptions(lane));
  lane.expandButton.addEventListener("click", () => openExpandedLane(lane));
  lane.autoApprove.addEventListener("change", () => {
    window.localStorage.setItem(
      autoApprovalPreferenceKey(id),
      lane.autoApprove.checked ? "1" : "0",
    );
  });
  for (const button of lane.approvalButtons) {
    button.addEventListener("click", () => resolveApproval(lane, button.dataset.decision));
  }
  lane.form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitLane(lane);
  });
  lane.prompt.addEventListener("input", () => {
    lane.prompt.classList.remove("submitted");
    syncExpandedLane(lane);
  });
  lanes.set(id, lane);
  grid.append(fragment);
  connectLane(lane);
}

laneDetailClose.addEventListener("click", closeExpandedLane);
laneDetail.addEventListener("close", () => {
  const lane = lanes.get(Number(laneDetail.dataset.laneId));
  if (lane) lane.expandButton.setAttribute("aria-expanded", "false");
  delete laneDetail.dataset.laneId;
});
laneDetail.addEventListener("click", (event) => {
  if (event.target === laneDetail) closeExpandedLane();
});
historyDialogClose.addEventListener("click", closeHistory);
historyDialog.addEventListener("click", (event) => {
  if (event.target === historyDialog) closeHistory();
});
historyDialog.addEventListener("close", () => {
  if (activeHistoryRunId !== null) closeHistory();
});

async function start() {
  try {
    const response = await fetch("/api/codex/models");
    if (!response.ok) throw new Error("model catalog unavailable");
    catalog = await response.json();
  } catch (_error) {
    catalog = {
      default_model: "gpt-5.6-sol",
      models: [
        {
          id: "gpt-5.6-sol",
          display_name: "GPT-5.6-Sol",
          description: "",
          default_reasoning_effort: "low",
          reasoning_efforts: ["low", "medium", "high", "xhigh", "max", "ultra"].map(
            (id) => ({ id, description: "" }),
          ),
        },
      ],
    };
  }

  for (let id = 1; id <= 4; id += 1) {
    createLane(id);
  }
  await loadHistory();
}

start();

const timerInterval = window.setInterval(() => {
  const now = Date.now();
  for (const lane of lanes.values()) {
    if (runningStates.has(lane.card.dataset.state)) renderTimer(lane, now);
  }
}, 250);

window.addEventListener("beforeunload", () => {
  window.clearInterval(timerInterval);
  for (const lane of lanes.values()) {
    lane.source?.close();
  }
});
