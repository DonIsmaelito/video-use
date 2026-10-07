import { examples, type GalleryExample } from '@/lib/gallery';

export const sectors = [
  {
    id: 'video-editing',
    title: 'Video Editing',
    shortTitle: 'Editing',
    href: '/video-editing',
    description: 'Turn your footage into something worth watching.',
    context:
      'Explore real footage edits, cinematic stories, sports highlights, and clips made to share. Find a direction, copy the prompt, and bring your own footage.',
    action: 'View all video edits',
  },
  {
    id: 'video-creation',
    title: 'Video Creation',
    shortTitle: 'Creation',
    href: '/video-creation',
    description: 'An idea, a prompt, a whole new world in motion.',
    context:
      'Explore original motion design, 3D animation, product films, and visual explainers. Find a prompt, bring an idea, and make it your own.',
    action: 'View all video creations',
  },
] as const;

export type Sector = (typeof sectors)[number];
export type SectorId = Sector['id'];

// Use the production technique, not the legacy category label: the five
// older "Video Creation" entries are edits of existing travel/food/film footage.
export function sectorForExample(
  example: Pick<GalleryExample, 'technique'>,
): SectorId {
  return example.technique === 'video-editing'
    ? 'video-editing'
    : 'video-creation';
}

export function getSectorExamples(
  id: SectorId,
  source = examples,
): GalleryExample[] {
  return source.filter((example) => sectorForExample(example) === id);
}

const previewIds: Record<SectorId, string[]> = {
  'video-editing': [
    'screen-demo-fuji-browser-tour',
    'useful-74-drew-editorial',
    'useful-83-spiderman-panels',
    'useful-75-leah-glambot',
    'useful-82-curry-locked-in',
    'useful-64-billie-finneas',
    'useful-85-rumi-double-life',
    'useful-79-dubai-chocolate',
    'useful-81-speed-fast-travel',
    'useful-73-pacu-poster',
    'useful-71-whiskey',
    'useful-65-andrew-amelia',
    'useful-84-wednesday-deadpan',
    'cloud-edit-travel',
    'useful-66-tank-workout',
    'useful-61-druski-entrance',
  ],
  'video-creation': [
    '11-rotary-telephone',
    'useful-07-workshop-invite',
    'useful-08-refill-product',
    'useful-14-campaign-announcement',
    'local-motion-20260916-10-ribbon-knot',
    'useful-01-launch-approvals',
    'useful-03-lead-routing',
    'useful-30-match-result',
    '02-jelly-chair',
    'useful-19-fulfilment-flow',
    'useful-04-monthly-report',
    'useful-27-hiring-post',
    'local-motion-20260916-02-chromatic-weave',
    'useful-02-modular-desk',
    'useful-35-water-cycle',
    '01-paper-koi',
  ],
};

export function getSectorPreview(
  id: SectorId,
  source = examples,
): GalleryExample[] {
  const available = getSectorExamples(id, source);
  const ids = previewIds[id];
  return [
    ...ids.flatMap((key) => available.filter((example) => example.id === key)),
    ...available.filter((example) => !ids.includes(example.id)),
  ].slice(0, 16);
}
