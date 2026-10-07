import { ImagePlay, MessageCircle, ScanSearch, Sparkles } from 'lucide-react';
import Image from 'next/image';
import screenshots from '@/data/imessage-conversations.json';
import styles from './imessage-feature.module.css';

type ConversationScreenshot = {
  src: string;
  width: number;
  height: number;
  alt: string;
};

function ConversationPhone({
  screenshot,
  label,
  side,
}: {
  screenshot: ConversationScreenshot;
  label: string;
  side: 'left' | 'right';
}) {
  return (
    <figure
      className={`${styles.phoneStage} ${styles[side]}`}
      aria-label={label}
      aria-describedby={side === 'left' ? 'imessage-edit' : 'imessage-create'}
    >
      <div className={styles.phone}>
        <a
          className={styles.screen}
          href={screenshot.src}
          target="_blank"
          rel="noopener"
          aria-label={`${label} — view full-size conversation in a new tab`}
        >
          <Image
            className={styles.conversation}
            src={screenshot.src}
            width={screenshot.width}
            height={screenshot.height}
            alt={screenshot.alt}
            sizes="(max-width: 540px) 30vw, (max-width: 1023px) 154px, 240px"
            loading="lazy"
            decoding="async"
          />
        </a>
        <Image
          className={styles.frame}
          src="/imessage/iphone-frame.png"
          width={762}
          height={1502}
          alt=""
          sizes="(max-width: 540px) 36vw, (max-width: 1023px) 184px, 286px"
          aria-hidden="true"
          loading="lazy"
          decoding="async"
        />
      </div>
    </figure>
  );
}

export function ImessageFeature() {
  return (
    <section
      id="imessage"
      className={styles.section}
      aria-labelledby="imessage-heading"
    >
      <div className={styles.composition}>
        <header className={styles.header}>
          <span className={styles.newBadge}>
            <Sparkles size={13} aria-hidden="true" />
            NEW!
          </span>
          <h2 id="imessage-heading">
            Video Use{' '}
            <span className={styles.imessageLine}>
              in{' '}
              <span className={styles.messageIcon} aria-hidden="true">
                <MessageCircle fill="currentColor" strokeWidth={0} />
              </span>{' '}
              iMessage
            </span>
          </h2>
          <p>
            <span>Your footage. Your ideas.</span>{' '}
            <span>One conversation.</span>
          </p>
        </header>

        <ConversationPhone
          screenshot={screenshots.cameraRoll}
          label="Editing from your camera roll"
          side="left"
        />

        <div className={styles.contexts}>
          <article className={styles.context} aria-labelledby="imessage-edit">
            <span className={styles.label}>
              <ImagePlay size={16} aria-hidden="true" />
              Edit your footage
            </span>
            <h3 id="imessage-edit">
              Your camera roll.
              <br />
              <span>Your next video.</span>
            </h3>
            <p>
              Share clips from your camera roll. Video Use finds the moments,
              makes the edit, and sends your video back in iMessage.
            </p>
          </article>

          <article className={styles.context} aria-labelledby="imessage-create">
            <span className={styles.label}>
              <ScanSearch size={16} aria-hidden="true" />
              Create from an idea
            </span>
            <h3 id="imessage-create">
              Send the idea.
              <br />
              <span>Find the look.</span>
            </h3>
            <p>
              Send an idea. Video Use finds references on the web, helps shape
              the direction, and creates your video in iMessage.
            </p>
          </article>
        </div>

        <ConversationPhone
          screenshot={screenshots.references}
          label="Creating with visual references"
          side="right"
        />
      </div>
    </section>
  );
}
