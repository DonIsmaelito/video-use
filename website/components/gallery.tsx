'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  categories,
  examples,
  filterExamples,
  formatDuration,
  type Example,
} from '@/lib/gallery';

function VideoCard({
  example,
  open,
  copy,
  copied,
  suspended,
}: {
  example: Example;
  open: () => void;
  copy: () => void;
  copied: boolean;
  suspended: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const frame = useRef<HTMLButtonElement>(null);
  const wantsPlayback = useRef(false);
  const [nearby, setNearby] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const [inView, setInView] = useState(false);

  const stop = () => {
    wantsPlayback.current = false;
    video.current?.pause();
    setPlaying(false);
  };

  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    // Mount media just before it enters view; only visible cards play.
    const preloadObserver = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setNearby(true);
          preloadObserver.disconnect();
        }
      },
      { rootMargin: '200px' },
    );
    const playbackObserver = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting);
    });
    preloadObserver.observe(target);
    playbackObserver.observe(target);
    return () => {
      preloadObserver.disconnect();
      playbackObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    const player = video.current;
    if (!player) return;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const syncPlayback = () => {
      const shouldPlay =
        inView &&
        !suspended &&
        !failed &&
        !document.hidden &&
        !preference.matches;
      wantsPlayback.current = shouldPlay;
      if (shouldPlay) {
        player
          .play()
          .then(() => {
            if (!wantsPlayback.current) player.pause();
          })
          .catch(() => {});
      } else {
        player.pause();
        setPlaying(false);
      }
    };
    syncPlayback();
    document.addEventListener('visibilitychange', syncPlayback);
    preference.addEventListener('change', syncPlayback);
    return () => {
      wantsPlayback.current = false;
      player.pause();
      document.removeEventListener('visibilitychange', syncPlayback);
      preference.removeEventListener('change', syncPlayback);
    };
  }, [nearby, inView, suspended, failed]);

  return (
    <article className="video-card" aria-label={example.title}>
      <button
        ref={frame}
        type="button"
        className={`video-frame ${playing ? 'is-playing' : ''} ${example.orientation}`}
        onClick={open}
        aria-label={`Watch ${example.title} and view its prompt`}
      >
        <img
          className="card-poster"
          src={example.poster}
          alt=""
          loading="lazy"
          width="640"
          height="480"
        />
        {nearby && (
          <video
            ref={video}
            src={example.video}
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
              setFailed(true);
              stop();
            }}
          />
        )}
        <span className="video-shade" />
        <span className="card-title">{example.title}</span>
        <span className="card-prompt" aria-hidden="true">
          <span className="card-prompt-label">Prompt</span>
          <span className="card-prompt-text">{example.prompt}</span>
        </span>
        <span className="video-duration">
          {formatDuration(example.duration)}
        </span>
      </button>
      <div className="card-meta">
        <Button
          variant="ghost"
          className={`copy-card ${copied ? 'copied' : ''}`}
          onClick={copy}
          aria-label={`Copy prompt for ${example.title}`}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy prompt'}
        </Button>
      </div>
    </article>
  );
}

