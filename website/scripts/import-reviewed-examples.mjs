// Run after publish_useful_video has verified the reviewed bytes at their public URL.
// node scripts/import-reviewed-examples.mjs /path/to/published-receipt.json [...]
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile, rename } from 'node:fs/promises';

const sha256 = /^[a-f0-9]{64}$/;
const archiveKind = 'archived screen demo created with Video Use';
const archiveScope =
  'Published film and reconstructed starter prompt; editable project not included';

function object(value, label) {
  assert.ok(
    value && typeof value === 'object' && !Array.isArray(value),
    label + ' must be an object',
  );
  return value;
}

function https(value, label) {
  assert.equal(typeof value, 'string', label + ' must be a public HTTPS URL');
  const url = new URL(value);
  assert.ok(
    url.protocol === 'https:' && !url.username && !url.password,
    label + ' must be a public HTTPS URL without credentials',
  );
}

// New campaign receipts carry the public subset of their exact final approval.
// Older useful/MCP receipts retain their established publication contract.
function validateCampaignReceipt(receipt, archived) {
  const { example, source, publicCheck } = receipt;
  const approval = object(receipt.approval, 'Final approval');
  const assets = object(receipt.assets, 'Published assets');
  const hashes = object(receipt.hashes, 'Published hashes');
  assert.equal(approval.id, example.id, 'Approval must identify this example');
  assert.equal(
    approval.approved,
    true,
    'Final media must be explicitly approved',
  );
  assert.ok(
    typeof approval.review === 'string' && approval.review.trim().length >= 80,
    'Approval must describe the actual review',
  );
  assert.match(approval.sha256, sha256, 'Approval must bind the exact movie');
  assert.equal(
    approval.sha256,
    publicCheck.sha256,
    'Approved movie differs from published movie',
  );
  assert.equal(
    hashes['final.mp4'],
    approval.sha256,
    'Published movie hash differs from approval',
  );
  assert.equal(
    assets['final.mp4'],
    example.video,
    'Movie URL differs from the published asset',
  );
  assert.equal(
    assets['poster.jpg'],
    example.poster,
    'Poster URL differs from the published asset',
  );
  assert.equal(
    assets['review.md'],
    example.reviewUrl,
    'Review URL differs from the published asset',
  );
  assert.equal(
    source.reviewUrl,
    example.reviewUrl,
    'Source ledger must link the same review',
  );
  assert.ok(
    typeof source.production === 'string' &&
      source.production.trim().length >= 40,
    'Describe the actual creation evidence',
  );
  assert.ok(
    typeof source.sourceRun === 'string' && source.sourceRun.trim(),
    'Identify the actual source run',
  );
  assert.ok(
    typeof example.promptSource === 'string' &&
      example.promptSource.trim().length >= 25,
    'Describe the prompt provenance',
  );
  assert.equal(
    source.promptSource,
    example.promptSource,
    'Prompt provenance differs between example and source',
  );

  const promptFile = archived ? 'prompt.txt' : 'creative-prompt.txt';
  assert.ok(
    typeof example.prompt === 'string' && example.prompt.trim().length >= 25,
    'Provide the reviewed prompt text',
  );
  https(assets[promptFile], 'Published prompt');
  assert.equal(
    source.promptUrl,
    assets[promptFile],
    'Prompt URL differs from the published asset',
  );
  const promptHash = createHash('sha256')
    .update(example.prompt + '\n', 'utf8')
    .digest('hex');
  assert.equal(
    hashes[promptFile],
    promptHash,
    'Displayed prompt differs from the published UTF-8 prompt file',
  );

  if (archived) {
    assert.equal(
      example.promptKind,
      'Starter prompt',
      'An archive without replay source must use a Starter prompt',
    );
    assert.equal(
      source.kind,
      archiveKind,
      'Identify the historical screen demo honestly',
    );
    assert.equal(
      source.sourceArchiveScope,
      archiveScope,
      'Disclose that the editable project is not included',
    );
    assert.notEqual(
      approval.sourceReviewed,
      true,
      'A no-source archive cannot claim editable-source review',
    );
    for (const [record, field] of [
      [example, 'sourceArchive'],
      [source, 'sourceArchive'],
      [source, 'editableSourceSha256'],
      [approval, 'sourceSha256'],
      [assets, 'source.zip'],
      [hashes, 'source.zip'],
    ]) {
      assert.equal(
        record[field],
        undefined,
        'A no-source archive must not publish or claim ' + field,
      );
    }
  } else {
    assert.equal(
      example.promptKind,
      'Original prompt',
      'A new social edit must preserve its executed prompt',
    );
    assert.equal(
      approval.sourceReviewed,
      true,
      'Editable source must be explicitly reviewed',
    );
    assert.match(
      approval.sourceSha256,
      sha256,
      'Approval must bind the exact editable source',
    );
    assert.equal(
      source.editableSourceSha256,
      approval.sourceSha256,
      'Source ledger hash differs from approval',
    );
    assert.equal(
      hashes['source.zip'],
      approval.sourceSha256,
      'Published source hash differs from approval',
    );
    https(example.sourceArchive, 'Editable project');
    assert.equal(
      source.sourceArchive,
      example.sourceArchive,
      'Source ledger must link the same editable project',
    );
    assert.equal(
      assets['source.zip'],
      example.sourceArchive,
      'Editable project URL differs from the published asset',
    );
  }
}

