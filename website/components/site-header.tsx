import { ArrowUpRight } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { repository } from '@/lib/gallery';

export function SiteHeader({ mcp = false }: { mcp?: boolean }) {
  return (
    <header className="site-header">
      <Link href="/" aria-label="Video Use home" className="brand">
        <Image src="/brand/browser-use.svg" alt="" width={40} height={40} />
        <span>video-use</span>
      </Link>
      <nav aria-label="Main navigation">
        <Link href={mcp ? '/#examples' : '#examples'}>Library</Link>
        <Link href="/mcp" aria-current={mcp ? 'page' : undefined}>
          MCP <span className="nav-new">Pilot</span>
        </Link>
      </nav>
      <a
        className="header-repo"
        href={repository}
        target="_blank"
        rel="noreferrer"
      >
        <Image src="/brand/github.svg" alt="" width={16} height={16} />
        <span>Star on GitHub</span>
        <ArrowUpRight size={13} />
      </a>
    </header>
  );
}
