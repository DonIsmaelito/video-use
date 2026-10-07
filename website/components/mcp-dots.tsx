import { ConnectMcp } from '@/components/connect-mcp';
import { McpMascot } from '@/components/mcp-mascot';
import styles from './mcp-dots.module.css';

const characters = [
  { role: 'Video editor', style: 'editor' },
  { role: 'Motion designer', style: 'designer' },
  { role: '3D artist', style: 'artist' },
  { role: 'Storyteller', style: 'storyteller' },
] as const;

/** An airy MCP interlude between the creation and 3D collections. */
export function McpDots() {
  return (
    <section
      className={styles.section}
      aria-labelledby="mcp-dots-heading"
      data-mcp-promo="dots"
    >
      <div className={styles.banner}>
        <div className={styles.glow} aria-hidden="true" />
        <div className={styles.halftone} aria-hidden="true" />
        <div className={styles.content}>
          <h2 id="mcp-dots-heading">
            <span className={styles.titleLine}>
              Your AI chat
              <span className={styles.pearl}>
                <McpMascot character="pearl" />
              </span>
            </span>
            <span className={styles.titleLine}>Your video studio.</span>
          </h2>
          <p className={styles.description}>
            Create, edit, and bring ideas to life with Video Use MCP. Right
            inside your favorite AI chat.
          </p>
          <ConnectMcp className={styles.connect} label="Connect Video Use" />
        </div>
        <div className={styles.characters} aria-hidden="true">
          {characters.map((character) => (
            <div
              className={`${styles.character} ${styles[character.style]}`}
              key={character.role}
            >
              <span className={styles.label}>{character.role}</span>
              <span className={styles.sculpture}>
                <McpMascot character={character.style} />
                <svg
                  className={styles.cursor}
                  width="28"
                  height="32"
                  viewBox="0 0 28 32"
                  aria-hidden="true"
                >
                  <path
                    d="M5 3V25L11 19.5L15.5 29L20 26.8L15.5 17.5L24 17Z"
                    fill="#fff"
                    stroke="#151515"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
