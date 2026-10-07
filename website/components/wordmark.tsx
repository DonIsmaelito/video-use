import Link from 'next/link';

export function Wordmark() {
  return (
    <footer className="site-footer" aria-label="Video Use">
      <div className="footer-links">
        <span>Made with Video Use.</span>
        <div>
          <Link href="/library">Library</Link>
          <Link href="/mcp">MCP</Link>
          <Link
            href="/edit-canvas/credits.txt"
            aria-label="Footage credits"
            prefetch={false}
            target="_blank"
            rel="noreferrer"
          >
            Credits
          </Link>
          <a
            href="https://github.com/browser-use/video-use"
            target="_blank"
            rel="noreferrer"
          >
            GitHub&nbsp;↗
          </a>
        </div>
      </div>
    </footer>
  );
}
