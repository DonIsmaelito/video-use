import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const result = await build({entryPoints:[fileURLToPath(new URL('question-app.js',import.meta.url))],bundle:true,write:false,format:'iife',target:'es2022',minify:true});
const template = await readFile(new URL('question-template.html',import.meta.url),'utf8');
await writeFile(new URL('question-card.html',import.meta.url),template.replace('/* QUESTION_APP_BUNDLE */',()=>result.outputFiles[0].text.replaceAll('</script','<\\/script')));
