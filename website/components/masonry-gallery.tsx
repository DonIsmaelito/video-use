'use client';

import { useLayoutEffect, useRef, type ReactNode } from 'react';
import styles from './gallery-cards.module.css';

/** Pack the original card order into equal-width columns without cropping media. */
export function MasonryGallery({ children }: { children: ReactNode }) {
  const grid = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const container = grid.current;
    if (!container) return;
    const cards = Array.from(container.children) as HTMLElement[];
    let scheduled = 0;

    function layout() {
      if (!container || !container.clientWidth) return;
      const css = getComputedStyle(container);
      const columns = Number(css.getPropertyValue('--gallery-columns')) || 2;
      const gap = Number.parseFloat(css.columnGap) || 8;
      const width =
        (container.getBoundingClientRect().width - gap * (columns - 1)) /
        columns;
      const bottoms = Array<number>(columns).fill(0);

      container.dataset.masonry = 'true';
      // Read natural heights together before writing positions. ResizeObserver
      // also catches font changes and keeps controls inside their own card.
      const heights = cards.map((card) => card.getBoundingClientRect().height);
      const positions = heights.map((height) => {
        const column = bottoms.indexOf(Math.min(...bottoms));
        const top = bottoms[column];
        bottoms[column] += height + gap;
        return { left: column * (width + gap), top };
      });
      cards.forEach((card, index) => {
        card.style.left = `${positions[index].left}px`;
        card.style.top = `${positions[index].top}px`;
      });
      container.style.height = `${Math.max(0, ...bottoms) - (cards.length ? gap : 0)}px`;
    }

    function schedule() {
      cancelAnimationFrame(scheduled);
      scheduled = requestAnimationFrame(layout);
    }

    layout();
    const resize = new ResizeObserver(schedule);
    resize.observe(container);
    cards.forEach((card) => resize.observe(card));
    return () => {
      cancelAnimationFrame(scheduled);
      resize.disconnect();
    };
  }, [children]);

  return (
    <div ref={grid} className={`video-grid ${styles.grid}`}>
      {children}
    </div>
  );
}
