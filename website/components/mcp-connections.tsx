import Image from 'next/image';
import Link from 'next/link';
import { McpTerminal } from '@/components/mcp-terminal';
import type { McpSetupClient } from '@/lib/mcp-setup';
import styles from './mcp-connections.module.css';

export function McpConnections({
  client,
  onClientChange,
}: {
  client: McpSetupClient;
  onClientChange: (client: McpSetupClient) => void;
}) {
  return (
    <section
      className={styles.section}
      aria-labelledby="mcp-connections-heading"
    >
      <div className={styles.grid} aria-hidden="true" />
      <div className={styles.stage}>
        <div className={styles.stack}>
          <div className={`${styles.tile} ${styles.far}`}>
            <Image
              unoptimized
              src="/clients/pi.svg"
              alt="Pi"
              width={26}
              height={26}
            />
          </div>
          <div className={`${styles.tile} ${styles.middle}`}>
            <Image
              unoptimized
              src="/clients/cursor.svg"
              alt="Cursor"
              width={32}
              height={32}
            />
          </div>
          <div className={`${styles.tile} ${styles.near}`}>
            <Image
              unoptimized
              className={styles.openai}
              src="/clients/chatgpt.svg"
              alt="OpenAI"
              width={76}
              height={76}
            />
          </div>
          <Link
            className={`${styles.tile} ${styles.brand}`}
            href="/mcp"
            aria-label="Explore Video Use MCP by Browser Use"
          >
            <Image
              unoptimized
              src="/brand/browser-use.svg"
              alt="Browser Use"
              width={52}
              height={52}
            />
          </Link>
          <div className={`${styles.tile} ${styles.near}`}>
            <Image
              unoptimized
              src="/clients/claude.svg"
              alt="Claude"
              width={38}
              height={38}
            />
          </div>
          <div className={`${styles.tile} ${styles.middle}`}>
            <Image
              unoptimized
              className={styles.hermes}
              src="/clients/hermes.png"
              alt="Hermes"
              width={32}
              height={32}
            />
          </div>
          <div className={`${styles.tile} ${styles.far}`}>
            <Image
              unoptimized
              src="/clients/openclaw.svg"
              alt="OpenClaw"
              width={26}
              height={26}
            />
          </div>
        </div>
      </div>
      <h2 id="mcp-connections-heading" className={styles.heading}>
        <span>Video Use MCP.</span> Your video studio, inside your agent.
      </h2>
      <McpTerminal client={client} onClientChange={onClientChange} />
    </section>
  );
}
