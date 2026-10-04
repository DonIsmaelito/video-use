import { App, applyDocumentTheme, applyHostStyleVariables } from "@modelcontextprotocol/ext-apps";

const app = new App({ name: "Video choices", version: "1.0.0" });
const $ = id => document.getElementById(id);
let pinned, current, closed = false;
const here = state => !closed && current === state;
const capabilities = () => app.getHostCapabilities?.() || {};
const requestId = () => globalThis.crypto?.randomUUID?.() || `choice-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function validQuestion(data) {
  const q = data?.question;
  if (typeof data?.project_id !== 'string' || !data.project_id || !q || typeof q.id !== 'string'
      || !Number.isInteger(q.revision) || q.revision < 1 || !Array.isArray(q.questions)
      || q.questions.length < 1 || q.questions.length > 3) return false;
  const ids = new Set();
  for (const item of q.questions) {
    if (typeof item.id !== 'string' || ids.has(item.id) || typeof item.prompt !== 'string'
        || !Array.isArray(item.options) || item.options.length < 2 || item.options.length > 4) return false;
    ids.add(item.id);
    const options = new Set();
    for (const option of item.options) {
      if (typeof option.id !== 'string' || options.has(option.id) || typeof option.label !== 'string') return false;
      options.add(option.id);
    }
  }
  return Array.isArray(q.required) && q.required.every(id => ids.has(id));
}

function receive(result) {
  const data = result?.structuredContent;
  if (closed || result?.isError || !validQuestion(data)) return;
  const key = JSON.stringify([data.project_id, data.question.id]);
  if (pinned && pinned !== key) return;
  pinned = key;
  const q = data.question;
  if (current && (q.revision < current.question.revision
      || (q.revision === current.question.revision && (q.status !== 'answered' || current.saved)))) return;
  const answers = {};
  for (const item of q.questions) {
    const value = q.recorded_answers?.[item.id];
    if (item.options.some(option => option.id === value)) answers[item.id] = value;
  }
  current = { project: data.project_id, question: q, answers, saving: false,
    saved: q.status === 'answered', delivered: false, notice: q.status === 'answered' ? 'Saved.' : '' };
  draw(current);
}

function complete(state) {
  return Object.keys(state.answers).length > 0 && state.question.required.every(id => Object.hasOwn(state.answers, id));
}

function draw(state) {
  if (!here(state)) return;
  $('question-card').hidden = false;
  $('question-fields').replaceChildren();
  for (const item of state.question.questions) {
    const field = document.createElement('fieldset');
    const prompt = document.createElement('legend');
    prompt.textContent = item.prompt;
    const options = document.createElement('div');
    options.className = 'choice-options';
    for (const option of item.options) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = option.label;
      button.dataset.question = item.id;
      button.dataset.option = option.id;
      button.setAttribute('aria-pressed', String(state.answers[item.id] === option.id));
      button.disabled = state.saving || state.saved;
      button.onclick = async () => {
        if (!here(state) || state.saving || state.saved) return;
        state.answers[item.id] = option.id;
        state.notice = '';
        draw(state);
        if (state.question.questions.length === 1) await save(state);
      };
      options.append(button);
    }
    field.append(prompt, options);
    $('question-fields').append(field);
  }
  $('choice-status').textContent = state.notice;
  $('choice-continue').hidden = state.saved || (state.question.questions.length === 1 && !state.failed);
  $('choice-continue').textContent = state.failed ? 'Try again' : 'Continue';
  $('choice-continue').disabled = state.saving || !complete(state);
  $('choice-reply').hidden = !state.receipt || state.delivered || state.manualReply;
  $('choice-reply').disabled = state.saving;
  $('choice-reply-text').hidden = !state.receipt || state.delivered;
  $('choice-reply-text').textContent = state.receipt?.message || '';
}

async function deliver(state) {
  if (!here(state) || !state.receipt || state.delivered) return;
  const caps = capabilities();
  if (!caps.message?.text || (!state.contextSent && !caps.updateModelContext?.text)) {
    state.manualReply = true;
    state.notice = 'Saved. Reply in chat to continue.';
    return;
  }
  state.manualReply = false;
  try {
    if (!state.contextSent) {
      const context = state.receipt.context;
      const result = await app.updateModelContext({ content: [{ type: 'text', text:
        typeof context === 'string' ? context : JSON.stringify(context) }] });
      if (result?.isError) throw Error('Context unavailable');
      state.contextSent = true;
    }
    if (!here(state)) return;
    const result = await app.sendMessage({ role: 'user', content: [{ type: 'text', text: state.receipt.message }] });
    if (result?.isError) throw Error('Reply unavailable');
    state.delivered = true;
    state.notice = 'Saved. Send the prepared reply if it appears in chat.';
  } catch {
    state.notice = 'Saved. Send reply';
  }
}

async function save(state) {
  if (!here(state) || state.saving || state.saved || !complete(state)) return;
  if (!capabilities().serverTools) {
    state.notice = 'Please reply in chat with your choice.';
    draw(state);
    return;
  }
  const answers = Object.fromEntries(state.question.questions
    .filter(q => Object.hasOwn(state.answers, q.id)).map(q => [q.id, state.answers[q.id]]));
  const signature = JSON.stringify(answers);
  if (state.submission?.signature !== signature) state.submission = { signature, id: requestId() };
  state.saving = true;
  state.notice = 'Saving…';
  draw(state);
  try {
    const result = await app.callServerTool({ name: 'submit_video_choice', arguments: {
      project_id: state.project, widget_id: state.question.id, revision: state.question.revision,
      request_id: state.submission.id, answers,
    } });
    const data = result?.structuredContent;
    if (result?.isError || data?.saved !== true || typeof data.message !== 'string'
        || !data.message.trim() || data.context == null) throw Error('Save unconfirmed');
    state.saved = true;
    state.failed = false;
    state.receipt = { message: data.message, context: data.context };
    await deliver(state);
  } catch {
    state.failed = true;
    state.notice = 'Could not save. Try again or reply in chat.';
  } finally {
    state.saving = false;
    draw(state);
  }
}

$('choice-continue').onclick = () => current && save(current);
$('choice-reply').onclick = async () => {
  const state = current;
  if (!state || state.saving || !state.receipt || state.delivered) return;
  state.saving = true;
  draw(state);
  await deliver(state);
  state.saving = false;
  draw(state);
};
function theme(context = {}) {
  if (context.theme) applyDocumentTheme(context.theme);
  if (context.styles?.variables) applyHostStyleVariables(context.styles.variables);
}
app.ontoolresult = receive;
app.onhostcontextchanged = theme;
app.onteardown = async () => { closed = true; return {}; };
// The SDK accepts protocol messages only from window.parent. No direct network
// requests, credentials, or independent message listeners are used by this card.
app.connect().then(() => theme(app.getHostContext?.())).catch(() => {
  $('choice-status').textContent = 'Please reply in chat with your choice.';
});
