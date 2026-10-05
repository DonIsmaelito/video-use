'use client';

import { useSyncExternalStore } from 'react';
import Link from 'next/link';
import { X } from 'lucide-react';
import styles from './mcp-announcement.module.css';

const dismissalKey = 'video-use-mcp-announcement-v1';
const listeners = new Set<() => void>();
let dismissedInMemory = false;

function readDismissal() {
  if (dismissedInMemory) return true;
  try {
    return sessionStorage.getItem(dismissalKey) === 'dismissed';
  } catch {
    return false;
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener('storage', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', listener);
  };
}

export function McpAnnouncement() {
  const dismissed = useSyncExternalStore(subscribe, readDismissal, () => false);

  function dismiss() {
    dismissedInMemory = true;
    try {
      sessionStorage.setItem(dismissalKey, 'dismissed');
    } catch {
      // Keep the in-memory choice for this visit.
    }
    listeners.forEach((listener) => listener());
    document
      .querySelector<HTMLElement>('.site-header .brand')
      ?.focus({ preventScroll: true });
  }

  if (dismissed) return null;

  return (
    <aside className={styles.banner} aria-label="Video Use MCP announcement">
      <div className={styles.inner}>
        <Link className={styles.message} href="/mcp#setup">
          Try Video Use MCP
        </Link>
        <button
          className={styles.close}
          type="button"
          aria-label="Dismiss MCP announcement"
          onClick={dismiss}
        >
          <X size={16} />
        </button>
      </div>
    </aside>
  );
}
