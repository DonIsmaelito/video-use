# Video production and interaction inside Claude and ChatGPT

The brief/story editors, interaction catalog and fullscreen negotiation described below are implemented and covered by local protocol and browser tests. Check the deployed harness version before using a new chat to validate them; earlier production traces do not demonstrate use of these controls. Signed-in Claude/ChatGPT acceptance remains a separate check.

## Two components with one creative context

**Video production** edits and creates the piece: source inspection, narration, scene construction, rendering, assembly, review and export. The host assistant orchestrates these operations through MCP. Editable sources and measured production timing belong to this component; displaying a form or calling a task successful does not prove that the video is correct.

**Experience and alignment** helps the person express what they want and understand what is being made. It chooses useful questions, examples, story proposals and visual updates for the current request. It should identify consequential uncertainty about audience, emphasis, style or story, rather than asking for approval at every production stage. The user should mainly see their material and the evolving video, accompanied by concise conversation.

The shared contract is persisted creative context with explicit provenance and a revision. Assistant assumptions, proposed story beats and submitted user preferences remain distinguishable. Production results return current preferences so the next affected edit can adopt a change while retaining compatible work. An optional unanswered question is not approval, rejection or a reason to stop independent work.

For a broad explainer, a useful sequence might be a short proposed direction, relevant optional choices, an editable story, then one meaningful motion excerpt while the remaining scenes develop. This is not a required sequence: a precise cut may need only the source and the resulting clip; a supplied script needs no invented questionnaire. Author and show a useful excerpt before spending minutes generating every scene. Do not replace conversation with tool status text or show empty workspace containers as progress.

## Host surfaces and boundaries

The same MCP tools and saved state serve both hosts. Host-specific evidence below does not establish identical display or continuation behavior in ChatGPT; negotiate capabilities and verify the account flow separately.

