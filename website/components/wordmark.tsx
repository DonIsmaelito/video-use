import Link from 'next/link';

export function Wordmark() {
  return (
    <footer className="site-footer" aria-label="Video Use">
      <div className="footer-links">
        <span>Made with Video Use.</span>
        <div>
          <Link href="/library">Library</Link>
          <Link href="/mcp">MCP</Link>
          <a
            href="https://github.com/browser-use/video-use"
            target="_blank"
            rel="noreferrer"
          >
            GitHub ↗
          </a>
        </div>
      </div>
      <p className="footer-wordmark">VIDEO USE</p>
    </footer>
  );
}
