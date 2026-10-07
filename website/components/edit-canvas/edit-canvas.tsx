'use client';

import { useEffect, useRef } from 'react';
import Image from 'next/image';
import { PreviewMedia } from '@/components/preview-media';
import footage from './footage.json';
import styles from './edit-canvas.module.css';

/** A wordless editing composition built from an existing gallery film. */
export function EditCanvas({ className }: { className?: string }) {
  const scene = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = scene.current;
    if (!element) return;
    let visible = false;
    let overlayOpen = false;
    const sync = () => {
      element.dataset.running = String(
        visible && !document.hidden && !overlayOpen,
      );
    };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      sync();
    });
    const onOverlay = (event: Event) => {
      overlayOpen = Boolean((event as CustomEvent<boolean>).detail);
      sync();
    };
    observer.observe(element);
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pageshow', sync);
    window.addEventListener('videouse:overlay', onOverlay);
    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', sync);
      window.removeEventListener('pageshow', sync);
      window.removeEventListener('videouse:overlay', onOverlay);
    };
  }, []);

  return (
    <figure
      ref={scene}
      className={`${styles.scene} ${className ?? ''}`}
      data-edit-canvas
      data-running="false"
      aria-label="A moving film edit: real footage, layered film frames, an orange selection guide and an audio waveform."
    >
      <div className={styles.stage} aria-hidden="true">
        <div className={styles.surface}>
          <div className={styles.ruler} />
          <div className={styles.contactStrip}>
            {[...footage.frames, ...footage.frames].map((frame, index) => (
              <div className={styles.contactFrame} key={index}>
                <Image
                  src={frame.src}
                  alt=""
                  width={640}
                  height={360}
                  unoptimized
                  draggable={false}
                  loading="lazy"
                />
              </div>
            ))}
          </div>

          <div className={styles.selected}>
            <div className={styles.offsetFrame} />
            <div className={styles.shot}>
              <PreviewMedia src={footage.video} poster={footage.poster} />
            </div>
            <span className={`${styles.handle} ${styles.topLeft}`} />
            <span className={`${styles.handle} ${styles.topRight}`} />
            <span className={`${styles.handle} ${styles.bottomLeft}`} />
            <span className={`${styles.handle} ${styles.bottomRight}`} />
            <div className={styles.cropGuides} />
          </div>

          <div className={styles.timeline}>
            <div className={styles.timelineFrames}>
              {[...footage.frames, ...footage.frames, ...footage.frames].map(
                (frame, index) => (
                  <Image
                    key={index}
                    src={frame.src}
                    alt=""
                    width={160}
                    height={90}
                    unoptimized
                    draggable={false}
                    loading="lazy"
                  />
                ),
              )}
            </div>
            <svg
              className={styles.waveform}
              viewBox="0 0 600 32"
              preserveAspectRatio="none"
            >
              <path
                d={footage.waveform}
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div className={styles.playhead}>
            <span />
          </div>
        </div>
        <div className={styles.edgeShade} />
      </div>
    </figure>
  );
}
