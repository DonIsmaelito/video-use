import type { Metadata } from 'next';
import { CollectionPage } from '@/components/collection-page';

export const metadata: Metadata = {
  title: '3D Animations & Visuals — Video Use',
  description:
    'Explore tactile materials, playful objects, product animations, and miniature worlds. Make original 3D visuals with Video Use.',
  alternates: { canonical: '/3d-visuals' },
};

export default function ThreeDVisualsPage() {
  return <CollectionPage sectorId="3d-visuals" />;
}
