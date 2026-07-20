// Post-build step: inline above-the-fold CSS into dist/index.html.
//
// Why: Vite emits one render-blocking stylesheet. On slow-4G mobile that
// stylesheet alone was worth ~270 ms of FCP (Lighthouse "render-blocking
// requests"). Beasties (maintained fork of Critters) inlines the rules the
// initial viewport actually needs and demotes the full stylesheet to a
// non-blocking load via the media="print" onload swap.
//
// Runs as part of `npm run build` (see package.json). Fails the build loudly
// rather than silently shipping an unprocessed index.html.

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Beasties from 'beasties';

const distDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist');
const indexPath = path.join(distDir, 'index.html');

const beasties = new Beasties({
  path: distDir,
  publicPath: '/',
  // media="print" swap: works without JS-framework cooperation and degrades
  // to a normal stylesheet if JS is disabled (noscript fallback is emitted).
  preload: 'media',
  // Keep the full stylesheet intact — hashed asset must stay byte-identical
  // so its immutable cache entry is still valid for returning visitors.
  pruneSource: false,
  inlineFonts: false,
  // Include rules for elements just below the fold so first scroll doesn't FOUC.
  reduceInlineStyles: false,
  logLevel: 'warn',
});

const html = await readFile(indexPath, 'utf8');
const processed = await beasties.process(html);

if (!processed.includes('<style>') && !processed.includes('<style ')) {
  throw new Error('inline-critical: Beasties produced no inline <style>; refusing to overwrite index.html');
}

await writeFile(indexPath, processed);
console.log('inline-critical: critical CSS inlined into dist/index.html');
