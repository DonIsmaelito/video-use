'use client';

/* oxlint-disable jsx-a11y/prefer-tag-over-role, jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex -- Carousel slides use ARIA groups, not form fieldsets. The labeled scroll viewport is focusable so keyboard users can operate its horizontal scroll. */

import {
  Children,
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import styles from './featured-carousel.module.css';

/** Native touch/trackpad momentum with card stops; mouse dragging uses the same stops. */
export function FeaturedCarousel({ children }: { children: ReactNode }) {
  const items = Children.toArray(children);
  const placeholderCount = Math.max(0, 8 - items.length);
  const total = items.length + placeholderCount;
  const id = useId();
  const viewport = useRef<HTMLDivElement>(null);
  const press = useRef<{
    x: number;
    y: number;
    left: number;
    dragging: boolean;
  } | null>(null);
  const suppressClick = useRef(false);
  const [edges, setEdges] = useState({ previous: false, next: true });

  useEffect(() => {
    const track = viewport.current;
    if (!track) return;
    const update = () => {
      const previous = track.scrollLeft > 1;
      const next = track.scrollLeft < track.scrollWidth - track.clientWidth - 1;
      setEdges((value) =>
        value.previous === previous && value.next === next
          ? value
          : { previous, next },
      );
    };
    const resize = new ResizeObserver(update);
    resize.observe(track);
    track.addEventListener('scroll', update, { passive: true });
    update();
    return () => {
      resize.disconnect();
      track.removeEventListener('scroll', update);
    };
  }, []);

  function stops() {
    const track = viewport.current;
    if (!track) return [0];
    const max = track.scrollWidth - track.clientWidth;
    const inset = Number.parseFloat(getComputedStyle(track).paddingLeft) || 0;
    return [
      ...new Set(
        Array.from(track.children, (item) =>
          Math.min(max, (item as HTMLElement).offsetLeft - inset),
        ),
      ),
    ];
  }

  function closest(left: number, points = stops()) {
    return points.reduce(
      (best, point, index) =>
        Math.abs(point - left) < Math.abs(points[best] - left) ? index : best,
      0,
    );
  }

  function goTo(index: number, points = stops()) {
    viewport.current?.scrollTo({
      left: points[Math.max(0, Math.min(index, points.length - 1))],
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
    });
  }

  function move(direction: number) {
    goTo(closest(viewport.current?.scrollLeft ?? 0) + direction);
  }

  function endDrag(event: PointerEvent<HTMLDivElement>) {
    const start = press.current;
    press.current = null;
    if (!start?.dragging) return;
    const track = event.currentTarget;
    const points = stops();
    let destination = closest(track.scrollLeft, points);
    const origin = closest(start.left, points);
    const distance = start.x - event.clientX;
    // A deliberate short pull advances one card; long pulls can cross several.
    if (
      event.type === 'pointerup' &&
      destination === origin &&
      Math.abs(distance) > 60
    ) {
      destination += Math.sign(distance);
    }
    delete track.dataset.dragging;
    if (track.hasPointerCapture(event.pointerId))
      track.releasePointerCapture(event.pointerId);
    suppressClick.current = event.type === 'pointerup';
    goTo(destination, points);
  }

  return (
    <section
      className={`homepage-featured ${styles.carousel}`}
      aria-label="Featured Video Use workflows"
      aria-roledescription="carousel"
    >
      <p id={`${id}-hint`} className="sr-only">
        Swipe to explore. When focused, use the left and right arrow keys to
        move between use cases.
      </p>
      <div
        ref={viewport}
        id={id}
        className={styles.viewport}
        role="group"
        aria-label="Use cases"
        aria-describedby={`${id}-hint`}
        tabIndex={0}
        onDragStart={(event) => event.preventDefault()}
        onPointerDown={(event) => {
          suppressClick.current = false;
          if (event.pointerType !== 'mouse' || event.button !== 0) return;
          press.current = {
            x: event.clientX,
            y: event.clientY,
            left: event.currentTarget.scrollLeft,
            dragging: false,
          };
        }}
        onPointerMove={(event) => {
          const start = press.current;
          if (!start) return;
          if (event.buttons === 0) {
            endDrag(event);
            return;
          }
          const distance = event.clientX - start.x;
          if (!start.dragging) {
            if (
              Math.abs(distance) < 6 ||
              Math.abs(distance) < Math.abs(event.clientY - start.y)
            )
              return;
            start.dragging = true;
            event.currentTarget.dataset.dragging = 'true';
            event.currentTarget.setPointerCapture(event.pointerId);
          }
          event.preventDefault();
          event.currentTarget.scrollLeft = start.left - distance;
        }}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onClickCapture={(event) => {
          if (!suppressClick.current) return;
          event.preventDefault();
          event.stopPropagation();
          suppressClick.current = false;
        }}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key))
            return;
          event.preventDefault();
          if (event.key === 'Home') goTo(0);
          else if (event.key === 'End') goTo(stops().length - 1);
          else move(event.key === 'ArrowRight' ? 1 : -1);
        }}
      >
        {items.map((item, index) => (
          <div
            className={styles.slide}
            role="group"
            aria-roledescription="slide"
            aria-label={`${index + 1} of ${total}`}
            key={index}
          >
            {item}
          </div>
        ))}
        {Array.from({ length: placeholderCount }, (_, index) => (
          <div
            className={styles.slide}
            role="group"
            aria-roledescription="slide"
            aria-label={`${items.length + index + 1} of ${total}. Reserved use case`}
            key={`reserved-${index}`}
          >
            <div
              className={`featured-frame ${styles.placeholder}`}
              aria-hidden="true"
            />
          </div>
        ))}
      </div>
      <div className={styles.controls}>
        <button
          type="button"
          aria-label="Previous use case"
          aria-controls={id}
          disabled={!edges.previous}
          onClick={() => move(-1)}
        >
          <ChevronLeft size={18} />
        </button>
        <button
          type="button"
          aria-label="Next use case"
          aria-controls={id}
          disabled={!edges.next}
          onClick={() => move(1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </section>
  );
}
