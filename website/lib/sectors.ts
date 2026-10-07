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
    action: 'View More',
  },
  {
    id: 'video-creation',
    title: 'Video Creation',
    shortTitle: 'Creation',
    href: '/video-creation',
    description: 'An idea, a prompt, a whole new world in motion.',
    context:
      'Explore original motion design, brand films, and visual explainers. Find a prompt, bring an idea, and make it your own.',
    action: 'View More',
  },
  {
    id: '3d-visuals',
    title: '3D Animations & Visuals',
    shortTitle: '3D Visuals',
    href: '/3d-visuals',
    description: 'Give your ideas a little more dimension.',
    context:
      'Explore visual lessons in math, physics, and AI, original animated scenes, and dimensional product films. Find a visual you love and make it move your way.',
    action: 'View More',
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
    'useful-112-marty-supreme',
    'useful-113-hamilton',
    'useful-114-anime-impact',
    'useful-115-sabrina',
    'useful-116-yuto',
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
    'useful-107-clear-space',
    'useful-108-off-the-grid',
    'useful-96-change-perspective',
    'useful-94-world-in-page',
    'useful-93-inside-lens',
    'useful-92-type-flight',
    'useful-95-format-shift',
    'useful-87-squish-drop',
    'useful-88-rewind',
    'useful-86-ghosted',
    'useful-91-night-court',
    'useful-90-touch-grass',
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
    'useful-109-mend-studio',
    'useful-110-orbit-scent',
    'useful-111-side-quest',
    'useful-103-mecha-assembly',
    'useful-97-determinant',
    'useful-104-spirit-train',
    'useful-100-attention',
    'useful-106-water-dragon',
    'useful-98-refraction',
    'useful-102-rooftop-courier',
    'useful-101-gradient-descent',
    'useful-105-sword-dojo',
    'useful-99-angular-momentum',
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
