import { ArrowUpRight, Terminal } from 'lucide-react';
import { McpCopy } from '@/components/mcp-copy';
import { mcpSetups, type McpSetupClient } from '@/lib/mcp-setup';
import styles from './mcp-terminal.module.css';

export function McpTerminal({
  client,
  onClientChange,
}: {
  client: McpSetupClient;
  onClientChange: (client: McpSetupClient) => void;
}) {
  const setup = mcpSetups[client];

  return (
    <div id="mcp-command" className={styles.terminal} tabIndex={-1}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          <Terminal size={16} aria-hidden="true" />
          Connect your agent
        </span>
        <fieldset className={styles.clients} aria-label="MCP setup client">
          {(Object.keys(mcpSetups) as McpSetupClient[]).map((id) => (
            <button
              type="button"
              key={id}
              aria-pressed={client === id}
              aria-controls="mcp-command-content"
              onClick={() => onClientChange(id)}
            >
              {mcpSetups[id].name}
            </button>
          ))}
        </fieldset>
      </div>
      <div id="mcp-command-content" className={styles.content}>
        <McpCopy key={client} code value={setup.value} label={setup.label} />
        <div className={styles.instructions}>
          <p>{setup.instruction}</p>
          <a
            href={setup.guide}
            target={setup.guide.startsWith('https:') ? '_blank' : undefined}
            rel="noopener noreferrer"
          >
            Setup guide <ArrowUpRight size={12} aria-hidden="true" />
          </a>
        </div>
      </div>
      <p className={styles.access}>
        Hosted MCP requires Video Use pilot access.
      </p>
    </div>
  );
}
