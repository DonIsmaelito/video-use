import { Box, Orbit, Scissors, Workflow } from 'lucide-react';
import type { Technique } from '@/lib/gallery';

export function TechniqueIcon({
  technique,
  size = 14,
}: {
  technique: Technique;
  size?: number;
}) {
  const Icon =
    technique === '3d'
      ? Box
      : technique === 'video-editing'
        ? Scissors
        : technique === 'diagrams'
          ? Workflow
          : Orbit;
  return <Icon size={size} strokeWidth={1.65} aria-hidden="true" />;
}
