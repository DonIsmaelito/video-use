import { ArrowUpRight } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { repository } from '@/lib/gallery';
import { ConnectMcp } from '@/components/connect-mcp';

export function SiteHeader() {
  return (
    <header className="site-header">
      <Link href="/" aria-label="Video Use home" className="brand">
        <Image src="/brand/browser-use.svg" alt="" width={40} height={40} />
        <span>
          video-use<span className="brand-dot">.</span>
        </span>
      </Link>
      <div className="header-actions">
        <a
          className="header-repo"
          href={repository}
          target="_blank"
          rel="noreferrer"
        >
          <Image src="/brand/github.svg" alt="" width={16} height={16} />
          <span>GitHub</span>
          <ArrowUpRight size={13} />
        </a>
        <ConnectMcp className="header-connect" label="Connect MCP" />
      </div>
    </header>
  );
}
