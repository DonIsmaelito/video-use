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
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
});
const exports = {};
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
  referencePrompt,
} = exports;

assert.equal(
  new Set(examples.map((example) => example.id)).size,
  examples.length,
  'Gallery IDs must be unique',
);
assert.ok(
  examples.length >= 16,
  'The initial gallery should include sixteen real examples',
);
assert.deepEqual(filterExamples('All examples', 'curated'), examples);
for (const category of categories.slice(1)) {
  const results = filterExamples(category, 'curated');
  assert.ok(results.length > 0, `${category} needs a working example`);
  assert.ok(results.every((example) => example.category === category));
}
const shortest = filterExamples('All examples', 'shortest');
assert.ok(
  shortest.every(
    (example, index) =>
      index === 0 || shortest[index - 1].duration <= example.duration,
  ),
);
const alphabetized = filterExamples('All examples', 'az');
assert.ok(
  alphabetized.every(
    (example, index) =>
      index === 0 ||
      alphabetized[index - 1].title.localeCompare(example.title) <= 0,
  ),
);
assert.notDeepEqual(
  shortest.map((example) => example.id),
  examples.map((example) => example.id),
  'Sorting must not mutate the curated list',
);
assert.equal(formatDuration(59.8), '1:00');
assert.equal(formatDuration(8), '0:08');
assert.equal(formatDuration(75.77), '1:16');

for (const example of examples) {
  assert.ok(categories.includes(example.category));
  assert.ok(example.prompt.trim().length >= 25);
  assert.ok(['Original prompt', 'Starter prompt'].includes(example.promptKind));
  assert.ok(Number.isFinite(example.duration) && example.duration > 0);
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
  const reference = referencePrompt(example, 'http://localhost:3001');
  assert.ok(
    reference.includes(new URL(example.video, 'http://localhost:3001').href),
  );
  assert.ok(reference.includes(example.prompt));
}
console.log(
  `Verified ${examples.length} examples, ${categories.length - 1} filters, sorting, durations, local media, and copy-reference content`,
);
