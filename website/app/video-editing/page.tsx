import type { Metadata } from 'next';
import { CollectionPage } from '@/components/collection-page';

export const metadata: Metadata = {
  title: 'Video Editing — Video Use',
  description:
    'Explore real footage edits, cinematic stories, sports highlights, and social clips. Copy a prompt and make it yours with Video Use.',
  alternates: { canonical: '/video-editing' },
};

export default function VideoEditingPage() {
  return <CollectionPage sectorId="video-editing" />;
}
