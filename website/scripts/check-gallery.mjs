import assert from 'node:assert/strict';
import { readFile, stat } from 'node:fs/promises';
import { createRequire } from 'node:module';
import ts from 'typescript';

// Exercise the real pure helpers without starting a browser or editing backend.
const require = createRequire(import.meta.url);
const source = await readFile(
  new URL('../lib/gallery.ts', import.meta.url),
  'utf8',
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
});
const exports = {};
// This compiles our own checked-in pure TypeScript helpers, never user input.
// oxlint-disable-next-line typescript/no-implied-eval
new Function('require', 'exports', outputText)(
  (specifier) =>
    specifier === '@/data/examples.json'
      ? require('../data/examples.json')
      : require(specifier),
  exports,
);
const {
  examples,
  categories,
  filterExamples,
  formatDuration,
  enrichExample,
  defaultFilters,
  techniqueOptions,
  readGalleryQuery,
  writeGalleryQuery,
  exampleLink,
  safeSourceUrl,
  buildChatPrompt,
  facetOptions,
} = exports;

// The new collection routes must form an exhaustive, non-overlapping library.
const sectorSource = await readFile(
  new URL('../lib/sectors.ts', import.meta.url),
  'utf8',
);
const sectorModule = ts.transpileModule(sectorSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
});
const sectorExports = {};
// oxlint-disable-next-line typescript/no-implied-eval
new Function('require', 'exports', sectorModule.outputText)(
  (specifier) => (specifier === '@/lib/gallery' ? exports : require(specifier)),
  sectorExports,
);
const { sectors, getSectorExamples, getSectorPreview, sectorForExample } =
  sectorExports;
const assigned = sectors.flatMap((sector) => getSectorExamples(sector.id));
assert.equal(
  assigned.length,
  examples.length,
  'Every clip must belong to one collection',
);
assert.equal(
  new Set(assigned.map((example) => example.id)).size,
  examples.length,
  'Collections must not overlap',
);
assert.deepEqual(
  new Set(assigned.map((example) => example.id)),
  new Set(examples.map((example) => example.id)),
);
for (const sector of sectors) {
  const collection = getSectorExamples(sector.id);
  const preview = getSectorPreview(sector.id);
  assert.ok(
    collection.length > 16,
    'A preview must lead to a larger real collection',
  );
  assert.equal(preview.length, 16);
  assert.equal(
    new Set(preview.map((example) => example.id)).size,
    preview.length,
  );
  assert.ok(
    preview.every((example) => collection.includes(example)),
    'Homepage teasers must come from their destination collection',
  );
  for (const query of ['product', 'motion', 'interview', 'football']) {
    assert.ok(
      filterExamples({ query }, collection).every(
        (example) => sectorForExample(example) === sector.id,
      ),
      'Search must stay inside the selected collection',
    );
  }
  for (const field of ['audiences', 'useCases']) {
    assert.deepEqual(
      new Set(facetOptions(field, collection)),
      new Set(collection.flatMap((example) => example[field])),
      'Collection filters must not include unrelated options',
    );
  }
}
for (const example of examples.filter(
  (example) => example.category === 'Video Creation',
)) {
  assert.equal(
    sectorForExample(example),
    'video-editing',
    'Legacy footage edits stay with edits regardless of their old category label',
  );
}
assert.deepEqual(
  filterExamples({ technique: '3d' }, getSectorExamples('video-editing')),
  [],
);
assert.deepEqual(
  filterExamples(
    { technique: 'video-editing' },
    getSectorExamples('video-creation'),
  ),
  [],
);
assert.equal(
  new Set(examples.map((example) => example.id)).size,
  examples.length,
  'Gallery IDs must be unique',
);
assert.ok(
  examples.length >= 16,
  'The initial gallery should include sixteen real examples',
);
const featuredWorkflows = require('../data/featured-workflows.json');
assert.equal(featuredWorkflows.length + 2, 8, 'Keep eight featured use cases');
assert.equal(
  new Set(featuredWorkflows.map((item) => item.exampleId)).size,
  featuredWorkflows.length,
  'Each featured workflow needs a distinct reviewed example',
);
for (const workflow of featuredWorkflows) {
  assert.ok(
    examples.some((example) => example.id === workflow.exampleId),
    `${workflow.title}: publish its reviewed example before featuring it`,
  );
  assert.ok(workflow.title.trim() && workflow.description.trim());
  assert.ok(['cover', 'contain'].includes(workflow.fit));
}
assert.deepEqual(filterExamples('All examples'), examples);
assert.equal(new Set(categories).size, categories.length);
assert.deepEqual(
  new Set(categories.slice(1)),
  new Set(examples.map((example) => example.category)),
  'Every example category must appear in the continuous gallery',
);
for (const category of categories.slice(1)) {
  const results = filterExamples(category);
  assert.ok(results.length > 0, `${category} needs a working example`);
  assert.ok(results.every((example) => example.category === category));
}
assert.equal(formatDuration(59.8), '1:00');
assert.equal(formatDuration(8), '0:08');
assert.equal(formatDuration(75.77), '1:16');

