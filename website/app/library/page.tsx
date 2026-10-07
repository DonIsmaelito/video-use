import type { Metadata } from 'next';
import { CollectionPage } from '@/components/collection-page';

export const metadata: Metadata = {
  title: 'Video Library — Video Use',
  description:
    'Search every Video Use example: real video edits, motion design, 3D animation, and explainers with copyable prompts.',
  alternates: { canonical: '/library' },
};

export default function LibraryPage() {
  return <CollectionPage />;
}
