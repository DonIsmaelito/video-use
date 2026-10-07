'use client';

import { useEffect, useRef, type CSSProperties } from 'react';
import { ArrowUp, AudioLines, Sparkles } from 'lucide-react';
import styles from './prompt-motion.module.css';

/** A native, twelve-second motion study. The CSS clock owns every frame. */
export function PromptMotion({ className }: { className?: string }) {
  const scene = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = scene.current;
    if (!element) return;

    let visible = false;
    let overlayOpen = false;
    const syncPlayback = () => {
      element.dataset.running = String(
        visible && !document.hidden && !overlayOpen,
      );
    };
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        syncPlayback();
      },
      { threshold: 0 },
    );
    const onOverlay = (event: Event) => {
      overlayOpen = Boolean((event as CustomEvent<boolean>).detail);
      syncPlayback();
    };

    observer.observe(element);
    document.addEventListener('visibilitychange', syncPlayback);
    window.addEventListener('videouse:overlay', onOverlay);
    window.addEventListener('pageshow', syncPlayback);
    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', syncPlayback);
      window.removeEventListener('videouse:overlay', onOverlay);
      window.removeEventListener('pageshow', syncPlayback);
    };
  }, []);

  return (
    <figure
      ref={scene}
      className={`${styles.scene} ${className ?? ''}`}
      data-prompt-motion
      data-running="false"
      aria-label="Just say it. See it move. A prompt brings an orange sculpture to life inside a video frame, then becomes an edit timeline."
    >
      <div className={styles.composition} aria-hidden="true">
        <div className={styles.ambience} />
        <div className={styles.copy}>
          <span className={styles.eyebrow}>FROM A FEW WORDS</span>
          <span className={styles.headline}>
            Just say it.
            <span>See it move.</span>
          </span>
        </div>

        <div className={styles.film}>
          <div className={styles.frameBehind} />
          <div className={styles.frame}>
            <span className={styles.frameCaption}>A LITTLE IMAGINATION.</span>
            <div className={styles.sculptureStage}>
              <div className={styles.sculpture}>
                {Array.from({ length: 12 }, (_, index) => (
                  <span
                    key={index}
                    className={styles.fin}
                    style={{ '--angle': `${index * 30}deg` } as CSSProperties}
                  />
                ))}
                <span className={styles.core} />
              </div>
            </div>
            <div className={styles.frameFooter}>
              <span className={styles.liveDot} />
              <AudioLines />
            </div>
          </div>
          <div className={styles.timeline}>
            <span className={styles.timelineClip} />
            <span className={styles.timelineClip} />
            <span className={styles.timelineClip} />
            <span className={styles.playhead} />
          </div>
        </div>

        <div className={styles.prompt}>
          <Sparkles className={styles.promptIcon} />
          <span className={styles.promptText}>
            <span>Make something worth watching.</span>
          </span>
          <span className={styles.send}>
            <ArrowUp />
          </span>
          <span className={styles.promptSweep} />
        </div>
      </div>
    </figure>
  );
}
