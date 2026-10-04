import { ArrowUpRight } from 'lucide-react';
import Link from 'next/link';
import launch from '@/data/mcp-launch.json';
import { PreviewMedia } from '@/components/preview-media';

export function McpArtwork() {
  return (
    <div className="mcp-artwork" aria-hidden="true">
      <span className="artwork-label">VIDEO USE / MCP</span>
      <span className="artwork-prompt">
        “make it
        <br />
        <em>move.”</em>
      </span>
      <span className="artwork-route">
        <span>Your chat</span>
        <span>↗</span>
        <span>Your video</span>
      </span>
      <span className="artwork-orbit" />
    </div>
  );
}

export function McpFeature({ suspended = false }: { suspended?: boolean }) {
  return (
    <article className="featured-card mcp-feature">
      <Link
        href="/mcp"
        className="featured-frame mcp-feature-frame"
        aria-label="Discover Video Use MCP and connect your chat"
      >
        {launch.src && launch.poster ? (
          <PreviewMedia
            src={launch.src}
            poster={launch.poster}
            suspended={suspended}
          />
        ) : (
          <McpArtwork />
        )}
      </Link>
      <div className="featured-caption">
        <Link href="/mcp">Video Use MCP</Link>
        <span>
          Connect your chat <ArrowUpRight size={14} />
        </span>
      </div>
    </article>
  );
}
