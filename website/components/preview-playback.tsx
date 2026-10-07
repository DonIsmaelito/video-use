'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';

type PlayerSync = () => void;
type Playback = {
  register: (sync: PlayerSync) => () => void;
  reportBlocked: () => void;
};

const PreviewPlaybackContext = createContext<Playback | null>(null);

/** Retry rejected autoplay during normal browsing without a playback control. */
export function PreviewPlaybackProvider({ children }: { children: ReactNode }) {
  const blocked = useRef(false);
  const players = useRef(new Set<PlayerSync>());

  const register = useCallback((sync: PlayerSync) => {
    players.current.add(sync);
    return () => {
      players.current.delete(sync);
    };
  }, []);
  const reportBlocked = useCallback(() => {
    blocked.current = true;
  }, []);

  useEffect(() => {
    const onGesture = (event: Event) => {
      if (!event.isTrusted || !blocked.current) return;
      blocked.current = false;
      // Keep play() inside the trusted gesture, before React schedules effects.
      players.current.forEach((sync) => sync());
    };
    document.addEventListener('pointerdown', onGesture);
    document.addEventListener('keydown', onGesture);
    return () => {
      document.removeEventListener('pointerdown', onGesture);
      document.removeEventListener('keydown', onGesture);
    };
  }, []);

  const value = useMemo(
    () => ({ register, reportBlocked }),
    [register, reportBlocked],
  );

  return (
    <PreviewPlaybackContext.Provider value={value}>
      {children}
    </PreviewPlaybackContext.Provider>
  );
}

export function usePreviewPlayback() {
  const playback = useContext(PreviewPlaybackContext);
  if (!playback) throw new Error('Preview media needs PreviewPlaybackProvider');
  return playback;
}
