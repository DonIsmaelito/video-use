'use client';

import { useEffect, useRef, useState } from 'react';

export type LikeState = { count: number; liked: boolean };
type Likes = Record<string, LikeState>;

async function readLikes(): Promise<Likes> {
  const response = await fetch('/api/likes', { cache: 'no-store' });
  if (!response.ok) throw new Error('Likes unavailable');
  return (await response.json()).likes;
}

/** One batched read; all appearances of a film share the same saved state. */
export function useGalleryLikes(onError: (message: string) => void) {
  const [likes, setLikes] = useState<Likes>({});
  const [pending, setPending] = useState<Set<string>>(new Set());
  const inFlight = useRef(new Set<string>());
  const initialRead = useRef<Promise<Likes> | null>(null);

  useEffect(() => {
    let active = true;
    initialRead.current ??= readLikes();
    initialRead.current
      .then((data) => {
        if (active) setLikes(data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  async function toggle(id: string) {
    if (inFlight.current.has(id)) return;
    inFlight.current.add(id);
    setPending(new Set(inFlight.current));
    let previous = likes[id];
    try {
      // Recover from an unavailable initial read before deciding like vs unlike.
      if (!previous)
        previous = (
          await (initialRead.current?.catch(() => readLikes()) ?? readLikes())
        )[id];
      if (!previous) throw new Error('Unknown example');
      const liked = !previous.liked;
      setLikes((current) => ({
        ...current,
        [id]: {
          liked,
          count: Math.max(0, previous.count + (liked ? 1 : -1)),
        },
      }));
      const response = await fetch('/api/likes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, liked }),
      });
      if (!response.ok) throw new Error('Could not save like');
      const saved: LikeState = await response.json();
      setLikes((current) => ({ ...current, [id]: saved }));
    } catch {
      if (previous) setLikes((current) => ({ ...current, [id]: previous }));
      onError('Couldn’t save your like. Try again.');
    } finally {
      inFlight.current.delete(id);
      setPending(new Set(inFlight.current));
    }
  }

  return { likes, pending, toggle };
}
