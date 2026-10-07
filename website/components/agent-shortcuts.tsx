import Image from 'next/image';
import { ArrowUpRight, Terminal } from 'lucide-react';
import { ConnectMcp } from '@/components/connect-mcp';
import type { McpSetupClient } from '@/lib/mcp-setup';
import styles from './agent-shortcuts.module.css';

const agents = [
  {
    id: 'chatgpt',
    name: 'ChatGPT',
    description: 'From a conversation to a finished video.',
  },
  {
    id: 'claude',
    name: 'Claude',
    description: 'Think it through. Bring it to life.',
  },
  {
    id: 'cursor',
    name: 'Cursor',
    description: 'Create product demos from your editor.',
  },
  {
    id: 'openclaw',
    name: 'OpenClaw',
    description: 'Put video into your agent’s workflow.',
  },
  {
    id: 'hermes',
    name: 'Hermes',
    description: 'Research, create, and edit with Nous.',
  },
  {
    id: 'url',
    name: 'Your agent',
    description: 'Your tools. Your workflow. One MCP.',
  },
] as const;

export function AgentShortcuts({
  onSelectAgent,
}: {
  onSelectAgent: (client: McpSetupClient) => void;
}) {
  return (
    <section
      id="agents"
      className={styles.section}
      aria-labelledby="agents-heading"
    >
      <h2 id="agents-heading" className="sr-only">
        Video Use in your favorite agent
      </h2>
      <div className={styles.layout}>
        {/* Reserved for the user's next showcase film. Intentionally blank. */}
        <div className={styles.showcase} aria-hidden="true" />
        <div className={styles.cards}>
          {agents.map((agent) => {
            const content = (
              <>
                <span className={styles.top}>
                  <span className={styles.icon}>
                    {agent.id === 'url' ? (
                      <Terminal size={28} aria-hidden="true" />
                    ) : (
                      <Image
                        unoptimized
                        className={
                          agent.id === 'chatgpt' ? styles.openai : undefined
                        }
                        src={`/clients/${agent.id}.${agent.id === 'hermes' ? 'png' : 'svg'}`}
                        alt=""
                        width={agent.id === 'chatgpt' ? 64 : 28}
                        height={agent.id === 'chatgpt' ? 64 : 28}
                      />
                    )}
                  </span>
                  <ArrowUpRight
                    className={styles.arrow}
                    size={15}
                    aria-hidden="true"
                  />
                </span>
                <span className={styles.copy}>
                  <span className={styles.name}>{agent.name}</span>
                  <span className={styles.description}>
                    {agent.description}
                  </span>
                </span>
              </>
            );

            return agent.id === 'chatgpt' ||
              agent.id === 'claude' ||
              agent.id === 'cursor' ? (
              <ConnectMcp
                key={agent.id}
                className={styles.card}
                label={`Use Video Use in ${agent.name}`}
                initialClient={agent.id}
              >
                {content}
              </ConnectMcp>
            ) : (
              <a
                key={agent.id}
                className={styles.card}
                href="#mcp-command"
                onClick={() => onSelectAgent(agent.id)}
                aria-label={`Set up Video Use in ${agent.name}`}
              >
                {content}
              </a>
            );
          })}
        </div>
      </div>
    </section>
  );
}
