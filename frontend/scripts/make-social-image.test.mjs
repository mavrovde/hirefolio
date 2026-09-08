#!/usr/bin/env node
/**
 * Self-test for make-social-image.mjs (#311, added per the PR #320 review — same
 * precedent as check-cd-safety.test.mjs beside it: hand-rolled parsers and
 * hand-rolled loops need their own pins).
 *
 * Deliberately BROWSERLESS and offline: it runs in the `npm run lint` gate,
 * which installs no Playwright browsers and has no business fetching a font. The
 * three things the review asked to pin are all reachable that way, because the
 * generator's logic is exported as DOM-free functions:
 *   1. the PNG assertions fire (dimensions / size ceiling / chunk allowlist);
 *   2. the auto-fit loop is BOUNDED and throws instead of hanging;
 *   3. font validation rejects a bad response before it can poison the cache.
 * Exits non-zero on any regression.
 */
import { deflateSync, crc32 } from 'node:zlib';
import { createHash, randomBytes } from 'node:crypto';
import {
  ALLOWED_PNG_CHUNKS,
  MAX_BYTES,
  MIN_FIT_RATIO,
  VT323_SHA256,
  assertCleanPng,
  shrinkToFit,
  verifyFont,
} from './make-social-image.mjs';

let fails = 0;
const check = (desc, ok, detail = '') => {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${desc}${ok || !detail ? '' : ` — ${detail}`}`);
  if (!ok) fails += 1;
};

/**
 * A regression in the fit loop HANGS rather than fails, which would stall the
 * lint gate instead of reporting. Every fit case runs under a deadline so the
 * failure mode is a legible message, not a timed-out CI job.
 */
const withDeadline = (promise, ms, desc) =>
  Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${desc} did not finish within ${ms}ms — the loop is unbounded again`)), ms),
    ),
  ]);

/** Assert `fn` throws, and that the message says WHICH problem it is. */
async function throwsWith(desc, fn, needle) {
  try {
    await fn();
    check(desc, false, 'did not throw');
  } catch (error) {
    check(desc, error.message.includes(needle), `message was: ${error.message}`);
  }
}

// --- PNG fixtures ----------------------------------------------------------
const chunk = (type, data = Buffer.alloc(0)) => {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'latin1'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body) >>> 0);
  return Buffer.concat([length, body, crc]);
};

const ihdr = (width, height) => {
  const data = Buffer.alloc(13);
  data.writeUInt32BE(width, 0);
  data.writeUInt32BE(height, 4);
  data.set([8, 2, 0, 0, 0], 8); // 8-bit RGB, as Chromium writes
  return chunk('IHDR', data);
};

const png = (width, height, { extra = [], pixels = 64 } = {}) =>
  Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    ihdr(width, height),
    ...extra,
    chunk('IDAT', deflateSync(Buffer.alloc(pixels))),
    chunk('IEND'),
  ]);

// --- 1. the PNG assertions -------------------------------------------------
check(
  'a clean PNG of the expected size passes and returns its byte length',
  assertCleanPng(png(1280, 640), { width: 1280, height: 640 }) === png(1280, 640).length,
);
await throwsWith(
  'wrong dimensions throw, naming both',
  () => assertCleanPng(png(1200, 630), { width: 1280, height: 640 }),
  'rendered 1200x630, expected 1280x640',
);
await throwsWith(
  `a file at or over the ${MAX_BYTES}-byte ceiling throws`,
  // Incompressible payload, so the fixture really is oversized on disk.
  () =>
    assertCleanPng(png(1280, 640, { pixels: 0, extra: [chunk('IDAT', randomBytes(MAX_BYTES))] }), {
      width: 1280,
      height: 640,
    }),
  "over GitHub's",
);
await throwsWith(
  'a tEXt metadata chunk throws (the PII case check_no_pii.sh cannot see)',
  () =>
    assertCleanPng(png(1280, 640, { extra: [chunk('tEXt', Buffer.from('Author\0somebody'))] }), {
      width: 1280,
      height: 640,
    }),
  'tEXt',
);
await throwsWith(
  'an UNKNOWN ancillary chunk throws too — allowlist, not denylist',
  () =>
    assertCleanPng(png(1280, 640, { extra: [chunk('gAMA', Buffer.alloc(4))] }), {
      width: 1280,
      height: 640,
    }),
  'gAMA',
);
check(
  'the allowlist stays minimal (no text-bearing chunk was ever added to it)',
  !ALLOWED_PNG_CHUNKS.some((c) => ['tEXt', 'iTXt', 'zTXt', 'eXIf'].includes(c)),
  ALLOWED_PNG_CHUNKS.join(','),
);