Verified against primary documentation on 2026-10-01. MCP Apps provides a sandboxed HTML/JavaScript interface, not a fixed catalog of widgets. We can build buttons, forms, sliders, selectable cards, image comparisons, a storyboard, video/audio controls, waveforms and a drawing canvas within that interface. Their editing behavior still needs server-side implementation; displaying a control does not add a rendering capability. See the [MCP Apps overview](https://modelcontextprotocol.io/extensions/apps/overview) and [official examples](https://github.com/modelcontextprotocol/ext-apps#examples).

| Surface or behavior | Evidence and implementation rule |
| --- | --- |
| Inline card | Supported in Claude. Best default for a small choice, a useful visual or a playable draft. Keep the interface focused on the video. |
| Fullscreen view | Supported in Claude, with the conversation input still available. Offer expansion only when `getHostContext().availableDisplayModes` includes `fullscreen`; use `requestDisplayMode`, then respect the returned mode. |
| Picture in picture | Defined by the MCP Apps protocol, but not documented as a Claude surface in the current help article. Do not promise or require it. Enable only if a host advertises it and it is tested there. |
| Video, images and audio | Ordinary web media inside the app; use authenticated or short-lived asset URLs covered by the declared resource domains. Our current app already displays images and playable MP4s. |
| Buttons, forms, choices, sliders, drag/reorder | Implementable with HTML/JavaScript. Local preview changes can happen immediately; persistent edits need an authenticated server tool. These are our controls, not native Claude question dialogs. |
| Live updates in an existing card | Supported through app-only tool calls. This can refresh the visual without a model turn for each refresh. Calls still create backend traffic; no claim is made about exemption from host usage limits. |
| Streaming partial tool input | Optional protocol feature. Useful for noncritical previews where supported; incomplete input must not start production work. Not a reliable substitute for a completed visual. |

Claude documents [inline and fullscreen connectors, permissions and iframe security](https://support.claude.com/en/articles/13454812-use-interactive-connectors-in-claude). The SDK documents [fullscreen negotiation, app-only tools, polling and partial-input handling](https://apps.extensions.modelcontextprotocol.io/api/documents/Patterns.html). The [protocol specification](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx) defines optional display modes and lifecycle behavior. Host capabilities must be checked at runtime rather than inferred from the host name.

## Context updates do not keep a model running

`updateModelContext` supplies state for a future model turn. It does not trigger an immediate response, and subsequent updates replace earlier context from that view. Send a compact current state rather than assuming incremental updates will accumulate.

`sendMessage` submits a message with the `user` role and may trigger a follow-up. The host can reject it or require consent. Use it after an explicit user action such as **Apply changes** or **Send suggestion**; never manufacture user messages from a timer or completed render. A successful save and a successfully delivered message are separate outcomes. See the SDK's [updateModelContext](https://apps.extensions.modelcontextprotocol.io/api/classes/app.App.html#updateModelContext) and [sendMessage](https://apps.extensions.modelcontextprotocol.io/api/classes/app.App.html#sendMessage) contracts.

The server remains authoritative: save preferences first, return the current creative revision in subsequent tool results, and let the next production step adopt the change. Show a truthful fallback if the host cannot deliver a follow-up. Neither API guarantees interruption of current reasoning, endless generation, or bypassing Claude's turn/tool/usage limits. App code also cannot control Claude's surrounding attribution, tool approvals or reasoning display.

## Implemented interaction catalog

`video_use_capabilities().interaction` now lists the available interaction types. The assistant selects the ones that fit the request; the catalog is not a workflow checklist or a promise that the host has already displayed them.

| When it helps | MCP tool / interface | Current behavior |
| --- | --- | --- |
| Audience, tone or emphasis is consequential and unspecified | `show_video_brief` | Displays 1–3 authored questions with 2–4 choices each. A suggested choice is labeled, not preselected. Users can save a subset of answers; the assistant continues independent work. |
| Motion references communicate a visual decision better than words | `show_video_choices` | Offers 2–3 relevant cached examples. They are references, not generated drafts or an exhaustive set of styles. A precise request or supplied reference can skip them. |
| A substantial new narrated story would benefit from an editable proposal | `show_video_story` | Saves and shows 1–12 beats with editable title, visual, narration and proposed seconds. It replaces a separate `plan_video` call. These are text story cards, not rendered frames or measured production timing. |
| A useful image, excerpt, complete draft or final export exists | `show_video_preview` | Displays actual media with download and **Edit this moment**. **Larger labels**, **Faster pace** and **Change the look** prefill an editable suggestion; only an explicit submission saves or sends it. The existing player can refresh newer media without another assistant display call; active playback and unsent feedback defer replacement. Fullscreen is offered only when the host advertises it. |
| Material is missing | In-chat source upload | Transfers explicitly selected files into the project. A connector elsewhere in the host does not automatically grant this MCP access to its private files. |

Brief answers and story edits are saved through the app-only `save_video_widget` tool after an explicit submission. Story titles, visuals, narration and duration are editable in the current UI. Reordering is accepted by the backend for the same stable beat IDs, but a drag/reorder control is not currently present; adding or removing beats requires the assistant to present a revised story. Waveform editing, timeline trimming, drawing and other custom controls are possible app interfaces, not implemented capabilities in this pass.

Avoid turning these into mandatory approval stages. A broad creative prompt benefits from a few choices; a precise trimming request usually needs none. Persist optional feedback without making every small interaction restart the model.

Media task results use conditional `preview_delivery.open_if_missing` guidance rather than an unconditional display command. The assistant should reuse an existing working player in the same conversation. The server cannot infer a chat's visible cards from account-level refresh traffic, and one iframe cannot remove earlier host-owned cards; this guidance reduces duplicate calls without pretending to enforce host layout.

## Persistence, continuation and code ownership

`video_use_mcp/pilot/widgets.py` validates and persists brief/story proposals and explicit user submissions. `creative_state.py` serializes edits. Widget revisions are distinct from creative revisions: replaced or stale editors and conflicting request-ID retries are rejected; identical retries do not apply the edit twice. Saves preserve unrelated creative fields. Story edits carry `user_edit` provenance, while displayed assistant proposals remain `assistant_plan`.

`ui/app.js` and `ui/template.html` render the editors, references, source controls and player. Unsent edits survive failed saves; a newer result does not silently erase them. After a confirmed submission, the app sends compact authoritative context through `updateModelContext` where supported, then attempts `sendMessage` from that explicit user action. A retry confirmed after newer edits updates context without replaying the old instruction. If the host cannot deliver a message, the UI distinguishes **saved** from **sent** and tells the user how to continue.

`server.py` registers the tools and exposes the interaction catalog; `workflow.py` supplies request-sensitive guidance. `cards.py` returns fresh creative context with production results and declares the app resource and permitted domains. App-only visibility reduces assistant-facing tool clutter; owner authorization and validated saves still enforce access. No widget can remove the host's approval prompts, guarantee immediate interruption, or keep model generation running after a host limit.

## Recent execution evidence

These findings separate production defects from interaction problems. Times are UTC on 2026-10-01; they describe the observed run, not the state after a later deployment or allowance change.

| Observation | Consequence and verification |
| --- | --- |
| Solar excerpt rendered at 15:25 had 7.000 seconds of video but only 5.482 seconds of encoded audio. The source WAV was a full 7.000 seconds. | The renderer's `-frames:v` limit cut audio early on cloud FFmpeg 5.1.9. `motion_render.mjs` now bounds the complete output by duration and checks encoded audio duration/start before publication. An isolated cloud reproduction produced 5.482 seconds with the old arguments and 7.000 with the fix; actual scene renders also preserved the selected audio offset and padded a short source. This fix is locally implemented and cloud-tested, not yet deployed. |
| Wi-Fi narration failed at 17:10:39 with `narrate allowance reached`. | The observed daily owner allowance was 2,000 characters: 1,909 consumed, including 200 diagnostic characters; the new script required 410. All earlier narration charges were settled, and this rejected request added no narration reservation. This was a pilot budget limit, not a Claude limit or evidence that the speech provider was unavailable. The requested voiceover remained unmet. |
| The Wi-Fi run then authored five scenes before displaying a silent seven-second excerpt at 17:15:49, about 5m31 after project creation. | Preflight correctly rejected one keyframe outside its scene duration; the assistant repaired it. The avoidable delay was mostly before rendering. A useful first excerpt and relevant optional steering should come before full-film authoring. Tool traces alone cannot establish what the host said to the user. |
| Player refresh calls succeeded after both previews. | This proves that app-to-server refresh calls worked. It does not prove playback, user comprehension, an assistant response to feedback, or use of the new brief/story controls. |

Verification of the audio fix includes nine renderer unit tests, twelve scene tests with twenty-five subtests, and isolated cloud encodes. Widget behavior still needs account-level validation after deployment, including a user submission during ongoing production, a rejected host message, stale editors and a playable final download.
