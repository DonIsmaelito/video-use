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

export function filterExamples(category: string, sort: string): Example[] {
  const filtered = examples.filter(
    (example) => category === 'All examples' || example.category === category,
  );
  if (sort === 'shortest')
    return filtered.sort((a, b) => a.duration - b.duration);
  if (sort === 'az')
    return filtered.sort((a, b) => a.title.localeCompare(b.title));
  return filtered;
}

export function formatDuration(seconds: number): string {
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')}`;
}

export function referencePrompt(example: Example, origin: string): string {
  return `Use this video as a reference for pacing, composition, and visual treatment:\n${new URL(example.video, origin).href}\n\n${example.prompt}\n\nKeep the style and editing approach, then adapt the subject and footage to my brief.`;
}
