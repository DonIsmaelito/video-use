import { McpCopy } from '@/components/mcp-copy';
import { mcpSetups, type McpSetupClient } from '@/lib/mcp-setup';
import styles from './mcp-terminal.module.css';

export function McpTerminal({ client }: { client: McpSetupClient }) {
  const setup = mcpSetups[client];

  return (
    <div id="mcp-command" className={styles.terminal} tabIndex={-1}>
      <McpCopy key={client} shell value={setup.value} label={setup.label} />
    </div>
  );
}