// --- 2. the auto-fit loop is bounded --------------------------------------
/**
 * A fake row: `slope` px of width per px of font size, plus `fixed` px that no
 * font size can shrink (letter-spacing, flex gaps — the real hang's cause).
 */
const fakeRow = (field, { size = 30, limit = 300, slope = 12, fixed = 0 } = {}) => {
  const row = {
    field,
    calls: 0,
    current: size,
    fontSize: async () => size,
    setFontSize: async (px) => {
      row.calls += 1;
      row.current = px;
    },
    // Yield to the macrotask queue so the deadline timer above can actually
    // fire; a pure-microtask loop would starve it.
    // Width saturates at the fixed part: a glyph cannot be narrower than 0, and
    // letter-spacing/gaps do not shrink with font size. Modelling that is what
    // makes the un-shrinkable case genuinely un-shrinkable.
    overflow: async () => {
      await new Promise(setImmediate);
      return Math.max(0, row.current) * slope + fixed - limit;
    },
  };
  return row;
};

const fits = fakeRow('BRAND_TAGLINE', { size: 30, limit: 300, slope: 12 });
check(
  'a shrinkable row is reduced until it fits, and the final size is returned',
  (await withDeadline(shrinkToFit(fits), 5000, 'shrinkToFit(shrinkable)')) === 25 &&
    (await fits.overflow()) <= 0,
  `size=${fits.current} overflow=${await fits.overflow()}`,
);

const alreadyFits = fakeRow('BRAND_URL', { size: 30, limit: 1000, slope: 12 });
check(
  'a row that already fits is left completely alone',
  (await shrinkToFit(alreadyFits)) === 30 && alreadyFits.calls === 0,
);

// The regression this whole section exists for: un-shrinkable row => the first
// implementation looped forever (reviewer's watchdog killed it at exit 142).
const stuck = fakeRow('BRAND_NAME', { size: 100, limit: 300, slope: 1, fixed: 900 });
await throwsWith(
  'an UN-SHRINKABLE row throws instead of hanging, naming the BRAND_* field',
  () => withDeadline(shrinkToFit(stuck), 5000, 'shrinkToFit(un-shrinkable)'),
  'BRAND_NAME',
);
check(
  'and it gave up after a bounded number of steps (no runaway loop)',
  stuck.calls > 0 && stuck.calls <= 100 - Math.ceil(100 * MIN_FIT_RATIO),
  `${stuck.calls} steps`,
);
check(
  'the bound is the documented floor: it never shrinks past MIN_FIT_RATIO',
  stuck.current === Math.ceil(100 * MIN_FIT_RATIO),
  `stopped at ${stuck.current}px`,
);

// --- 3. font validation ----------------------------------------------------
const realFont = Buffer.concat([Buffer.from('wOF2', 'latin1'), randomBytes(64)]);
const realHash = createHash('sha256').update(realFont).digest('hex');
check(
  'a woff2 whose hash matches the pin is accepted',
  verifyFont(realFont, realHash) === realFont,
);
await throwsWith(
  'an HTML error page served as a font is rejected (the cache-poisoning case)',
  () => verifyFont(Buffer.from('<!doctype html><title>429</title>', 'latin1')),
  'not a woff2 file',
);
await throwsWith(
  'a truncated response is rejected',
  () => verifyFont(Buffer.from('wO', 'latin1')),
  'not a woff2 file',
);
await throwsWith(
  'a real woff2 that is NOT the pinned revision is rejected',
  () => verifyFont(realFont),
  'does not match the pinned',
);
check(
  'the pin is a full sha256 hex digest',
  /^[0-9a-f]{64}$/.test(VT323_SHA256),
  VT323_SHA256,
);

if (fails) {
  console.error(`\n${fails} make-social-image self-test case(s) FAILED.`);
  process.exit(1);
}
console.log('All make-social-image self-test cases passed.');