// Visible subject names can change without moving a clip to different facets.
for (const example of require('../data/examples.json')) {
  const original = enrichExample(example);
  const renamed = enrichExample({ ...example, title: 'New Product Film' });
  for (const field of ['technique', 'audiences', 'useCases']) {
    assert.deepEqual(
      renamed[field],
      original[field],
      `${example.id}: renaming must preserve ${field}`,
    );
  }
}
assert.equal(
  enrichExample({
    id: '11-rotary-telephone',
    title: 'Red Telephone',
    description: 'A red telephone forms around its cord.',
    category: 'Motion Design',
  }).technique,
  '3d',
  'A renamed 3D study must retain its video type',
);

// The gallery is linked from agent conversations, so stale or invalid links
// must not silently activate unsupported techniques, filters, or examples.
for (const technique of techniqueOptions) {
  const state = readGalleryQuery(
    new URLSearchParams({ technique: technique.value }),
  );
  assert.equal(state.filters.technique, technique.value);
  const matches = filterExamples(state.filters);
  assert.ok(matches.length > 0, `${technique.label} needs real examples`);
  assert.ok(matches.every((item) => item.technique === technique.value));
}
const invalid = readGalleryQuery(
  new URLSearchParams(
    'category=missing&technique=javascript%3Abad&example=missing&audience=Administrator&useCase=none&q=' +
      'x'.repeat(300),
  ),
);
assert.equal(invalid.filters.technique, '');
assert.equal(invalid.filters.category, 'All examples');
assert.deepEqual(invalid.filters.audiences, []);
assert.deepEqual(invalid.filters.useCases, []);
assert.equal(invalid.filters.query.length, 200);
assert.equal(invalid.example, null);
const linked = readGalleryQuery(
  new URLSearchParams({ example: examples[0].id }),
);
assert.equal(linked.example.id, examples[0].id);
const params = writeGalleryQuery(
  new URLSearchParams('utm_source=chat&example=old&audience=Old'),
  { ...defaultFilters, technique: '3d', query: 'glass' },
  examples[0].id,
);
assert.equal(params.get('utm_source'), 'chat');
assert.deepEqual(params.getAll('audience'), []);
assert.equal(readGalleryQuery(params).example.id, examples[0].id);
assert.equal(readGalleryQuery(params).filters.query, 'glass');
assert.equal(
  writeGalleryQuery(params, defaultFilters, null).toString(),
  'utm_source=chat',
);
assert.equal(
  new URL(exampleLink('https://example.com', examples[0].id)).searchParams.get(
    'example',
  ),
  examples[0].id,
);

