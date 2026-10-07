import Link from 'next/link';
import { ArrowDown, ArrowLeft } from 'lucide-react';
import { SiteHeader } from '@/components/site-header';
import { Gallery } from '@/components/gallery';
import { Wordmark } from '@/components/wordmark';
import { ConnectMcp } from '@/components/connect-mcp';
import { examples } from '@/lib/gallery';
import { getSectorExamples, sectors, type SectorId } from '@/lib/sectors';
import styles from './collection-page.module.css';

export function CollectionPage({ sectorId }: { sectorId?: SectorId }) {
  const sector = sectors.find((item) => item.id === sectorId);
  const count = sector ? getSectorExamples(sector.id).length : examples.length;
  return (
    <main>
      <a className="skip-link" href="#examples">
        Skip to video examples
      </a>
      <SiteHeader active={sectorId ?? 'library'} />
      <section className={styles.hero} aria-labelledby="collection-title">
        <Link
          href={sector ? `/#${sector.id}-heading` : '/'}
          className={styles.back}
        >
          <ArrowLeft size={15} /> Explore
        </Link>
        <p className={styles.eyebrow}>
          {count} examples. Endless possibilities.
        </p>
        <h1 id="collection-title">{sector?.title ?? 'The Video Library'}</h1>
        <p className={styles.context}>
          {sector?.context ??
            'Every edit, animation, and idea in one place. Explore real examples, find a prompt that speaks to you, and make it your own.'}
        </p>
        <div className={styles.actions}>
          <ConnectMcp label="Connect your chat" className={styles.connect} />
          <a href="#examples" className={styles.browse}>
            Explore examples <ArrowDown size={16} />
          </a>
        </div>
      </section>
      <nav className={styles.collections} aria-label="Video collections">
        <Link href="/library" aria-current={!sector ? 'page' : undefined}>
          All videos <span>{examples.length}</span>
        </Link>
        {sectors.map((item) => (
          <Link
            key={item.id}
            href={item.href}
            aria-current={sector?.id === item.id ? 'page' : undefined}
          >
            {item.title}
            <span>{getSectorExamples(item.id).length}</span>
          </Link>
        ))}
      </nav>
      <Gallery key={sectorId ?? 'library'} sector={sectorId} browse />
      <Wordmark />
    </main>
  );
}
