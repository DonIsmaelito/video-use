import { Hero } from '@/components/hero';
import { Gallery } from '@/components/gallery';
import { Wordmark } from '@/components/wordmark';

export default function Home() {
  return (
    <main>
      <a className="skip-link" href="#examples">
        Skip to video examples
      </a>
      <Hero />
      <Gallery />
      <Wordmark />
    </main>
  );
}
