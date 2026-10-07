'use client';

import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { usePreviewPlayback } from '@/components/preview-playback';

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
  const syncPlayback = useRef<() => void>(() => {});
  const { enabled, register, reportBlocked } = usePreviewPlayback();
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
    const sync = (allowPlayback = enabled) => {
      const shouldPlay =
        visible &&
        !suspended &&
        !overlayOpen &&
        !failed &&
        !document.hidden &&
        allowPlayback;
      wantsPlayback.current = shouldPlay;
      // Set both the HTML default and live property before requesting playback.
      // WebKit uses the muted/autoplay attributes for native scroll resumption.
      player.defaultMuted = true;
      player.muted = true;
      player.autoplay = shouldPlay;
      if (shouldPlay)
        player
          .play()
          .then(() => {
            if (!wantsPlayback.current) player.pause();
          })
          .catch((error: DOMException) => {
            if (error.name === 'NotAllowedError' && wantsPlayback.current)
              reportBlocked();
          });
      else {
        player.pause();
        setPlaying(false);
      }
    };
    syncPlayback.current = () => sync();
    const unregister = register(sync);
    const onVisibility = () => sync();
    sync();
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pageshow', onVisibility);
    return () => {
      wantsPlayback.current = false;
      player.autoplay = false;
      player.pause();
      syncPlayback.current = () => {};
      unregister();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pageshow', onVisibility);
    };
  }, [
    nearby,
    visible,
    suspended,
    overlayOpen,
    failed,
    enabled,
    register,
    reportBlocked,
  ]);

  return (
    <div
      ref={frame}
      className={`preview-media ${orientation} ${ambient ? 'has-ambient' : ''} ${playing ? 'is-playing' : ''}`}
    >
      {/* Optional ambient fill never crops the foreground film. */}
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
          autoPlay={enabled && visible && !suspended && !overlayOpen}
          playsInline
          loop
          preload="metadata"
          aria-hidden="true"
          onCanPlay={() => syncPlayback.current()}
          onLoadedData={() => syncPlayback.current()}
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
