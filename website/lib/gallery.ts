import data from '@/data/examples.json';

export const techniqueOptions = [
  { value: 'motion-design', label: 'Motion design' },
  { value: '3d', label: '3D animation' },
  { value: 'diagrams', label: 'Diagrams & explainers' },
  { value: 'video-editing', label: 'Video editing' },
] as const;
export type Technique = (typeof techniqueOptions)[number]['value'];

export type Example = {
  id: string;
  title: string;
  category: string;
  description: string;
  prompt: string;
  video: string;
  poster: string;
  duration: number;
  loop?: boolean;
  muted?: boolean;
  promptKind: string;
  orientation: string;
  audiences?: string[];
  audience?: string;
  useCases?: string[];
  useCase?: string;
  technique?: Technique;
  sourceRepo?: string;
  promptSource?: string;
  sourceArchive?: string;
  reviewUrl?: string;
};

export type GalleryExample = Example & {
  audiences: string[];
  useCases: string[];
  technique: Technique;
  hasWorkflowMetadata: boolean;
};

export type Filters = {
  category: string;
  query: string;
  audiences: string[];
  useCases: string[];
  technique: Technique | '';
};

export const defaultFilters: Filters = {
  category: 'All examples',
  query: '',
  audiences: [],
  useCases: [],
  technique: '',
};

export const categories = [
  'All examples',
  'Video Edits',
  'Video Creation',
  'Motion Design',
  'Explainers',
];
export const repository = 'https://github.com/browser-use/video-use';
export const mcpUrl =
  'https://iaredur--video-use-browser-pilot-web.modal.run/mcp';

// These older studies predate explicit tags. Keep their known classifications
// attached to IDs so changing the display title never changes the filters.
const legacy3dIds = new Set([
  '11-rotary-telephone',
  '12-glass-staircase',
  '13-beach-umbrella',
  '15-color-zipper',
  '02-jelly-chair',
  '03-chrome-beetle',
  '06-satin-bow',
  '07-blood-orange',
  '08-toy-planet',
  '09-jellyfish',
  '02-orbit',
  '04-fold',
  'optical-assembly',
]);
const legacyBrandIds = new Set([
  'cloud-motion-01-make-room',
  'cloud-motion-02-night-shift',
  'cloud-motion-06-ink-relay',
]);
const legacyEditingIds = new Set([
  'edit-velocity',
  'edit-freeze_poster',
  'edit-triptych',
  'edit-after_dark',
  'cloud-edit-podcast',
]);

// Older cards predate audience/use-case metadata. Label studies as studies;
// a visually interesting loop alone is not evidence of a product workflow.
export function enrichExample(example: Example): GalleryExample {
  const text = `${example.id} ${example.description}`.toLowerCase();
  let technique: Technique = 'motion-design';
  let audiences = ['Designers'];
  let useCases = ['Motion studies'];

  if (example.category === 'Video Edits') {
    technique = 'video-editing';
    audiences = ['Content creators'];
    useCases = ['Social content'];
    if (/unboxing|product/.test(text)) {
      audiences.push('Marketers');
      useCases = ['Product demos'];
    }
    if (/podcast|interview|caption/.test(text))
      useCases = ['Podcast clips', 'Social content'];
    if (/recipe|tutorial/.test(text)) {
      audiences.push('Educators');
      useCases = ['Tutorials'];
    }
    if (
      legacyEditingIds.has(example.id) ||
      /cinematic|film|freeze|split screen|speed ramp/.test(text)
    )
      useCases = ['Editing techniques'];
  } else if (example.category === 'Video Creation') {
    technique = 'video-editing';
    audiences = ['Content creators'];
    useCases = ['Stories & recaps'];
  } else if (example.category === 'Explainers') {
    technique = 'diagrams';
    audiences = ['Educators', 'Product teams'];
    useCases = ['Explainers', 'Learning materials'];
  } else {
    if (
      legacy3dIds.has(example.id) ||
      /local-motion-20260916-(09|10|11|12|13|14|15|16)-/.test(example.id)
    ) {
      technique = '3d';
    }
    if (legacyBrandIds.has(example.id)) {
      audiences.push('Marketers');
      useCases = ['Brand identity', 'Motion studies'];
    }
    if (example.id === 'cloud-motion-07-one-good-day') {
      audiences = ['Designers', 'Product teams'];
      useCases = ['Product demos'];
    }
  }

  return {
    ...example,
    hasWorkflowMetadata: !!(
      (example.audiences?.length || example.audience) &&
      (example.useCases?.length || example.useCase)
    ),
    technique: example.technique ?? technique,
    audiences: example.audiences?.length
      ? example.audiences
      : example.audience
        ? [example.audience]
        : audiences,
    useCases: example.useCases?.length
      ? example.useCases
      : example.useCase
        ? [example.useCase]
        : useCases,
  };
}

