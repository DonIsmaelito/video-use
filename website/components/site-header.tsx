import Image from 'next/image';
import Link from 'next/link';
import { repository } from '@/lib/gallery';
import { getRepositoryStars } from '@/lib/github';
import { ConnectMcp } from '@/components/connect-mcp';
import type { SectorId } from '@/lib/sectors';
import styles from './site-header.module.css';

export async function SiteHeader({
  active,
}: { active?: SectorId | 'explore' | 'library' | 'mcp' } = {}) {
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
    <header className={`site-header ${styles.header}`}>
      <Link
        href="/"
        aria-label="Video Use by Browser Use home"
        className="brand"
      >
        <Image src="/brand/browser-use.svg" alt="" width={40} height={40} />
        <span className="brand-copy">
          <span className="brand-title">Video Use</span>
          <span className="brand-credit">by Browser Use</span>
        </span>
      </Link>
      <nav className={styles.navigation} aria-label="Main navigation">
        {[
          { id: 'explore', href: '/', label: 'Explore' },
          {
            id: 'video-editing',
            href: '/video-editing',
            label: 'Video Editing',
          },
          {
            id: 'video-creation',
            href: '/video-creation',
            label: 'Video Creation',
          },
          { id: '3d-visuals', href: '/3d-visuals', label: '3D Visuals' },
          { id: 'mcp', href: '/mcp', label: 'MCP' },
        ].map((item) => (
          <Link
            key={item.id}
            href={item.href}
            aria-current={active === item.id ? 'page' : undefined}
          >
            {item.label}
          </Link>
        ))}
      </nav>
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
