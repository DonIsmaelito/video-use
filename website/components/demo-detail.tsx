'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- Published media retain their original audio and burned captions. */
/* oxlint-disable jsx-a11y/no-noninteractive-tabindex -- The independently scrolling prompt needs keyboard focus for arrow and Page Down navigation. */

import { useState } from 'react';
import { ArrowUpRight, Check, Copy } from 'lucide-react';
import {
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { Disclosure } from '@/components/ui/disclosure';
import { ConnectMcp } from '@/components/connect-mcp';
import { TechniqueIcon } from '@/components/technique-icon';
import {
  buildChatPrompt,
  safeSourceUrl,
  type GalleryExample,
} from '@/lib/gallery';
import styles from './demo-detail.module.css';

function DemoSources({ example }: { example: GalleryExample }) {
  return (
    <Disclosure label="Sources" className={styles.sources}>
      {example.promptSource && <p>{example.promptSource}</p>}
      {safeSourceUrl(example.sourceRepo) && (
        <a
          href={safeSourceUrl(example.sourceRepo)!}
          target="_blank"
          rel="noreferrer"
        >
          Open-source inspiration <ArrowUpRight size={12} />
        </a>
      )}
      {safeSourceUrl(example.sourceArchive) && (
        <a
          href={safeSourceUrl(example.sourceArchive)!}
          target="_blank"
          rel="noreferrer"
        >
          Editable project <ArrowUpRight size={12} />
        </a>
      )}
      {safeSourceUrl(example.reviewUrl) && (
        <a
          href={safeSourceUrl(example.reviewUrl)!}
          target="_blank"
          rel="noreferrer"
        >
          Production notes <ArrowUpRight size={12} />
        </a>
      )}
      {example.mediaCredits?.map((credit) => (
        <p key={credit.url + credit.title}>
          {safeSourceUrl(credit.url) ? (
            <a
              href={safeSourceUrl(credit.url)!}
              target="_blank"
              rel="noreferrer"
            >
              {credit.title}
            </a>
          ) : (
            credit.title
          )}
          {' · '}
          {credit.creator}
          {credit.license && (
            <>
              {' · '}
              {safeSourceUrl(credit.licenseUrl) ? (
                <a
                  href={safeSourceUrl(credit.licenseUrl)!}
                  target="_blank"
                  rel="noreferrer"
                >
                  {credit.license}
                </a>
              ) : (
                credit.license
              )}
            </>
          )}
          {credit.changes && <>. {credit.changes}</>}
        </p>
      ))}
      <MediaCredit example={example} />
    </Disclosure>
  );
}

function MediaCredit({ example }: { example: GalleryExample }) {
  if (
    [
      'edit-velocity',
      'edit-freeze_poster',
      'edit-triptych',
      'edit-after_dark',
      'social-13-robot-hand-dialogue',
      'social-14-robot-action',
    ].includes(example.id)
  ) {
    return (
      <p>
        Modified excerpt from{' '}
        <a
          href="https://www.youtube.com/watch?v=R6MlUcmOul8"
          target="_blank"
          rel="noreferrer"
        >
          Tears of Steel
        </a>{' '}
        · (CC) Blender Foundation |{' '}
        <a href="https://mango.blender.org/" target="_blank" rel="noreferrer">
          mango.blender.org
        </a>{' '}
        ·{' '}
        <a
          href="https://creativecommons.org/licenses/by/3.0/"
          target="_blank"
          rel="noreferrer"
        >
          CC BY 3.0
        </a>
      </p>
    );
  }
  if (example.id === 'social-12-spring-story') {
    return (
      <p>
        Modified excerpt from{' '}
        <a
          href="https://studio.blender.org/projects/spring/pages/about/"
          target="_blank"
          rel="noreferrer"
        >
          Spring
        </a>{' '}
        ·{' '}
        <a
          href="https://www.blender.org/foundation/"
          target="_blank"
          rel="noreferrer"
        >
          Blender Foundation
        </a>{' '}
        ·{' '}
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noreferrer"
        >
          CC BY 4.0
        </a>
      </p>
    );
  }
  if (example.id === 'social-19-weekend-roundup') {
    return (
      <p>
        Music:{' '}
        <a
          href="https://freemusicarchive.org/music/John_Bartmann/retro-boogie/boogie-til-you-drop/"
          target="_blank"
          rel="noreferrer"
        >
          Boogie Til You Drop
        </a>{' '}
        by{' '}
        <a
          href="https://johnbartmann.com/music"
          target="_blank"
          rel="noreferrer"
        >
          John Bartmann
        </a>{' '}
        ·{' '}
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noreferrer"
        >
          CC BY 4.0
        </a>
        . Edited excerpt and mix.
      </p>
    );
  }
  return null;
}

export function DemoDetail({
  example,
  copied,
  onCopy,
}: {
  example: GalleryExample;
  copied: boolean;
  onCopy: () => void;
}) {
  const [videoError, setVideoError] = useState(false);
  const hasSources =
    example.promptSource ||
    safeSourceUrl(example.sourceRepo) ||
    safeSourceUrl(example.sourceArchive) ||
    safeSourceUrl(example.reviewUrl) ||
    example.mediaCredits?.length ||
    [
      'edit-velocity',
      'edit-freeze_poster',
      'edit-triptych',
      'edit-after_dark',
      'social-13-robot-hand-dialogue',
      'social-14-robot-action',
      'social-12-spring-story',
      'social-19-weekend-roundup',
    ].includes(example.id);

  return (
    <DialogContent
      className={styles.dialog}
      data-demo-dialog
      data-orientation={example.orientation}
    >
      <div className={styles.media}>
        {!videoError ? (
          <video
            src={example.video}
            poster={example.poster}
            controls
            playsInline
            autoPlay
            muted={example.muted ?? example.category === 'Motion Design'}
            loop={example.loop ?? example.category === 'Motion Design'}
            preload="metadata"
            aria-label={example.title}
            onError={() => setVideoError(true)}
          />
        ) : (
          <div className="video-error">
            <p>This preview couldn’t load.</p>
            <a href={example.video} target="_blank" rel="noreferrer">
              Open the video directly <ArrowUpRight size={14} />
            </a>
          </div>
        )}
      </div>
      <div className={styles.panel}>
        <header className={styles.header}>
          <p className={styles.category}>
            <TechniqueIcon technique={example.technique} />
            {example.category}
          </p>
          <DialogTitle className={styles.title}>{example.title}</DialogTitle>
          <DialogDescription className="sr-only">
            Watch the video and copy its prompt. {example.description}
          </DialogDescription>
        </header>
        <section
          className={styles.prompt}
          aria-labelledby="demo-prompt-heading"
        >
          <h3 id="demo-prompt-heading" className={styles.promptLabel}>
            {example.promptKind}
          </h3>
          <section
            className={styles.promptScroll}
            aria-label="Complete prompt that will be copied"
            tabIndex={0}
          >
            <p className={styles.promptText}>{buildChatPrompt(example)}</p>
            {hasSources && <DemoSources example={example} />}
          </section>
        </section>
        <footer className={styles.actions}>
          <button type="button" className={styles.copy} onClick={onCopy}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? 'Copied' : 'Copy Prompt'}
          </button>
          <ConnectMcp
            className={styles.connect}
            label="Connect your chat"
            compact
          />
        </footer>
      </div>
    </DialogContent>
  );
}
