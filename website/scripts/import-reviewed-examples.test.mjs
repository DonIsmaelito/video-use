import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const movieHash = 'a'.repeat(64);
const sourceHash = 'b'.repeat(64);
const changedHash = 'c'.repeat(64);
const hash = (text) => createHash('sha256').update(text, 'utf8').digest('hex');
const review =
  'Reviewed the complete encoded edit, readable captions, composition, audio continuity and final hold against the saved production evidence.';

function social(id = 'social-01-captioned-interview') {
  const base = 'https://media.example.test/' + id + '/';
  const prompt =
    'Turn the supplied interview into a concise social clip with accurate captions.';
  const promptSource =
    'Original executed creative request preserved from the reviewed production.';
  return {
    example: {
      id,
      title: 'Caption an Interview',
      category: 'Video Edits',
      description:
        'Make a useful short interview clip with accurate speech captions.',
      prompt,
      promptKind: 'Original prompt',
      promptSource,
      video: base + 'final.mp4',
      poster: base + 'poster.jpg',
      sourceArchive: base + 'source.zip',
      reviewUrl: base + 'review.md',
      duration: 20,
      orientation: 'portrait',
      technique: 'video-editing',
      audiences: ['Content creators'],
      useCases: ['Interview clips', 'Social content'],
    },
    source: {
      id,
      kind: 'original useful workflow produced with Video Use',
      sourceRun: id,
      production:
        'Video Use production with recorded framework identity and encoded output review.',
      websiteSha256: movieHash,
      editableSourceSha256: sourceHash,
      sourceArchive: base + 'source.zip',
      reviewUrl: base + 'review.md',
      promptSource,
      promptUrl: base + 'creative-prompt.txt',
    },
    publicCheck: { sha256: movieHash, bytes: 2000, rangeStatus: 206 },
    approval: {
      id,
      approved: true,
      sourceReviewed: true,
      sha256: movieHash,
      sourceSha256: sourceHash,
      review,
    },
    assets: {
      'final.mp4': base + 'final.mp4',
      'poster.jpg': base + 'poster.jpg',
      'source.zip': base + 'source.zip',
      'review.md': base + 'review.md',
      'creative-prompt.txt': base + 'creative-prompt.txt',
    },
    hashes: {
      'final.mp4': movieHash,
      'source.zip': sourceHash,
      'creative-prompt.txt': hash(prompt + '\n'),
    },
  };
}

function archive() {
  const receipt = social('screen-demo-feature-tour');
  receipt.example.promptKind = 'Starter prompt';
  receipt.example.promptSource =
    'Reconstructed starter from a saved Video Use screen demo; these words did not produce the archived film.';
  receipt.source.promptSource = receipt.example.promptSource;
  receipt.source.kind = 'archived screen demo created with Video Use';
  receipt.source.sourceArchiveScope =
    'Published film and reconstructed starter prompt; editable project not included';
  receipt.source.production =
    'Historical x-demo-maker export; creation evidence retained with the saved project and final render.';
  receipt.assets['prompt.txt'] = receipt.assets['creative-prompt.txt'].replace(
    'creative-prompt.txt',
    'prompt.txt',
  );
  receipt.hashes['prompt.txt'] = receipt.hashes['creative-prompt.txt'];
  receipt.source.promptUrl = receipt.assets['prompt.txt'];
  delete receipt.example.sourceArchive;
  delete receipt.source.sourceArchive;
  delete receipt.source.editableSourceSha256;
  delete receipt.approval.sourceReviewed;
  delete receipt.approval.sourceSha256;
  delete receipt.assets['source.zip'];
  delete receipt.hashes['source.zip'];
  delete receipt.assets['creative-prompt.txt'];
  delete receipt.hashes['creative-prompt.txt'];
  return receipt;
}

