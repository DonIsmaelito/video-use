'use client';

/* oxlint-disable jsx-a11y/media-has-caption -- The launch film contains visual on-screen copy. Add measured caption tracks only if a narrated version is published. */

import { useState } from 'react';
import { Play } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { McpArtwork } from '@/components/mcp-feature';
import { PreviewMedia } from '@/components/preview-media';
import launch from '@/data/mcp-launch.json';

export function McpLaunch() {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  if (!launch.src || !launch.poster || !launch.video) return <McpArtwork />;
  return (
    <>
      <button
        type="button"
        className="launch-film-preview"
        onClick={() => setOpen(true)}
        aria-label="Play the Video Use MCP launch film"
      >
        <PreviewMedia
          src={launch.src}
          poster={launch.poster}
          suspended={open}
        />
        <span>
          <Play size={14} fill="currentColor" /> Watch the film
        </span>
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="launch-film-dialog">
          <DialogTitle className="sr-only">
            Video Use MCP launch film
          </DialogTitle>
          <DialogDescription className="sr-only">
            See how Video Use turns your chat into a video studio.
          </DialogDescription>
          {failed ? (
            <a href={launch.video} target="_blank" rel="noreferrer">
              Open the launch film directly
            </a>
          ) : (
            <video
              src={launch.video}
              poster={launch.poster}
              controls
              playsInline
              autoPlay
              onError={() => setFailed(true)}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
