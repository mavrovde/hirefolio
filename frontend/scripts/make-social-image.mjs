#!/usr/bin/env node
/**
 * Regenerate the project's marketing artwork (#311) — one composition, two sizes:
 *
 *   docs/assets/social-preview.png                     1280x640  (GitHub Settings -> Social
 *                                                                 preview + the README banner)
 *   frontend/projects/public/src/assets/og-image.png   1200x630  (the site's own og:image /
 *                                                                 twitter:image, #71)
 *
 * WHY A SCRIPT AND NOT A HAND-MADE PNG: this repo is a fork-and-go template
 * (#61/#88), so a forker must be able to re-brand the artwork instead of
 * inheriting someone else's. Everything identifying is a constant below and is
 * overridable from the environment — see BRAND.
 *
 * WHY NO SCREENSHOT OF THE LIVE SITE: the home hero renders `profile.name` and
 * `assets/images/profile.png` from runtime config, so a raw capture would bake a
 * PERSON into the artwork and propagate them into every fork (#311, #66). The
 * card therefore carries the PRODUCT identity, drawn in the site's own visual
 * language: `#33ff00` phosphor on `#050505`, VT323, matrix grid, scanlines,
 * terminal prompt (projects/public/src/styles.css:3-24,27-57 and
 * projects/public/src/app/components/hero/hero.component.html:2-19).
 *
 * Usage:
 *   node frontend/scripts/make-social-image.mjs        # or: bash scripts/make-social-image.sh
 *   BRAND_NAME=Yourfolio BRAND_URL=github.com/you/yourfolio node frontend/scripts/make-social-image.mjs
 */
import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const FRONTEND = fileURLToPath(new URL('..', import.meta.url));
const REPO = join(FRONTEND, '..');

/** Everything a forker re-brands. No owner name, no headshot, by design (#311). */
const BRAND = {
  name: process.env.BRAND_NAME ?? 'HIREFOLIO',
  host: process.env.BRAND_HOST ?? 'hirefolio',
  tagline:
    process.env.BRAND_TAGLINE ??
    'fork-and-go portfolio + recruiter comms for engineers',
  features: (
    process.env.BRAND_FEATURES ?? 'semantic search,local AI,recruiter inbox,self-hosted'
  ).split(','),
  url: process.env.BRAND_URL ?? 'github.com/mavrovde/hirefolio',
};

/** width, height, output path — the two surfaces the artwork has to serve. */
const TARGETS = [
  { width: 1280, height: 640, out: join(REPO, 'docs', 'assets', 'social-preview.png') },
  {
    width: 1200,
    height: 630,
    out: join(FRONTEND, 'projects', 'public', 'src', 'assets', 'og-image.png'),
  },
];

/**
 * VT323 is the site's typeface, loaded from Google Fonts by `index.html:16`. We
 * embed the same file as a data URI instead of letting headless Chromium fetch
 * it, so the render never depends on the browser's network stack, and cache it
 * so a second run (and an offline one) is deterministic. If it cannot be
 * obtained we fall back to a monospace stack and SAY SO — a silently different
 * render is worse than a documented one.
 */
const FONT_CACHE = join(FRONTEND, 'scripts', '.cache', 'vt323.woff2');
const UA_WOFF2 =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
/** The exact bytes the committed artwork was rendered with. Pinned so
 *  "deterministic" is mechanical, not incidental: a different VT323 revision (or
 *  a captive-portal HTML page served as a font) changes the render, and this is
 *  what notices. */
export const VT323_SHA256 = '0ee3d783a89f050280fb48f7fec8602c6922da1716856f75089e4c77d61de9c7';

/**
 * A font is only usable if it IS a font and IS the pinned one. Without this a
 * non-2xx body (error page, captive portal, rate-limit HTML) was written to the
 * cache and embedded, and every later run logged "VT323 embedded" while silently
 * rendering Courier — a poisoned cache that no gate could see.
 */
export function verifyFont(buffer, sha256 = VT323_SHA256) {
  if (buffer.length < 4 || buffer.toString('latin1', 0, 4) !== 'wOF2') {
    throw new Error(`not a woff2 file (magic ${JSON.stringify(buffer.toString('latin1', 0, 4))})`);
  }
  const digest = createHash('sha256').update(buffer).digest('hex');
  if (digest !== sha256) {
    throw new Error(`woff2 sha256 ${digest} does not match the pinned ${sha256}`);
  }
  return buffer;
}

