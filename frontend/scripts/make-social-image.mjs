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

async function loadFont() {
  try {
    return await readFile(FONT_CACHE);
  } catch {
    /* not cached yet — fetch it below */
  }
  const css = await (
    await fetch('https://fonts.googleapis.com/css2?family=VT323&display=swap', {
      headers: { 'user-agent': UA_WOFF2 },
    })
  ).text();
  const url = css.match(/url\((https:\/\/[^)]+\.woff2)\)/)?.[1];
  if (!url) throw new Error('no woff2 URL in the Google Fonts CSS response');
  const font = Buffer.from(await (await fetch(url)).arrayBuffer());
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
      <div class="prompt fit">you@${BRAND.host}:~$ ./deploy.sh --domain="your-name.dev"</div>
      <h1 class="fit">${BRAND.name}</h1>
      <div class="tagline fit">// ${BRAND.tagline}</div>
      <div class="chips fit">${chips}</div>
      <div class="url fit">&gt; ${BRAND.url}<span class="cursor"></span></div>
    </div>
  </div>
  <div class="vignette"></div><div class="scan"></div>
</body></html>`;
};

/**
 * Verify what was actually written, not what was intended (#311 acceptance
 * criteria, enforced by the producer instead of by a reviewer's eye):
 *  - the PNG carries the demanded dimensions;
 *  - it stays under GitHub's 1 MB social-preview limit;
 *  - it contains NO ancillary text/EXIF chunk. `scripts/check_no_pii.sh` is
 *    text-only and cannot look inside a PNG, so metadata that leaked here would
 *    pass every gate in the repo.
 * Throws — a broken card must fail the run, not be committed quietly.
 */
async function assertClean(out, width, height) {
  const png = await readFile(out);
  const [w, h] = [png.readUInt32BE(16), png.readUInt32BE(20)];
  if (w !== width || h !== height) throw new Error(`${out}: rendered ${w}x${h}, expected ${width}x${height}`);
  if (png.length >= 1_000_000) throw new Error(`${out}: ${png.length} bytes — over GitHub's 1 MB limit`);
  const chunks = new Set();
  for (let i = 8; i < png.length; i += 12 + png.readUInt32BE(i)) {
    chunks.add(png.toString('latin1', i + 4, i + 8));
  }
  const metadata = [...chunks].filter((c) => ['tEXt', 'iTXt', 'zTXt', 'eXIf', 'tIME'].includes(c));
  if (metadata.length) throw new Error(`${out}: carries metadata chunks ${metadata.join(', ')}`);
  return png.length;
}

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
for (const { width, height, out } of TARGETS) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  await page.setContent(html(width, height, fontFace), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  // Auto-fit: a re-branded name or tagline (BRAND_*) is arbitrary text, so every
  // single-line row is shrunk until it fits its column instead of bleeding
  // through the terminal frame. No-op for text that already fits.
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('.fit')) {
      const limit = el.parentElement.clientWidth - 2;
      for (let size = parseFloat(getComputedStyle(el).fontSize); el.scrollWidth > limit; size -= 1) {
        el.style.fontSize = `${size}px`;
      }
    }
  });
  await mkdir(dirname(out), { recursive: true });
  await page.screenshot({ path: out, type: 'png' });
  await page.close();
  console.log(`wrote ${out} (${width}x${height}, ${await assertClean(out, width, height)} bytes)`);
}

// Legibility evidence (#311): the social preview as a link-unfurl thumbnail.
// Produced by DOWNSCALING the real PNG — which is what Slack/X/GitHub do — and
// not by re-laying-out at a small size, which would flatter the design.
const THUMB = { width: 320, height: 160, out: join(REPO, 'docs', 'assets', 'social-preview-thumbnail.png') };
const source = (await readFile(TARGETS[0].out)).toString('base64');
const thumbPage = await browser.newPage({
  viewport: { width: THUMB.width, height: THUMB.height },
  deviceScaleFactor: 1,
});
await thumbPage.setContent(
  `<body style="margin:0"><img src="data:image/png;base64,${source}" width="${THUMB.width}" height="${THUMB.height}"></body>`,
  { waitUntil: 'load' },
);
await thumbPage.screenshot({ path: THUMB.out, type: 'png' });
await thumbPage.close();
console.log(
  `wrote ${THUMB.out} (${THUMB.width}x${THUMB.height}, ${await assertClean(THUMB.out, THUMB.width, THUMB.height)} bytes)`,
);

await browser.close();
