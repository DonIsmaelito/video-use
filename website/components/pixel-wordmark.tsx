'use client';

import { useEffect, useRef, useState, type CSSProperties } from 'react';

// A small bitmap alphabet gives the wordmark real square pixels at every size.
const glyphs: Record<string, string[]> = {
  V: ['10001', '10001', '10001', '01010', '01010', '01010', '00100'],
  I: ['11111', '00100', '00100', '00100', '00100', '00100', '11111'],
  D: ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
  E: ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
  O: ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
  U: ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
  S: ['01111', '10000', '10000', '01110', '00001', '00001', '11110'],
};

const pixels: { x: number; y: number; phase: number }[] = [];
let cursor = 0;
for (const letter of 'VIDEO USE') {
  if (letter === ' ') {
    cursor += 2;
    continue;
  }
  glyphs[letter].forEach((row, y) => {
    [...row].forEach((pixel, x) => {
      if (pixel === '1')
        pixels.push({
          x: cursor + x,
          y,
          phase: (cursor + x) * 0.11 + y * 0.19,
        });
    });
  });
  cursor += 6;
}

export function PixelWordmark() {
  const footer = useRef<HTMLElement>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    let visible = false;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () =>
      setActive(visible && !document.hidden && !preference.matches);
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      update();
    });
    if (footer.current) observer.observe(footer.current);
    document.addEventListener('visibilitychange', update);
    preference.addEventListener('change', update);
    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', update);
      preference.removeEventListener('change', update);
    };
  }, []);

  return (
    <footer
      ref={footer}
      className={`pixel-footer ${active ? 'is-active' : ''}`}
      aria-label="Video Use"
    >
      <div className="pixel-crop" aria-hidden="true">
        <svg
          className="pixel-wordmark"
          viewBox={`0 0 ${cursor - 1} 7`}
          fill="currentColor"
          focusable="false"
        >
          {pixels.map(({ x, y, phase }) => (
            <rect
              key={`${x}-${y}`}
              className="wordmark-pixel"
              x={x}
              y={y}
              width=".9"
              height=".9"
              style={{ '--phase': `${-phase}s` } as CSSProperties}
            />
          ))}
        </svg>
      </div>
    </footer>
  );
}