async function fetchOk(url, init) {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`${url} responded ${response.status} ${response.statusText}`);
  return response;
}

async function loadFont() {
  try {
    // A previously poisoned or stale cache must not survive: it is verified on
    // read exactly like a fresh download, and re-fetched when it fails.
    return verifyFont(await readFile(FONT_CACHE));
  } catch {
    /* not cached, or the cached bytes are not the pinned font — fetch below */
  }
  const css = await (
    await fetchOk('https://fonts.googleapis.com/css2?family=VT323&display=swap', {
      headers: { 'user-agent': UA_WOFF2 },
    })
  ).text();
  const url = css.match(/url\((https:\/\/[^)]+\.woff2)\)/)?.[1];
  if (!url) throw new Error('no woff2 URL in the Google Fonts CSS response');
  const font = verifyFont(Buffer.from(await (await fetchOk(url)).arrayBuffer()));
  await mkdir(dirname(FONT_CACHE), { recursive: true });
  await writeFile(FONT_CACHE, font);
  return font;
}

const html = (w, h, fontFace) => {
  // One layout, two canvases: every dimension scales off the 1280x640 reference
  // so the 1200x630 variant is the same picture, not a squeezed one.
  const s = (px) => `${((px * h) / 640).toFixed(2)}px`;
  // Whole-pixel sizing for the repeating overlays: a fractional scanline period
  // resamples into per-row noise that PNG cannot compress (measured: 701 KB vs
  // 219 KB for the same 1200x630 card).
  const px = (n) => `${Math.max(1, Math.round((n * h) / 640))}px`;
  const chips = BRAND.features
    .map((f) => `<span class="chip">${f.trim()}</span>`)
    .join('<span class="sep">/</span>');
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  ${fontFace}
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: ${w}px; height: ${h}px; background: #050505; color: #33ff00;
    font-family: 'VT323', 'Courier New', Courier, monospace;
    display: flex; align-items: center; justify-content: center; overflow: hidden;
  }
  /* Matrix grid — hero.component.html:4 */
  .grid {
    position: absolute; inset: 0;
    background-image:
      linear-gradient(rgba(0,255,0,.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,255,0,.05) 1px, transparent 1px);
    background-size: ${px(32)} ${px(32)};
  }
  /* Phosphor bloom + vignette — styles.css:28,60 */
  .bloom { position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 45%, rgba(51,255,0,.13), transparent 62%); }
  .vignette { position: absolute; inset: 0;
    background: radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,.85)); }
  /* Scanlines — styles.css:41-57, static (a screenshot has no time axis, so the
     flicker animation is dropped). The site's RGB chroma stripe is dropped too:
     invisible at card scale and measured at a third of the file size. */
  .scan { position: absolute; inset: 0; z-index: 50;
    background: linear-gradient(rgba(18,16,16,0) 50%, rgba(0,0,0,.28) 50%);
    background-size: 100% ${px(3)}; }

  .frame { position: relative; z-index: 10;
    width: ${s(1112)}; height: ${s(520)};
    border: ${s(2)} solid #33ff00; background: rgba(10,21,10,.55);
    box-shadow: 0 0 ${s(40)} rgba(51,255,0,.25), inset 0 0 ${s(60)} rgba(51,255,0,.06);
    display: flex; flex-direction: column; }
  .titlebar { display: flex; justify-content: space-between; align-items: center;
    padding: ${s(6)} ${s(18)}; border-bottom: ${s(2)} solid rgba(51,255,0,.5);
    font-size: ${s(24)}; color: rgba(51,255,0,.7); letter-spacing: ${s(1)}; }
  .dots { letter-spacing: ${s(4)}; }
  /* Safe area: all meaning lives in the middle ~2:1 of the canvas so Slack, X and
     GitHub can crop differently without eating the wordmark (#311). */
  .body { flex: 1; display: flex; flex-direction: column; justify-content: center;
    align-items: center; text-align: center; padding: 0 ${s(60)}; }
  .prompt { font-size: ${s(28)}; color: rgba(51,255,0,.75); letter-spacing: ${s(1)}; }
  h1 { font-size: ${s(150)}; line-height: 1; letter-spacing: ${s(14)};
    margin: ${s(10)} 0 ${s(8)}; text-indent: ${s(14)};
    text-shadow: 0 0 ${s(9)} rgba(51,255,0,.7), 0 0 ${s(30)} rgba(51,255,0,.35); }
  .tagline { font-size: ${s(30)}; color: #33ff00; opacity: .92; }
  .fit { white-space: nowrap; }
  .chips { margin-top: ${s(18)}; font-size: ${s(26)}; color: rgba(51,255,0,.72);
    display: flex; gap: ${s(12)}; align-items: baseline; }
  .sep { color: rgba(51,255,0,.35); }
  .url { margin-top: ${s(22)}; font-size: ${s(30)}; letter-spacing: ${s(1)}; }
  .cursor { display: inline-block; width: ${s(16)}; height: ${s(24)};
    background: #33ff00; vertical-align: ${s(-3)}; margin-left: ${s(8)};
    box-shadow: 0 0 ${s(10)} rgba(51,255,0,.8); }
</style></head><body>
  <div class="grid"></div><div class="bloom"></div>
  <div class="frame">
    <div class="titlebar"><span>~/${BRAND.host} &mdash; bash &mdash; 96x28</span><span class="dots">[ ][ ][x]</span></div>
    <div class="body">
      <div class="prompt fit" data-field="BRAND_HOST">you@${BRAND.host}:~$ ./deploy.sh --domain="your-name.dev"</div>
      <h1 class="fit" data-field="BRAND_NAME">${BRAND.name}</h1>
      <div class="tagline fit" data-field="BRAND_TAGLINE">// ${BRAND.tagline}</div>
      <div class="chips fit" data-field="BRAND_FEATURES">${chips}</div>
      <div class="url fit" data-field="BRAND_URL">&gt; ${BRAND.url}<span class="cursor"></span></div>
    </div>
  </div>
  <div class="vignette"></div><div class="scan"></div>
</body></html>`;
};

/**
 * The ONLY chunks the artwork may carry. An allowlist, not a denylist: an
 * unknown ancillary chunk is exactly the case a denylist misses, and
 * `scripts/check_no_pii.sh` is text-only and cannot look inside a PNG
 * (`scripts/check_no_pii.sh:9-11`), so metadata leaked here would pass every
 * gate in the repo.
 */
export const ALLOWED_PNG_CHUNKS = ['IHDR', 'PLTE', 'IDAT', 'IEND'];
/** GitHub's social-preview ceiling. */
export const MAX_BYTES = 1_000_000;

/**
 * Verify what was actually written, not what was intended (#311 acceptance
 * criteria, enforced by the producer instead of by a reviewer's eye): declared
 * dimensions, the size ceiling, and the chunk allowlist. Throws — a broken card
 * must fail the run, not be committed quietly.
 */
export function assertCleanPng(png, { width, height, label = 'png' }) {
  const [w, h] = [png.readUInt32BE(16), png.readUInt32BE(20)];
  if (w !== width || h !== height) {
    throw new Error(`${label}: rendered ${w}x${h}, expected ${width}x${height}`);
  }
  if (png.length >= MAX_BYTES) {
    throw new Error(`${label}: ${png.length} bytes — over GitHub's ${MAX_BYTES} byte limit`);
  }
  const chunks = new Set();
  for (let i = 8; i < png.length; i += 12 + png.readUInt32BE(i)) {
    chunks.add(png.toString('latin1', i + 4, i + 8));
  }
  const unexpected = [...chunks].filter((c) => !ALLOWED_PNG_CHUNKS.includes(c));
  if (unexpected.length) {
    throw new Error(`${label}: carries non-image chunks ${unexpected.join(', ')}`);
  }
  return png.length;
}

