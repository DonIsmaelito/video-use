import { ArrowUpRight } from 'lucide-react';
import Link from 'next/link';
import launch from '@/data/mcp-launch.json';
import { AgentMarks } from '@/components/connect-mcp';
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

export function McpFeature() {
  return (
    <article className="video-card mcp-feature">
      <Link
        href="/mcp"
        className="video-frame mcp-feature-frame"
        aria-label="Discover Video Use MCP and connect your chat"
      >
        {launch.src && launch.poster ? (
          <PreviewMedia src={launch.src} poster={launch.poster} />
        ) : (
          <McpArtwork />
        )}
      </Link>
      <div className="card-heading">
        <Link href="/mcp">Your chat is a video studio</Link>
        <ArrowUpRight size={14} />
      </div>
      <div className="card-bottom">
        <span className="feature-tag">Video Use MCP</span>
        <Link
          className="card-connect"
          href="/mcp"
          aria-label="Connect Video Use to ChatGPT, Claude, or Cursor"
        >
          <AgentMarks compact />
          <span>
            Connect <ArrowUpRight size={12} />
          </span>
        </Link>
      </div>
    </article>
  );
}