async function workspace(t) {
  const root = await mkdtemp(join(tmpdir(), 'video-use-import-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, 'scripts'));
  await mkdir(join(root, 'data'));
  await copyFile(
    new URL('./import-reviewed-examples.mjs', import.meta.url),
    join(root, 'scripts/import-reviewed-examples.mjs'),
  );
  const old = social('useful-26-website-loop');
  const baseline = {
    examples: [{ ...old.example, loop: true, muted: false }],
    'media-sources': [old.source],
    'mcp-launch': { src: null, video: null, poster: null, duration: null },
  };
  const paths = Object.keys(baseline).map((name) =>
    join(root, 'data', name + '.json'),
  );
  await Promise.all(
    Object.entries(baseline).map(([name, data]) =>
      writeFile(
        join(root, 'data', name + '.json'),
        JSON.stringify(data, null, 2) + '\n',
      ),
    ),
  );
  const before = await Promise.all(paths.map((path) => readFile(path, 'utf8')));
  const run = async (...receipts) => {
    const inputs = receipts.map((_, i) => join(root, 'receipt-' + i + '.json'));
    await Promise.all(
      inputs.map((path, i) => writeFile(path, JSON.stringify(receipts[i]))),
    );
    return spawnSync(
      process.execPath,
      [join(root, 'scripts/import-reviewed-examples.mjs'), ...inputs],
      { cwd: root, encoding: 'utf8', timeout: 10000 },
    );
  };
  const current = () =>
    Promise.all(paths.map((path) => readFile(path, 'utf8')));
  return { root, baseline, before, run, current };
}

test('imports reviewed social edits and honest archives without changing older entries', async (t) => {
  const w = await workspace(t);
  const second = social('social-02-speaker-reframe');
  const first = social();
  const archived = archive();
  const result = await w.run(second, archived, first);
  assert.equal(result.status, 0, result.stderr);
  const [examples, sources, launch] = (await w.current()).map(JSON.parse);
  assert.deepEqual(
    examples.map((entry) => entry.id),
    [
      first.example.id,
      second.example.id,
      archived.example.id,
      'useful-26-website-loop',
    ],
  );
  assert.deepEqual(examples.at(-1), w.baseline.examples[0]);
  assert.deepEqual(examples[2], archived.example);
  assert.equal(Object.hasOwn(examples[2], 'sourceArchive'), false);
  assert.equal(
    Object.hasOwn(
      sources.find((entry) => entry.id === archived.example.id),
      'editableSourceSha256',
    ),
    false,
  );
  assert.deepEqual(launch, w.baseline['mcp-launch']);
  first.example.loop = true;
  assert.equal((await w.run(first)).status, 0);
  delete first.example.loop;
  assert.equal((await w.run(first)).status, 0);
  const updated = JSON.parse((await w.current())[0]);
  assert.equal(
    updated.find((entry) => entry.id === first.example.id).loop,
    true,
  );
  assert.equal(new Set(updated.map((entry) => entry.id)).size, updated.length);
});

test('keeps legacy useful and MCP receipts compatible and preserves curated playback metadata', async (t) => {
  const w = await workspace(t);
  const old = social('useful-26-website-loop');
  delete old.approval;
  const mcp = social('mcp-launch');
  delete mcp.approval;
  mcp.assets['autoplay.mp4'] =
    'https://media.example.test/mcp-launch/autoplay.mp4';
  const result = await w.run(old, mcp);
  assert.equal(result.status, 0, result.stderr);
  const [examples, , launch] = (await w.current()).map(JSON.parse);
  assert.equal(examples.length, 1);
  assert.equal(examples[0].loop, true);
  assert.equal(examples[0].muted, false);
  assert.deepEqual(launch, {
    src: mcp.assets['autoplay.mp4'],
    video: mcp.example.video,
    poster: mcp.example.poster,
    duration: mcp.example.duration,
  });
});

const rejected = [
  [
    'missing social approval',
    social,
    (r) => {
      delete r.approval;
    },
  ],
  [
    'unapproved social movie',
    social,
    (r) => {
      r.approval.approved = false;
    },
  ],
  [
    'approval for another ID',
    social,
    (r) => {
      r.approval.id = 'social-99-other';
    },
  ],
  [
    'changed movie after approval',
    social,
    (r) => {
      r.approval.sha256 = changedHash;
    },
  ],
  [
    'published movie hash mismatch',
    social,
    (r) => {
      r.hashes['final.mp4'] = changedHash;
    },
  ],
  [
    'source ledger movie mismatch',
    social,
    (r) => {
      r.source.websiteSha256 = changedHash;
    },
  ],
  [
    'unreviewed editable source',
    social,
    (r) => {
      r.approval.sourceReviewed = false;
    },
  ],
  [
    'missing approved source hash',
    social,
    (r) => {
      delete r.approval.sourceSha256;
    },
  ],
  [
    'changed editable source ledger',
    social,
    (r) => {
      r.source.editableSourceSha256 = changedHash;
    },
  ],
  [
    'changed published source archive',
    social,
    (r) => {
      r.hashes['source.zip'] = changedHash;
    },
  ],
  [
    'source URL substituted after publication',
    social,
    (r) => {
      r.assets['source.zip'] += '?different=1';
    },
  ],
  [
    'missing social source archive',
    social,
    (r) => {
      delete r.example.sourceArchive;
    },
  ],
  [
    'social prompt relabeled as a starter',
    social,
    (r) => {
      r.example.promptKind = 'Starter prompt';
    },
  ],
  [
    'changed social prompt text',
    social,
    (r) => {
      r.example.prompt += ' Changed after review.';
    },
  ],
  [
    'missing public prompt hash',
    social,
    (r) => {
      delete r.hashes['creative-prompt.txt'];
    },
  ],
  [
    'prompt URL mismatch',
    social,
    (r) => {
      r.source.promptUrl += '?different=1';
    },
  ],
  [
    'unapproved archive',
    archive,
    (r) => {
      r.approval.approved = false;
    },
  ],
  [
    'archive claims an original prompt',
    archive,
    (r) => {
      r.example.promptKind = 'Original prompt';
    },
  ],
  [
    'archive prompt text changed',
    archive,
    (r) => {
      r.example.prompt += ' Changed after review.';
    },
  ],
  [
    'archive claims a new production',
    archive,
    (r) => {
      r.source.kind = 'newly generated workflow';
    },
  ],
  [
    'archive omits its creation evidence',
    archive,
    (r) => {
      delete r.source.production;
    },
  ],
  [
    'archive links an unreviewed project',
    archive,
    (r) => {
      r.example.sourceArchive = 'https://media.example.test/source.zip';
    },
  ],
  [
    'archive hides a ZIP in its asset map',
    archive,
    (r) => {
      r.assets['source.zip'] = 'https://media.example.test/source.zip';
    },
  ],
  [
    'archive claims source review',
    archive,
    (r) => {
      r.approval.sourceReviewed = true;
    },
  ],
  [
    'archive claims an editable hash',
    archive,
    (r) => {
      r.source.editableSourceSha256 = sourceHash;
    },
  ],
  [
    'unverified byte-range media',
    social,
    (r) => {
      r.publicCheck.rangeStatus = 200;
    },
  ],
  [
    'credential-bearing public link',
    archive,
    (r) => {
      r.example.reviewUrl = 'https://secret@example.test/review.md';
    },
  ],
  [
    'unsupported import namespace',
    social,
    (r) => {
      r.example.id = 'unreviewed-film';
    },
  ],
];

for (const [label, make, mutate] of rejected) {
  test('rejects ' + label + ' before changing any manifest', async (t) => {
    const w = await workspace(t);
    const invalid = make();
    mutate(invalid);
    // The valid sibling is intentionally first: a later failure must not publish it.
    const result = await w.run(social('social-03-valid-sibling'), invalid);
    assert.notEqual(result.status, 0, 'Invalid receipt was accepted');
    assert.deepEqual(
      await w.current(),
      w.before,
      'A rejected batch changed a manifest',
    );
  });
}