export function Gallery() {
  const [category, setCategory] = useState('All examples');
  const [selected, setSelected] = useState<Example | null>(null);
  const [copied, setCopied] = useState('');
  const [message, setMessage] = useState('');
  const [manualCopy, setManualCopy] = useState('');
  const [videoError, setVideoError] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);
  const visible = filterExamples(category);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  useEffect(() => {
    if (manualCopy) manualText.current?.select();
  }, [manualCopy]);

  async function copyText(text: string, key: string, notice: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setMessage(notice);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        setCopied('');
        setMessage('');
      }, 2400);
    } catch {
      setManualCopy(text);
    }
  }

  function open(example: Example) {
    setSelected(example);
    setVideoError(false);
  }

  return (
    <>
      <section
        id="examples"
        className="gallery-section"
        aria-label="Video examples and prompts"
      >
        <div className="filter-bar">
          <div
            className="filter-list"
            role="group"
            aria-label="Filter video examples"
          >
            {categories.map((item) => (
              <Button
                key={item}
                variant="ghost"
                className={`filter-pill ${category === item ? 'active' : ''}`}
                aria-pressed={category === item}
                onClick={() => setCategory(item)}
              >
                {item === 'All examples' ? 'All' : item}
                <span className="filter-count">
                  {item === 'All examples'
                    ? examples.length
                    : examples.filter((example) => example.category === item)
                        .length}
                </span>
              </Button>
            ))}
          </div>
        </div>
        <p className="sr-only" aria-live="polite">
          {visible.length} examples
        </p>
        {categories
          .slice(1)
          .filter((item) => category === 'All examples' || category === item)
          .map((item) => {
            const items = filterExamples(item);
            const headingId = `category-${item.toLowerCase().replaceAll(' ', '-')}`;
            return (
              <section
                key={item}
                className="gallery-category"
                aria-labelledby={headingId}
              >
                <header className="category-heading">
                  <h2 id={headingId}>{item}</h2>
                  <span>{items.length}</span>
                </header>
                <div className="video-grid">
                  {items.map((example) => (
                    <VideoCard
                      key={example.id}
                      example={example}
                      open={() => open(example)}
                      copy={() =>
                        copyText(example.prompt, example.id, 'Prompt copied.')
                      }
                      copied={copied === example.id}
                      suspended={selected !== null || !!manualCopy}
                    />
                  ))}
                </div>
              </section>
            );
          })}
      </section>
      <Dialog
        open={selected !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setSelected(null);
        }}
      >
        {selected && (
          <DialogContent className={`example-dialog ${selected.orientation}`}>
            <DialogTitle className="sr-only">{selected.title}</DialogTitle>
            <DialogDescription className="sr-only">
              Watch the video and copy its prompt.
            </DialogDescription>
            <div className={`dialog-video ${selected.orientation}`}>
              {!videoError ? (
                <video
                  key={selected.id}
                  src={selected.video}
                  poster={selected.poster}
                  controls
                  playsInline
                  autoPlay
                  muted={selected.category === 'Motion Design'}
                  loop={selected.category === 'Motion Design'}
                  preload="metadata"
                  onError={() => setVideoError(true)}
                />
              ) : (
                <div className="video-error">
                  <p>This preview couldn’t load.</p>
                  <a href={selected.video} target="_blank" rel="noreferrer">
                    Open the video directly <ArrowUpRight size={14} />
                  </a>
                </div>
              )}
            </div>
            <div className="dialog-body">
              <div className="prompt-text">{selected.prompt}</div>
              {[
                'edit-velocity',
                'edit-freeze_poster',
                'edit-triptych',
                'edit-after_dark',
              ].includes(selected.id) && (
                <p className="media-attribution">
                  Edited from{' '}
                  <a
                    href="https://www.youtube.com/watch?v=R6MlUcmOul8"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Tears of Steel
                  </a>
                  {' · (CC) Blender Foundation | '}
                  <a
                    href="https://mango.blender.org/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    mango.blender.org
                  </a>
                  {' · '}
                  <a
                    href="https://creativecommons.org/licenses/by/3.0/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    CC BY 3.0
                  </a>
                </p>
              )}
              <div className="dialog-actions">
                <Button
                  className="copy-primary"
                  onClick={() =>
                    copyText(selected.prompt, selected.id, 'Prompt copied.')
                  }
                >
                  {copied === selected.id ? (
                    <Check size={15} />
                  ) : (
                    <Copy size={15} />
                  )}
                  {copied === selected.id ? 'Copied!' : 'Copy prompt'}
                </Button>
              </div>
            </div>
          </DialogContent>
        )}
      </Dialog>
      <Dialog
        open={!!manualCopy}
        onOpenChange={(isOpen) => {
          if (!isOpen) setManualCopy('');
        }}
      >
        <DialogContent className="manual-copy-dialog">
          <DialogTitle>Copy your prompt</DialogTitle>
          <DialogDescription>
            Your browser couldn’t copy automatically. Copy the selected text
            below.
          </DialogDescription>
          <textarea
            ref={manualText}
            value={manualCopy}
            readOnly
            aria-label="Prompt to copy"
            rows={8}
          />
          <Button onClick={() => setManualCopy('')}>Done</Button>
        </DialogContent>
      </Dialog>
      <div
        className={`toast-message ${message ? 'visible' : ''}`}
        role="status"
        aria-live="polite"
      >
        {message && (
          <>
            <Check size={15} />
            {message}
          </>
        )}
      </div>
    </>
  );
}