export const examples: GalleryExample[] = (data as Example[]).map(
  enrichExample,
);

export function facetOptions(field: 'audiences' | 'useCases'): string[] {
  return [...new Set(examples.flatMap((example) => example[field]))].sort(
    (a, b) => a.localeCompare(b),
  );
}

export function filterExamples(
  filters: string | Partial<Filters>,
  source = examples,
): GalleryExample[] {
  const active = {
    ...defaultFilters,
    ...(typeof filters === 'string' ? { category: filters } : filters),
  };
  const terms = active.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return source.filter((example) => {
    if (
      active.category !== 'All examples' &&
      example.category !== active.category
    )
      return false;
    if (active.technique && example.technique !== active.technique)
      return false;
    if (
      active.audiences.length &&
      !active.audiences.some((audience) => example.audiences.includes(audience))
    )
      return false;
    if (
      active.useCases.length &&
      !active.useCases.some((useCase) => example.useCases.includes(useCase))
    )
      return false;
    const searchText = [
      example.title,
      example.description,
      example.prompt,
      example.category,
      techniqueLabel(example.technique),
      ...example.audiences,
      ...example.useCases,
    ]
      .join(' ')
      .toLowerCase();
    return terms.every((term) => searchText.includes(term));
  });
}

export function techniqueLabel(technique: Technique): string {
  return (
    techniqueOptions.find((item) => item.value === technique)?.label ??
    'Motion design'
  );
}

export function readGalleryQuery(params: URLSearchParams): {
  filters: Filters;
  example: GalleryExample | null;
} {
  const technique = params.get('technique');
  const category = params.get('category');
  const audiences = facetOptions('audiences');
  const useCases = facetOptions('useCases');
  return {
    filters: {
      category:
        category && categories.includes(category) ? category : 'All examples',
      technique: techniqueOptions.some((item) => item.value === technique)
        ? (technique as Technique)
        : '',
      query: (params.get('q') ?? '').slice(0, 200),
      audiences: [...new Set(params.getAll('audience'))].filter((item) =>
        audiences.includes(item),
      ),
      useCases: [...new Set(params.getAll('useCase'))].filter((item) =>
        useCases.includes(item),
      ),
    },
    example:
      examples.find((example) => example.id === params.get('example')) ?? null,
  };
}

export function writeGalleryQuery(
  params: URLSearchParams,
  filters: Filters,
  selectedId: string | null,
): URLSearchParams {
  const next = new URLSearchParams(params);
  for (const key of [
    'category',
    'technique',
    'q',
    'audience',
    'useCase',
    'example',
  ])
    next.delete(key);
  if (filters.category !== 'All examples')
    next.set('category', filters.category);
  if (filters.technique) next.set('technique', filters.technique);
  if (filters.query.trim()) next.set('q', filters.query.trim());
  for (const item of filters.audiences) next.append('audience', item);
  for (const item of filters.useCases) next.append('useCase', item);
  if (selectedId) next.set('example', selectedId);
  return next;
}

export function exampleLink(origin: string, exampleId: string): string {
  const url = new URL('/', origin);
  url.searchParams.set('example', exampleId);
  return url.toString();
}

export function buildChatPrompt(example: Example): string {
  return `${example.prompt}\n\nVideo Use example: ${exampleLink('https://video-use.insforge.site', example.id)}\n\nUse this workflow as my creative direction and adapt it to the subject, brand, format and length already requested in this chat. Skip searching for other reference videos. Preserve my involvement mode; in hands-on mode show a short snippet for approval before the full video.`;
}

export function safeSourceUrl(value?: string): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

export function formatDuration(seconds: number): string {
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')}`;
}
