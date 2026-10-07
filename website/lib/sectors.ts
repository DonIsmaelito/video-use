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
      'Explore original motion design, brand films, and visual explainers. Find a prompt, bring an idea, and make it your own.',
    action: 'View all video creations',
  },
  {
    id: '3d-visuals',
    title: '3D Animations & Visuals',
    shortTitle: '3D Visuals',
    href: '/3d-visuals',
    description: 'Give your ideas a little more dimension.',
    context:
      'Explore playful objects, tactile materials, product animations, and impossible little worlds. Find a visual you love and make it move your way.',
    action: 'View all 3D visuals',
  },
] as const;

export type Sector = (typeof sectors)[number];
export type SectorId = Sector['id'];

// Use the production technique, not the legacy category label: the five
// older "Video Creation" entries are edits of existing travel/food/film footage.
export function sectorForExample(
  example: Pick<GalleryExample, 'technique'>,
): SectorId {
  if (example.technique === 'video-editing') return 'video-editing';
  if (example.technique === '3d') return '3d-visuals';
  return 'video-creation';
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
    'useful-07-workshop-invite',
    'useful-14-campaign-announcement',
    'useful-01-launch-approvals',
    'useful-03-lead-routing',
    'useful-30-match-result',
    'useful-04-monthly-report',
    'useful-27-hiring-post',
    'local-motion-20260916-02-chromatic-weave',
    'useful-35-water-cycle',
    '01-paper-koi',
    'cloud-motion-01-make-room',
    'cloud-motion-02-night-shift',
    'cloud-motion-06-ink-relay',
    'cloud-motion-07-one-good-day',
  ],
  '3d-visuals': [
    '11-rotary-telephone',
    'useful-08-refill-product',
    'local-motion-20260916-10-ribbon-knot',
    '02-jelly-chair',
    'useful-02-modular-desk',
    'local-motion-20260916-09-porcelain-bloom',
    '03-chrome-beetle',
    'useful-37-product-dimensions',
    'local-motion-20260916-12-glass-tide',
    '08-toy-planet',
    'useful-19-fulfilment-flow',
    '06-satin-bow',
    'local-motion-20260916-16-orbital-rings',
    '07-blood-orange',
    'optical-assembly',
    '04-fold',
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
