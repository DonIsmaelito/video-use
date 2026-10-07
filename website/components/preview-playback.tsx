'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Pause, Play } from 'lucide-react';

type PlayerSync = (enabled: boolean) => void;
type Playback = {
  enabled: boolean;
  blocked: boolean;
  register: (sync: PlayerSync) => () => void;
  reportBlocked: () => void;
  toggle: () => void;
};

const PreviewPlaybackContext = createContext<Playback | null>(null);

/** Keep an explicit preview choice across collection navigation. */
export function PreviewPlaybackProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const explicitChoice = useRef(false);
  const players = useRef(new Set<PlayerSync>());

  useEffect(() => {
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => {
      if (!explicitChoice.current) setEnabled(!preference.matches);
    };
    update();
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  const register = useCallback((sync: PlayerSync) => {
    players.current.add(sync);
    return () => {
      players.current.delete(sync);
    };
  }, []);
  const reportBlocked = useCallback(() => setBlocked(true), []);

  const retry = useCallback(() => {
    setBlocked(false);
    // Run play() inside the trusted gesture, before React schedules an effect.
    players.current.forEach((sync) => sync(true));
  }, []);

  useEffect(() => {
    if (!enabled || !blocked) return;
    const onGesture = (event: Event) => {
      if (
        event.target instanceof Element &&
        event.target.closest('.preview-playback-toggle')
      )
        return;
      if (event.isTrusted) retry();
    };
    document.addEventListener('pointerdown', onGesture, { once: true });
    document.addEventListener('keydown', onGesture, { once: true });
    return () => {
      document.removeEventListener('pointerdown', onGesture);
      document.removeEventListener('keydown', onGesture);
    };
  }, [enabled, blocked, retry]);

  const toggle = useCallback(() => {
    const next = !enabled || blocked;
    explicitChoice.current = true;
    setEnabled(next);
    setBlocked(false);
    players.current.forEach((sync) => sync(next));
  }, [enabled, blocked]);

  const value = useMemo(
    () => ({ enabled, blocked, register, reportBlocked, toggle }),
    [enabled, blocked, register, reportBlocked, toggle],
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

export function PreviewPlaybackToggle() {
  const { enabled, blocked, toggle } = usePreviewPlayback();
  const paused = !enabled || blocked;
  const label = paused ? 'Play video previews' : 'Pause video previews';
  return (
    <button
      className="preview-playback-toggle"
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      data-paused={paused || undefined}
    >
      {paused ? <Play size={16} /> : <Pause size={16} />}
    </button>
  );
}
