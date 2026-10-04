import { McpArtwork } from '@/components/mcp-feature';
import { FeaturedFilm } from '@/components/featured-film';
import launch from '@/data/mcp-launch.json';

export function McpLaunch() {
  if (!launch.src || !launch.poster || !launch.video) return <McpArtwork />;
  return (
    <FeaturedFilm media={launch} title="Video Use MCP launch" standalone />
  );
}
