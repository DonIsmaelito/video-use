'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- The supplied product film is preserved as published. The MCP film is silent with on-screen copy; no unmeasured caption track is fabricated. */

import { useEffect, useState } from 'react';
import { ArrowUpRight, Maximize2, Play } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { PreviewMedia } from '@/components/preview-media';

type FilmMedia = {
  src: string;
  video: string;
  poster: string;
  duration: number;
  loop?: boolean;
};

/** Promotional films keep their own player without changing the prompt library. */
export function FeaturedFilm({
  media,
  title,
  subtitle,
  suspended = false,
  standalone = false,
  interactive = true,
}: {
  media: FilmMedia;
  title: string;
  subtitle?: string;
  suspended?: boolean;
  standalone?: boolean;
  interactive?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open) return;
    window.dispatchEvent(new CustomEvent('videouse:overlay', { detail: true }));
    return () => {
      window.dispatchEvent(
        new CustomEvent('videouse:overlay', { detail: false }),
      );
    };
  }, [open]);

  function watch() {
    setFailed(false);
    setOpen(true);
  }

  if (!interactive) {
    return (
      <article className="featured-card product-launch-feature">
        <div className="featured-frame">
          <PreviewMedia
            src={media.src}
            poster={media.poster}
            suspended={suspended}
          />
        </div>
        <div className="featured-caption">
          <h3>{title}</h3>
          {subtitle && <span>{subtitle}</span>}
        </div>
      </article>
    );
  }

  return (
    <>
      <div
        className={
          standalone ? undefined : 'featured-card product-launch-feature'
        }
      >
        <button
          type="button"
          className={standalone ? 'launch-film-preview' : 'featured-frame'}
          onClick={watch}
          aria-label={`Watch ${title}`}
        >
          <PreviewMedia
            src={media.src}
            poster={media.poster}
            suspended={suspended || open}
          />
          {standalone ? (
            <span>
              <Play size={14} fill="currentColor" /> Watch the film
            </span>
          ) : (
            <span className="featured-watch">
              <Maximize2 size={18} />
            </span>
          )}
        </button>
        {!standalone && (
          <div className="featured-caption">
            <button type="button" onClick={watch}>
              {title}
            </button>
            {subtitle && <span>{subtitle}</span>}
          </div>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="launch-film-dialog">
          <DialogTitle className="sr-only">{title}</DialogTitle>
          <DialogDescription className="sr-only">
            Watch the full {title.toLowerCase()} film with playback controls.
          </DialogDescription>
          {failed ? (
            <a
              className="film-fallback"
              href={media.video}
              target="_blank"
              rel="noreferrer"
            >
              Open the film directly <ArrowUpRight size={16} />
            </a>
          ) : (
            <video
              src={media.video}
              poster={media.poster}
              controls
              playsInline
              autoPlay
              loop={media.loop}
              onError={() => setFailed(true)}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
