// Run after publish_useful_video has verified the reviewed bytes at their public URL.
// node scripts/import-reviewed-examples.mjs /path/to/published-receipt.json [...]
import assert from 'node:assert/strict';
import { readFile, writeFile, rename } from 'node:fs/promises';

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
  assert.match(example.id, /^(useful-\d{2}-[a-z0-9-]+|mcp-launch)$/);
  assert.equal(source.id, example.id);
  assert.equal(source.websiteSha256, publicCheck.sha256);
  assert.match(publicCheck.sha256, /^[a-f0-9]{64}$/);
  assert.equal(publicCheck.rangeStatus, 206);
  assert.ok(publicCheck.bytes > 1000);
  for (const url of [example.video, example.poster, example.sourceArchive, example.reviewUrl]) {
    assert.equal(new URL(url).protocol, 'https:');
  }
  if (example.id === 'mcp-launch') {
    assert.equal(new URL(assets['autoplay.mp4']).protocol, 'https:');
    launch = { src: assets['autoplay.mp4'], video: example.video, poster: example.poster, duration: example.duration };
  } else {
    const index = examples.findIndex((item) => item.id === example.id);
    if (index === -1) additions.push(example);
    else examples[index] = example;
  }
  const index = sources.findIndex((item) => item.id === source.id);
  if (index === -1) sources.push(source);
  else sources[index] = source;
}
const updated = [...additions, ...examples];
// Keep the useful workflow sequence together ahead of the older studies.
updated.sort((a, b) => {
  const aNew = a.id.startsWith('useful-');
  const bNew = b.id.startsWith('useful-');
  return aNew && bNew ? a.id.localeCompare(b.id) : Number(bNew) - Number(aNew);
});
assert.equal(new Set(updated.map((item) => item.id)).size, updated.length);
for (const [name, value] of [['examples', updated], ['media-sources', sources], ['mcp-launch', launch]]) {
  const target = dataFile(name);
  const temporary = new URL(target.href + '.tmp');
  await writeFile(temporary, JSON.stringify(value, null, 2) + '\n');
  await rename(temporary, target);
}
console.log(`Registered ${files.length} reviewed deliveries. Gallery: ${updated.length} examples. MCP film: ${launch.src ? 'ready' : 'pending'}.`);
