'use client';

import { useLayoutEffect, useRef, type ReactNode } from 'react';
import styles from './gallery-cards.module.css';

/** Pack cards in order, reserving adjacent columns for the larger lead demo. */
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
      const sizes = cards.map((card) => ({
        height: card.getBoundingClientRect().height,
        span: Math.min(
          columns,
          Math.max(
            1,
            Number.parseInt(
              getComputedStyle(card).getPropertyValue('--gallery-span'),
            ) || 1,
          ),
        ),
      }));
      const positions = sizes.map(({ height, span }) => {
        const available = Array.from({ length: columns - span + 1 }, (_, i) =>
          Math.max(...bottoms.slice(i, i + span)),
        );
        const top = Math.min(...available);
        const column = available.indexOf(top);
        bottoms.fill(top + height + gap, column, column + span);
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
