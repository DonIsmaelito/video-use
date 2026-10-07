import { mcpUrl } from '@/lib/gallery';

// Syntax checked against each client's official MCP docs; no credentials belong here.
export const mcpSetups = {
  'claude-code': {
    name: 'Claude Code',
    label: 'Claude Code command',
    value: `claude mcp add --transport http --scope user video-use ${mcpUrl}`,
    instruction:
      'Run in your terminal, then open /mcp in Claude Code to sign in.',
    guide: 'https://code.claude.com/docs/en/mcp',
  },
  openclaw: {
    name: 'OpenClaw',
    label: 'OpenClaw command',
    value: `openclaw mcp add video-use --url ${mcpUrl} --transport streamable-http`,
    instruction: 'Then run openclaw mcp login video-use to sign in.',
    guide: 'https://docs.openclaw.ai/tools/mcp',
  },
  hermes: {
    name: 'Hermes',
    label: 'Hermes command',
    value: `hermes mcp add video-use --url ${mcpUrl} --auth oauth`,
    instruction: 'Run in your terminal and complete the browser sign-in.',
    guide:
      'https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/',
  },
  url: {
    name: 'Your agent',
    label: 'Remote MCP URL',
    value: mcpUrl,
    instruction:
      'Add this URL in your agent’s MCP settings. Use HTTP with OAuth sign-in.',
    guide: '/mcp#setup',
  },
} as const;

export type McpSetupClient = keyof typeof mcpSetups;
