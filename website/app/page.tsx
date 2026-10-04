import { Hero } from '@/components/hero';
import { Gallery } from '@/components/gallery';
import { Wordmark } from '@/components/wordmark';
import { McpBanner } from '@/components/connect-mcp';

export default function Home() {
  return (
    <main>
      <a className="skip-link" href="#examples">
        Skip to video examples
      </a>
      <Hero />
      <Gallery />
      <McpBanner />
      <Wordmark />
    </main>
  );
}
