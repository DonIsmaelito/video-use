import type { Metadata } from 'next';
import { CollectionPage } from '@/components/collection-page';

export const metadata: Metadata = {
  title: 'Video Creation — Video Use',
  description:
    'Explore original motion design, 3D animation, product films, and explainers. Start with a prompt and create something new with Video Use.',
  alternates: { canonical: '/video-creation' },
};

export default function VideoCreationPage() {
  return <CollectionPage sectorId="video-creation" />;
}
