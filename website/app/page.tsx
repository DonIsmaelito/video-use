import { ArrowUpRight } from 'lucide-react';
import { Hero } from '@/components/hero';
import { Gallery } from '@/components/gallery';
import { repository } from '@/lib/gallery';

export default function Home() {
  return (
    <main>
      <a className="skip-link" href="#examples">
        Skip to video examples
      </a>
      <Hero />
      <Gallery />
      <footer>
        <a href={repository} target="_blank" rel="noreferrer">
          video-use <ArrowUpRight size={16} />
        </a>
        <a href={`${repository}#setup-prompt`} target="_blank" rel="noreferrer">
          Get started <ArrowUpRight size={16} />
        </a>
        <a href="#">Back to top ↑</a>
      </footer>
    </main>
  );
}
