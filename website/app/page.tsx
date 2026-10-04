import { SiteHeader } from '@/components/site-header';
import { Gallery } from '@/components/gallery';
import { Wordmark } from '@/components/wordmark';

export default function Home() {
  return (
    <main>
      <a className="skip-link" href="#examples">
        Skip to video examples
      </a>
      <SiteHeader />
      <h1 className="sr-only">Video Use — find a video, make it yours</h1>
      <Gallery />
      <Wordmark />
    </main>
  );
}
