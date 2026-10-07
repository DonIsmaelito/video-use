import { MousePointer2 } from 'lucide-react';
import { ConnectMcp } from '@/components/connect-mcp';
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
      <div className={styles.glow} aria-hidden="true" />
      <div className={styles.halftone} aria-hidden="true" />
      <div className={styles.content}>
        <p className={styles.eyebrow}>Video Use MCP</p>
        <h2 id="mcp-dots-heading">
          Your next video.
          <span>Starts in a chat.</span>
        </h2>
        <p className={styles.description}>
          Edit footage, animate an idea, or build a world in 3D.
          <br /> All inside your favorite AI chat.
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
            <span className={styles.dot}>
              <span className={styles.eyes} />
            </span>
            <MousePointer2 className={styles.cursor} size={20} />
          </div>
        ))}
      </div>
    </section>
  );
}
