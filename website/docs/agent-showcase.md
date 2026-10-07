# Agent showcase and hosted MCP setup

The 2026-10-07 homepage row uses Higgsfield’s [large promotion and six shortcut cards](https://higgsfield.ai/) as a structural reference. The current page was visually inspected in isolated Chromium. The left Video Use panel stays blank at the user’s request. The six destinations are ChatGPT, Claude, Cursor, OpenClaw, Hermes and Your agent. Hermes is the [Nous Research agent](https://hermes-agent.nousresearch.com/); existing locally stored brand assets and their attribution are reused.

`AgentShortcuts` appears between `FeaturedCarousel` and `ImessageFeature`. `ConnectMcp` accepts custom trigger content while retaining the existing dialog, guide selection, clipboard behavior and preview suspension. OpenClaw, Hermes and Your agent use ordinary fragment links to `#mcp-command`; state owned by `Gallery` selects the relevant setup in `McpTerminal` before scrolling. Collection and filtered library views omit the promotional sections.

`lib/mcp-setup.ts` derives each command from the same `mcpUrl` used by the rest of the site. Commands are displayed and copied, never executed by the website. `McpCopy` retains selectable text and copy feedback when clipboard permission is unavailable. The generic option displays a URL because there is no universal MCP installation command.

Syntax sources checked on 2026-10-07:

- [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp): `claude mcp add --transport http --scope user video-use URL`. Installed `claude mcp add --help` also confirms the transport, user scope and argument order. The user signs in through `/mcp` in Claude Code.
- [OpenClaw MCP documentation](https://docs.openclaw.ai/tools/mcp): `openclaw mcp add video-use --url URL --transport streamable-http`, then `openclaw mcp login video-use` for OAuth.
- [Hermes OAuth bootstrap documentation](https://hermes-agent.nousresearch.com/docs/getting-started/nix-setup/): `hermes mcp add video-use --url URL --auth oauth`. Its [MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/) documents the HTTP and OAuth behavior.

These are documented client setup recipes, not claims of an end-to-end authenticated test in each client. The hosted endpoint requires pilot access; the UI states this beside the setup. No installation, local agent configuration, account authorization or credentials are changed by this website work.

## Verification

Production build, TypeScript/catalog validation, all 30 importer tests, lint, formatting and diff checks pass with 192 current films. Chromium layout checks pass at 1440, 1280, 1024, 1001, 1000, 850, 768, 600, 540, 390 and 320px: eight ordered content sectors, aligned agent cards, an empty showcase panel, no horizontal overflow, no mascot/text overlap, four white cursors inside the banner, and 24px spacing to neighboring galleries.

At 1440 and 390px all six destinations select their intended guide or command, all four setup values copy exactly, clipboard rejection selects the command, dialogs restore focus, and real preview frames advance before and after modal use. Separate phone touch checks pass for a setup card and fragment navigation. All collection/library routes and legacy root search hide the promotional rows after query hydration. The initial query-route assertion ran before hydration; waiting for the filtered library resolves the check. Evidence is in `/tmp/video-use-agent-row-20261007/`.

Published at https://video-use.insforge.site in InsForge deployment `8669ceb3-9b04-40d8-8328-5ee9408facda` from source `b348f67`. Live layout checks pass at 1440/390/320px; all six destinations, exact command copying, clipboard fallback, focus restoration and actual video playback pass at 1440/390px. All six public pages, the Hermes artwork and both conversation PNGs return 200. The current 192-film catalog and source manifests are unchanged from release `e3c73bf`. Final receipt: `/tmp/video-use-agent-row-20261007/release-summary.json`.