const files = process.argv.slice(2);
assert.ok(files.length, 'Provide one or more reviewed publication receipts');
const dataFile = (name) => new URL(`../data/${name}.json`, import.meta.url);
const read = async (name) => JSON.parse(await readFile(dataFile(name), 'utf8'));
const examples = await read('examples');
const sources = await read('media-sources');
let launch = await read('mcp-launch');
const additions = [];
for (const file of files) {
  const receipt = JSON.parse(await readFile(file, 'utf8'));
  const { example, source, publicCheck, assets } = receipt;
  assert.match(
    example.id,
    /^(useful-\d{2}-[a-z0-9-]+|social-\d{2}-[a-z0-9-]+|screen-demo-[a-z0-9-]+|mcp-launch)$/,
  );
  assert.equal(source.id, example.id);
  assert.equal(source.websiteSha256, publicCheck.sha256);
  assert.match(publicCheck.sha256, sha256);
  assert.equal(publicCheck.rangeStatus, 206);
  assert.ok(publicCheck.bytes > 1000);
  for (const field of ['video', 'poster', 'reviewUrl']) {
    https(example[field], field);
  }
  const archived = example.id.startsWith('screen-demo-');
  if (archived || example.id.startsWith('social-'))
    validateCampaignReceipt(receipt, archived);
  else https(example.sourceArchive, 'Editable project');
  if (example.id === 'mcp-launch') {
    assert.equal(new URL(assets['autoplay.mp4']).protocol, 'https:');
    launch = {
      src: assets['autoplay.mp4'],
      video: example.video,
      poster: example.poster,
      duration: example.duration,
    };
  } else {
    const index = examples.findIndex((item) => item.id === example.id);
    if (index === -1) additions.push(example);
    else {
      // Playback is curated website metadata and may postdate the publication receipt.
      const loop = example.loop ?? examples[index].loop;
      const muted = example.muted ?? examples[index].muted;
      examples[index] = {
        ...example,
        ...(loop === undefined ? {} : { loop }),
        ...(muted === undefined ? {} : { muted }),
      };
    }
  }
  const index = sources.findIndex((item) => item.id === source.id);
  if (index === -1) sources.push(source);
  else sources[index] = source;
}
const updated = [...additions, ...examples];
// Keep each reviewed campaign together, with the latest edits and demos first.
function campaignRank(id) {
  if (id.startsWith('social-')) return 0;
  if (id.startsWith('screen-demo-')) return 1;
  if (id.startsWith('useful-')) return 2;
  return 3;
}
updated.sort((a, b) => {
  const aRank = campaignRank(a.id);
  const bRank = campaignRank(b.id);
  return aRank === bRank
    ? aRank < 3
      ? a.id.localeCompare(b.id)
      : 0
    : aRank - bRank;
});
assert.equal(new Set(updated.map((item) => item.id)).size, updated.length);
for (const [name, value] of [
  ['examples', updated],
  ['media-sources', sources],
  ['mcp-launch', launch],
]) {
  const target = dataFile(name);
  const temporary = new URL(target.href + '.tmp');
  await writeFile(temporary, JSON.stringify(value, null, 2) + '\n');
  await rename(temporary, target);
}
console.log(
  `Registered ${files.length} reviewed deliveries. Gallery: ${updated.length} examples. MCP film: ${launch.src ? 'ready' : 'pending'}.`,
);
