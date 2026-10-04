import Image from 'next/image';
import Link from 'next/link';
import { repository } from '@/lib/gallery';
import { getRepositoryStars } from '@/lib/github';
import { ConnectMcp } from '@/components/connect-mcp';

export async function SiteHeader() {
  const stars = await getRepositoryStars();
  const starCount =
    stars === null
      ? 'GitHub'
      : new Intl.NumberFormat('en-US', {
          notation: 'compact',
          maximumFractionDigits: 1,
        }).format(stars);
  const repositoryLabel =
    stars === null
      ? 'Video Use on GitHub'
      : `Video Use on GitHub (${stars.toLocaleString('en-US')} stars)`;

  return (
    <header className="site-header">
      <Link href="/" aria-label="Video Use home" className="brand">
        <Image src="/brand/browser-use.svg" alt="" width={40} height={40} />
        <span>
          Video Use<span className="brand-dot">.</span>
        </span>
      </Link>
      <div className="header-actions">
        <a
          className="header-repo"
          href={repository}
          target="_blank"
          rel="noreferrer"
          aria-label={repositoryLabel}
          title={repositoryLabel}
        >
          <Image src="/brand/github.svg" alt="" width={18} height={18} />
          <span>{starCount}</span>
        </a>
        <ConnectMcp className="header-connect" label="Connect MCP" />
      </div>
    </header>
  );
}
