import data from '@/data/examples.json';

export type Example = (typeof data)[number];
export const examples: Example[] = data;
export const categories = [
  'All examples',
  'Motion design',
  'Explainers',
  'YouTube edits',
  'Podcast edits',
  'Social edits',
  'Short films',
] as const;
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
