'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  Copy,
  Link2,
  Play,
  X,
} from 'lucide-react';
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
  referencePrompt,
  repository,
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

  const stop = () => {
    wantsPlayback.current = false;
    video.current?.pause();
    setPlaying(false);
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setNearby(true);
        else {
          wantsPlayback.current = false;
          video.current?.pause();
          setPlaying(false);
        }
      },
      { rootMargin: '200px' },
    );
    if (frame.current) observer.observe(frame.current);
    const onVisibility = () => {
      if (document.hidden) stop();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  useEffect(() => {
    if (suspended) stop();
  }, [suspended]);

  useEffect(() => {
    // A fast hover or keyboard focus can arrive before lazy media mounts.
    if (nearby && wantsPlayback.current && video.current) {
      const player = video.current;
      player
        .play()
        .then(() => {
          if (!wantsPlayback.current) player.pause();
        })
        .catch(() => {});
    }
  }, [nearby]);

  const play = () => {
    if (
      suspended ||
      failed ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
      return;
    wantsPlayback.current = true;
    setNearby(true);
    if (!video.current) return;
    video.current
      .play()
      .then(() => {
        if (!wantsPlayback.current) video.current?.pause();
      })
      .catch(() => {});
  };

  return (
    <article className="video-card">
      <button
        ref={frame}
        type="button"
        className={`video-frame ${playing ? 'is-playing' : ''} ${example.orientation}`}
        onPointerEnter={(event) => {
          if (event.pointerType === 'mouse') play();
        }}
        onPointerLeave={stop}
        onFocus={play}
        onBlur={stop}
        onClick={() => {
          stop();
          open();
        }}
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
        <span className="play-indicator">
          <Play size={15} fill="currentColor" />
        </span>
        <span className="video-duration">
          {formatDuration(example.duration)}
        </span>
      </button>
      <div className="card-meta">
        <span className="category-tag">{example.category}</span>
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
      <h3>
        <button type="button" onClick={open}>
          <span className="card-title">{example.title}</span>
          <ArrowUpRight size={14} />
        </button>
      </h3>
    </article>
  );
}

export function Gallery() {
  const [category, setCategory] = useState('All examples');
  const [sort, setSort] = useState('curated');
  const [selected, setSelected] = useState<Example | null>(null);
  const [copied, setCopied] = useState('');
  const [message, setMessage] = useState('');
  const [manualCopy, setManualCopy] = useState('');
  const [videoError, setVideoError] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualText = useRef<HTMLTextAreaElement>(null);
  const visible = filterExamples(category, sort);

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
        <div className="gallery-toolbar">
          <Button
            variant="ghost"
            className="clear-filter"
            disabled={category === 'All examples'}
            onClick={() => setCategory('All examples')}
          >
            <X size={16} /> Clear filters
          </Button>
          <label className="sort-control">
            <span>Sort by:</span>
            <select
              aria-label="Sort examples"
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="curated">Handpicked</option>
              <option value="shortest">Shortest first</option>
              <option value="az">Title A–Z</option>
            </select>
            <ChevronDown size={16} />
          </label>
        </div>
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
        <div className="video-grid" key={category + sort}>
          {visible.map((example) => (
            <VideoCard
              key={example.id}
              example={example}
              open={() => open(example)}
              copy={() =>
                copyText(
                  example.prompt,
                  example.id,
                  'Prompt copied. Make it yours.',
                )
              }
              copied={copied === example.id}
              suspended={selected !== null || !!manualCopy}
            />
          ))}
        </div>
      </section>
      <Dialog
        open={selected !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setSelected(null);
        }}
      >
        {selected && (
          <DialogContent className="example-dialog">
            <div className={`dialog-video ${selected.orientation}`}>
              {!videoError ? (
                <video
                  key={selected.id}
                  src={selected.video}
                  poster={selected.poster}
                  controls
                  playsInline
                  autoPlay
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
              <div className="dialog-heading">
                <span className="category-tag">{selected.category}</span>
                <span>{formatDuration(selected.duration)}</span>
              </div>
              <DialogTitle className="dialog-title">
                {selected.title}
              </DialogTitle>
              <DialogDescription className="dialog-description">
                {selected.description}
              </DialogDescription>
              <div className="prompt-heading">
                <span>{selected.promptKind}</span>
              </div>
              <div className="prompt-text">{selected.prompt}</div>
              {selected.orientation === 'portrait' && (
                <p className="source-note">
                  Bring your own recording or footage to make a version of this
                  edit.
                </p>
              )}
              <div className="dialog-actions">
                <Button
                  className="copy-primary"
                  onClick={() =>
                    copyText(
                      selected.prompt,
                      selected.id,
                      'Prompt copied. Make it yours.',
                    )
                  }
                >
                  {copied === selected.id ? (
                    <Check size={15} />
                  ) : (
                    <Copy size={15} />
                  )}
                  {copied === selected.id ? 'Copied!' : 'Copy prompt'}
                </Button>
                <Button
                  variant="outline"
                  className="reference-button"
                  onClick={() =>
                    copyText(
                      referencePrompt(selected, window.location.origin),
                      `${selected.id}-reference`,
                      'Prompt and video reference copied.',
                    )
                  }
                >
                  <Link2 size={15} />
                  {copied === `${selected.id}-reference`
                    ? 'Copied!'
                    : 'Copy reference'}
                </Button>
              </div>
              <p className="getting-started">
                <a
                  href={`${repository}#setup-prompt`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Get started <ArrowUpRight size={11} />
                </a>
              </p>
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
