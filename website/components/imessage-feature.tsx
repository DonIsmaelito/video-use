import { ImagePlay, MessageCircle, ScanSearch } from 'lucide-react';
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
}: {
  screenshot: ConversationScreenshot | null;
  label: string;
}) {
  return (
    <figure className={styles.phoneStage} aria-label={label}>
      <div className={styles.phone}>
        <div className={styles.screen}>
          {screenshot ? (
            <Image
              className={styles.conversation}
              src={screenshot.src}
              width={screenshot.width}
              height={screenshot.height}
              alt={screenshot.alt}
              sizes="(max-width: 375px) 240px, 300px"
              loading="lazy"
              decoding="async"
            />
          ) : (
            <div className={styles.placeholder} aria-hidden="true">
              <MessageCircle size={38} strokeWidth={1.25} />
              <span>{label}</span>
              <span className={styles.placeholderNote}>Chat screenshot</span>
            </div>
          )}
        </div>
        <Image
          className={styles.frame}
          src="/imessage/iphone-frame.png"
          width={762}
          height={1502}
          alt=""
          sizes="(max-width: 375px) 290px, (max-width: 1023px) 330px, 356px"
          aria-hidden="true"
          loading="lazy"
          decoding="async"
        />
      </div>
    </figure>
  );
}

export function ImessageFeature() {
  // The real conversations are still to be supplied. Keep the draft local until
  // both screenshots are present; never publish invented chat content.
  if (
    process.env.NODE_ENV === 'production' &&
    (!screenshots.cameraRoll || !screenshots.references)
  ) {
    return null;
  }

  return (
    <section
      id="imessage"
      className={styles.section}
      aria-labelledby="imessage-heading"
    >
      <div className={styles.inner}>
        <header className={styles.header}>
          <span className={styles.eyebrow}>
            <MessageCircle size={15} aria-hidden="true" />
            A conversation away
          </span>
          <h2 id="imessage-heading">Video Use in iMessage</h2>
          <p>Your footage. Your ideas. One conversation.</p>
        </header>

        <div className={styles.rows}>
          <article className={styles.row} aria-labelledby="imessage-edit">
            <ConversationPhone
              screenshot={screenshots.cameraRoll}
              label="Editing from your camera roll"
            />
            <div className={styles.context}>
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
                Share clips from your camera roll and say what you have in mind.
                Video Use finds the moments, makes the edit, and sends it back
                in iMessage.
              </p>
              <div className={styles.detail}>
                <span className={styles.step}>01</span>
                Your footage, with the context to make it yours.
              </div>
            </div>
          </article>

          <article
            className={`${styles.row} ${styles.reverse}`}
            aria-labelledby="imessage-create"
          >
            <div className={styles.context}>
              <span className={styles.label}>
                <ScanSearch size={16} aria-hidden="true" />
                Create from an idea
              </span>
              <h3 id="imessage-create">
                Send the idea.
                <br />
                <span>Find the direction.</span>
              </h3>
              <p>
                Describe the video you want to make. Video Use searches the web
                for references, helps you choose a direction, and creates with
                you in the same conversation.
              </p>
              <div className={styles.detail}>
                <span className={styles.step}>02</span>
                References, creation, and revisions. Keep texting.
              </div>
            </div>
            <ConversationPhone
              screenshot={screenshots.references}
              label="Creating with visual references"
            />
          </article>
        </div>
      </div>
    </section>
  );
}
