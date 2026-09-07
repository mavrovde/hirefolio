#!/usr/bin/env node
/**
 * Regenerate the social-share card `projects/public/src/assets/og-image.png` (#71).
 *
 * `SeoService` has always advertised `${SITE_URL}/assets/og-image.png` as
 * `og:image`/`twitter:image`, but the file was never in the repo — every share
 * of the site pointed a crawler at a 404. This script renders the committed
 * PNG so the asset has provenance instead of being an opaque binary blob.
 *
 * The card is deliberately IDENTITY-NEUTRAL: owner name/headline are runtime
 * config (#65) and cannot be baked into a static image, so it carries only the
 * site's terminal styling. Final branded artwork is issue #311's job.
 *
 * Usage: node scripts/generate-og-image.mjs   (uses the repo's Playwright Chromium)
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const OUT = join(
  fileURLToPath(new URL('..', import.meta.url)),
  'projects',
  'public',
  'src',
  'assets',
  'og-image.png',
);

// 1200x630 is the Open Graph / Twitter `summary_large_image` reference size.
const WIDTH = 1200;
const HEIGHT = 630;

const HTML = `<!doctype html>
<html><head><meta charset="utf-8"><style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: ${WIDTH}px; height: ${HEIGHT}px; background: #000; color: #33ff00;
    font-family: "Courier New", Courier, monospace;
    display: flex; align-items: center; justify-content: center;
  }
  .frame { width: 1080px; height: 510px; border: 3px solid #33ff00; padding: 48px 56px; position: relative;
           display: flex; flex-direction: column; justify-content: center; }
  .frame::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: repeating-linear-gradient(180deg, rgba(51,255,0,.07) 0 2px, transparent 2px 4px);
  }
  .bar { font-size: 26px; opacity: .75; letter-spacing: 2px; }
  h1 { font-size: 92px; line-height: 1.05; margin: 36px 0 22px; letter-spacing: 4px; }
  p { font-size: 30px; opacity: .85; white-space: nowrap; }
  .cursor { display: inline-block; width: 22px; height: 28px; background: #33ff00; vertical-align: -4px; margin-left: 10px; }
</style></head>
<body><div class="frame">
  <div class="bar">~/portfolio &mdash; bash &mdash; 80x24</div>
  <h1>$ whoami</h1>
  <p>&gt; engineering portfolio &middot; cv &middot; blog &middot; ai demos<span class="cursor"></span></p>
</div></body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
await page.setContent(HTML);
await page.screenshot({ path: OUT, type: 'png' });
await browser.close();
console.log(`wrote ${OUT} (${WIDTH}x${HEIGHT})`);