// Audiences and use cases are OR within one group, AND between groups.
// Explicit metadata must override legacy inference for new practical workflows.
const fixtures = [
  enrichExample({
    ...examples[0],
    id: 'launch',
    category: 'Motion Design',
    title: 'Quiet Product Launch',
    audiences: ['Founders'],
    useCases: ['Product launches'],
    technique: '3d',
  }),
  enrichExample({
    ...examples[0],
    id: 'design',
    category: 'Motion Design',
    title: 'Quiet Design Launch',
    audiences: ['Designers'],
    useCases: ['Product launches'],
    technique: 'motion-design',
  }),
  enrichExample({
    ...examples[0],
    id: 'lesson',
    category: 'Motion Design',
    title: 'Quiet Product Lesson',
    audiences: ['Educators'],
    useCases: ['Tutorials'],
    technique: 'diagrams',
  }),
];
assert.deepEqual(
  filterExamples({ audiences: ['Founders', 'Educators'] }, fixtures).map(
    (item) => item.id,
  ),
  ['launch', 'lesson'],
);
assert.deepEqual(
  filterExamples(
    { audiences: ['Founders', 'Educators'], useCases: ['Product launches'] },
    fixtures,
  ).map((item) => item.id),
  ['launch'],
);
assert.deepEqual(
  filterExamples(
    { query: 'quiet product', technique: 'diagrams' },
    fixtures,
  ).map((item) => item.id),
  ['lesson'],
);
assert.deepEqual(
  filterExamples({ category: 'Explainers', technique: '3d' }, fixtures),
  [],
);
assert.equal(safeSourceUrl('javascript:alert(1)'), null);
assert.equal(safeSourceUrl('file:///tmp/secret'), null);
assert.equal(safeSourceUrl('https://user:password@example.com/source'), null);
assert.equal(
  safeSourceUrl('https://github.com/browser-use/video-use'),
  'https://github.com/browser-use/video-use',
);
const handoff = buildChatPrompt(examples[0]);
assert.ok(handoff.startsWith(examples[0].prompt + '\n\n'));
assert.ok(
  handoff.includes(
    exampleLink('https://video-use.insforge.site', examples[0].id),
  ),
);
assert.ok(
  handoff.includes(
    'adapt it to the subject, brand, format and length already requested',
  ),
);
assert.ok(
  handoff.includes(
    'in hands-on mode show a short snippet for approval before the full video',
  ),
);

const launch = require('../data/mcp-launch.json');
const launchValues = [launch.src, launch.video, launch.poster, launch.duration];
if (launchValues.some((value) => value !== null)) {
  for (const asset of [launch.src, launch.video, launch.poster]) {
    assert.ok(
      safeSourceUrl(asset),
      'MCP launch media must be published HTTPS assets',
    );
  }
  assert.ok(Number.isFinite(launch.duration) && launch.duration > 0);
} else {
  assert.ok(
    launchValues.every((value) => value === null),
    'Unpublished MCP media stays an honest static tile',
  );
}

for (const example of examples) {
  assert.ok(typeof example.category === 'string' && example.category.trim());
  assert.ok(example.prompt.trim().length >= 25);
  assert.ok(['Original prompt', 'Starter prompt'].includes(example.promptKind));
  assert.ok(Number.isFinite(example.duration) && example.duration > 0);
  assert.ok(
    example.loop === undefined || typeof example.loop === 'boolean',
    'Optional full-player loop metadata must be a boolean',
  );
  assert.ok(
    example.muted === undefined || typeof example.muted === 'boolean',
    'Optional full-player muted metadata must be a boolean',
  );
  assert.ok(
    example.audiences.length > 0 &&
      example.audiences.every(
        (item) => typeof item === 'string' && item.trim(),
      ),
  );
  assert.ok(
    example.useCases.length > 0 &&
      example.useCases.every((item) => typeof item === 'string' && item.trim()),
  );
  assert.ok(techniqueOptions.some((item) => item.value === example.technique));
  for (const source of [
    example.sourceRepo,
    example.sourceArchive,
    example.reviewUrl,
  ]) {
    if (source)
      assert.ok(
        safeSourceUrl(source),
        'Source links must be public HTTPS URLs without credentials',
      );
  }
  assert.ok(
    !/\/Users\/|\/tmp\/|API_KEY|remaining credits/.test(example.prompt),
    'Prompts must be reusable without machine-specific context',
  );
  for (const asset of [example.video, example.poster]) {
    if (asset.startsWith('/')) {
      const info = await stat(new URL(`../public${asset}`, import.meta.url));
      assert.ok(info.size > 100, `${asset} must contain media`);
    } else {
      assert.equal(new URL(asset).protocol, 'https:');
    }
  }
}
console.log(
  `Verified ${examples.length} examples, category/audience/use-case/technique filtering, deep links, safe source URLs, prompt handoff, durations, and media references`,
);