/** Never shrink a row below this fraction of its design size. */
export const MIN_FIT_RATIO = 0.6;

/**
 * Shrink one single-line row until it fits its column — BOUNDED. A row whose
 * width is dominated by fixed-px letter-spacing or flex gaps can never fit no
 * matter how small the glyphs get, and the first version of this loop spun
 * forever on exactly that input (review of PR #320: an ~79-character product
 * name hung the render). It now stops at MIN_FIT_RATIO of the design size and
 * throws, naming the BRAND_* field to shorten, because a hang tells the forker
 * nothing and a silently overflowing card is not better than an error.
 *
 * `row` is an async, DOM-free interface (`field`, `fontSize`, `setFontSize`,
 * `overflow`) so the algorithm is testable without a browser; the generator
 * backs it with Playwright element handles.
 */
export async function shrinkToFit(row, minRatio = MIN_FIT_RATIO) {
  const base = await row.fontSize();
  const floor = Math.max(1, Math.ceil(base * minRatio));
  let size = base;
  while ((await row.overflow()) > 0 && size > floor) {
    size -= 1;
    await row.setFontSize(size);
  }
  if ((await row.overflow()) > 0) {
    throw new Error(
      `${row.field} does not fit the terminal frame even at ${size}px ` +
        `(${Math.round(minRatio * 100)}% of the design size) — shorten it.`,
    );
  }
  return size;
}

