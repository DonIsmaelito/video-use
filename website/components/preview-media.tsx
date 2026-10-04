'use client';

import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';

/** Each card fetches media near the viewport and only plays while visible. */
export function PreviewMedia({
  src,
  poster,
  suspended = false,
  orientation = 'landscape',
  ambient = false,
}: {
  src: string;
  poster: string;
  suspended?: boolean;
  orientation?: string;
  ambient?: boolean;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const wantsPlayback = useRef(false);
  const [nearby, setNearby] = useState(false);
  const [visible, setVisible] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const [overlayOpen, setOverlayOpen] = useState(false);

  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    const preload = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setNearby(true);
          preload.disconnect();
        }
      },
      { rootMargin: '200px' },
    );
    const playback = new IntersectionObserver(([entry]) =>
      setVisible(entry.isIntersecting),
    );
    preload.observe(target);
    playback.observe(target);
    const onOverlay = (event: Event) =>
      setOverlayOpen((event as CustomEvent<boolean>).detail);
    window.addEventListener('videouse:overlay', onOverlay);
    return () => {
      preload.disconnect();
      playback.disconnect();
      window.removeEventListener('videouse:overlay', onOverlay);
    };
  }, []);

  useEffect(() => {
    const player = video.current;
    if (!player) return;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => {
      const shouldPlay =
        visible &&
        !suspended &&
        !overlayOpen &&
        !failed &&
        !document.hidden &&
        !preference.matches;
      wantsPlayback.current = shouldPlay;
      if (shouldPlay)
        player
          .play()
          .then(() => {
            if (!wantsPlayback.current) player.pause();
          })
          .catch(() => {});
      else {
        player.pause();
        setPlaying(false);
      }
    };
    sync();
    document.addEventListener('visibilitychange', sync);
    preference.addEventListener('change', sync);
    return () => {
      wantsPlayback.current = false;
      player.pause();
      document.removeEventListener('visibilitychange', sync);
      preference.removeEventListener('change', sync);
    };
  }, [nearby, visible, suspended, overlayOpen, failed]);

  return (
    <div
      ref={frame}
      className={`preview-media ${orientation} ${ambient ? 'has-ambient' : ''} ${playing ? 'is-playing' : ''}`}
    >
      {/* Tall gallery windows preserve the complete film over its blurred poster. */}
      {ambient && (
        <Image
          src={poster}
          className="card-ambient"
          alt=""
          loading="lazy"
          width={320}
          height={180}
          unoptimized
        />
      )}
      <Image
        src={poster}
        className="card-poster"
        alt=""
        loading="lazy"
        width={640}
        height={360}
        unoptimized
      />
      {nearby && !failed && (
        <video
          ref={video}
          src={src}
          muted
          playsInline
          loop
          preload="metadata"
          aria-hidden="true"
          onCanPlay={() => {
            if (wantsPlayback.current) video.current?.play().catch(() => {});
          }}
          onPlaying={() => {
            if (wantsPlayback.current) setPlaying(true);
            else video.current?.pause();
          }}
          onError={() => {
            wantsPlayback.current = false;
            video.current?.pause();
            setPlaying(false);
            setFailed(true);
          }}
        />
      )}
    </div>
  );
}
