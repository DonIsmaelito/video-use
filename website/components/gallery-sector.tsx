'use client';

import { useLayoutEffect, useRef, type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import type { Sector } from '@/lib/sectors';
import styles from './gallery-sector.module.css';

/** A finite window into a collection, with the next page at its faded edge. */
export function GallerySector({
  sector,
  count,
  children,
}: {
  sector: Sector;
  count: number;
  children: ReactNode;
}) {
  const preview = useRef<HTMLDivElement>(null);
  const viewMore = useRef<HTMLAnchorElement>(null);

  useLayoutEffect(() => {
    const viewport = preview.current;
    if (!viewport) return;
    const cards = Array.from(
      viewport.querySelectorAll<HTMLElement>('.video-card'),
    );
    let frame = 0;
    const update = () => {
      const edge = viewport.getBoundingClientRect().bottom - 100;
      for (const card of cards) {
        // A clipped card is a decorative teaser, never a hidden tab stop.
        const clipped = card.getBoundingClientRect().bottom > edge;
        if (clipped && card.contains(document.activeElement))
          viewMore.current?.focus();
        card.inert = clipped;
        if (clipped) card.setAttribute('aria-hidden', 'true');
        else card.removeAttribute('aria-hidden');
      }
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(viewport);
    if (viewport.firstElementChild)
      observer.observe(viewport.firstElementChild);
    cards.forEach((card) => observer.observe(card));
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      cards.forEach((card) => {
        card.inert = false;
        card.removeAttribute('aria-hidden');
      });
    };
  }, []);

  return (
    <section
      className={styles.sector}
      aria-labelledby={`${sector.id}-heading`}
      data-sector={sector.id}
    >
      <header className={styles.heading}>
        <div>
          <h2 id={`${sector.id}-heading`}>
            <Link href={sector.href}>{sector.title}</Link>
          </h2>
          <p>{sector.description}</p>
        </div>
        <span className={styles.count}>{count} examples</span>
      </header>
      <div className={styles.window} ref={preview}>
        {children}
        <div className={styles.fade}>
          <Link
            href={sector.href}
            className={styles.viewMore}
            ref={viewMore}
            aria-label={`${sector.action} ${sector.title}`}
          >
            {sector.action}
            <ArrowRight size={17} />
          </Link>
        </div>
      </div>
    </section>
  );
}