/**
 * Playwright-backed rows. The fit limit is the parent's CONTENT box: its
 * `clientWidth` still includes the padding that IS the card's safe area, so
 * measuring against it let rows sit a few pixels off the frame border (review of
 * PR #320) instead of inside the documented margin.
 */
async function rowsOf(page) {
  const handles = await page.$$('.fit');
  return Promise.all(
    handles.map(async (el) => ({
      field: await el.evaluate((node) => node.dataset.field),
      fontSize: () => el.evaluate((node) => parseFloat(getComputedStyle(node).fontSize)),
      setFontSize: (size) => el.evaluate((node, px) => (node.style.fontSize = `${px}px`), size),
      overflow: () =>
        el.evaluate((node) => {
          const parent = node.parentElement;
          const style = getComputedStyle(parent);
          const content =
            parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          return node.scrollWidth - content;
        }),
    })),
  );
}

async function main() {
  let fontFace = '';
  try {
    const font = await loadFont();
    fontFace = `@font-face { font-family: 'VT323'; font-style: normal; font-weight: 400;
    src: url(data:font/woff2;base64,${font.toString('base64')}) format('woff2'); }`;
    console.log(`font: VT323 embedded (${font.length} bytes, cached at scripts/.cache/vt323.woff2)`);
  } catch (error) {
    console.warn(
      `font: VT323 UNAVAILABLE (${error.message}) — falling back to Courier. The committed artwork was rendered WITH VT323; re-run online to match it.`,
    );
  }

  const browser = await chromium.launch();
  try {
    for (const { width, height, out } of TARGETS) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
      await page.setContent(html(width, height, fontFace), { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      // A re-branded name or tagline (BRAND_*) is arbitrary text, so every
      // single-line row is shrunk until it fits its column instead of bleeding
      // through the terminal frame. No-op for text that already fits.
      for (const row of await rowsOf(page)) await shrinkToFit(row);
      await mkdir(dirname(out), { recursive: true });
      await page.screenshot({ path: out, type: 'png' });
      await page.close();
      const bytes = assertCleanPng(await readFile(out), { width, height, label: out });
      console.log(`wrote ${out} (${width}x${height}, ${bytes} bytes)`);
    }

    // Legibility evidence (#311): the social preview as a link-unfurl thumbnail.
    // Produced by DOWNSCALING the real PNG — which is what Slack/X/GitHub do —
    // and not by re-laying-out at a small size, which would flatter the design.
    const thumb = {
      width: 320,
      height: 160,
      out: join(REPO, 'docs', 'assets', 'social-preview-thumbnail.png'),
    };
    const source = (await readFile(TARGETS[0].out)).toString('base64');
    const page = await browser.newPage({
      viewport: { width: thumb.width, height: thumb.height },
      deviceScaleFactor: 1,
    });
    await page.setContent(
      `<body style="margin:0"><img src="data:image/png;base64,${source}" width="${thumb.width}" height="${thumb.height}"></body>`,
      { waitUntil: 'load' },
    );
    await page.screenshot({ path: thumb.out, type: 'png' });
    await page.close();
    const bytes = assertCleanPng(await readFile(thumb.out), { ...thumb, label: thumb.out });
    console.log(`wrote ${thumb.out} (${thumb.width}x${thumb.height}, ${bytes} bytes)`);
  } finally {
    await browser.close();
  }
}

// Importable for `make-social-image.test.mjs`; renders only when run directly.
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await main();
