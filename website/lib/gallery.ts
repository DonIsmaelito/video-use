import data from '@/data/examples.json';

export type Example = (typeof data)[number];
export const examples: Example[] = data;
const categoryOrder = [
  'Video Edits',
  'Video Creation',
  'Motion Design',
  'Explainers',
];
export const categories = ['All examples', ...categoryOrder];
export const repository = 'https://github.com/browser-use/video-use';

export function filterExamples(category: string): Example[] {
  return examples.filter(
    (example) => category === 'All examples' || example.category === category,
  );
}

export function formatDuration(seconds: number): string {
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')}`;
}
