import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

/**
 * Regression guard for the jsdom 30 -> undici 8 coupling (PR #149).
 *
 * jsdom's resource loader is built on an undici `Dispatcher`
 * (`jsdom/lib/jsdom/browser/resources/jsdom-dispatcher.js` -> `fetchCollected`,
 * consumed by `per-document-resource-loader.js`). jsdom 30 was rewritten for
 * undici 8's module layout, so pinning/overriding `undici` back to 7 (leftover
 * jsdom-29 scaffolding) reintroduces the "Cannot find module .../jsdom-dispatcher"
 * class of failure — invisible to the rest of the suite because Angular specs
 * mock `HttpBackend` and never exercise jsdom's undici-backed loader.
 *
 * We assert the resolved undici major, and drive the real loader in a child Node
 * process (jsdom pulls a mixed CJS/ESM dep graph that vitest's transform can't
 * bundle; a plain Node process loads it exactly as the toolchain does). A `data:`
 * subresource travels the same `fetchCollected` -> undici `Dispatcher` path as an
 * http(s) resource but resolves locally, so no real network / paid service is hit.
 */
const nodeRequire = createRequire(import.meta.url);
// frontend workspace root (…/projects/shared/src -> …/frontend), which owns the
// single node_modules tree the whole workspace resolves against.
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');

function resolvedUndiciMajor(): number {
  // `.resolve` only computes paths — it never executes jsdom's runtime graph,
  // so it is safe to call from inside vitest's transform pipeline.
  const jsdomEntry = nodeRequire.resolve('jsdom');
  const undiciPkgPath = nodeRequire.resolve('undici/package.json', {
    paths: [jsdomEntry],
  });
  const { version } = nodeRequire(undiciPkgPath) as { version: string };
  return Number(version.split('.')[0]);
}

describe('jsdom 30 resource loader is backed by undici 8', () => {
  it('resolves undici >= 8 from jsdom (matching the jsdom 30 module layout)', () => {
    const major = resolvedUndiciMajor();

    expect(Number.isNaN(major)).toBe(false);
    expect(major).toBeGreaterThanOrEqual(8);
  });

  it('loads an external subresource through the undici-backed dispatcher (no network)', () => {
    const driver = `
      const { JSDOM } = require('jsdom');
      const undiciPkg = require.resolve('undici/package.json', {
        paths: [require.resolve('jsdom')],
      });
      const undiciVersion = require(undiciPkg).version;
      const scriptSrc =
        'data:text/javascript;base64,' +
        Buffer.from('window.__undiciResourceLoaded = true;').toString('base64');
      const html =
        '<!DOCTYPE html><html><head><script src="' + scriptSrc + '"></' +
        'script></head><body></body></html>';
      const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        resources: 'usable',
        url: 'https://jsdom.test/',
      });
      const deadline = Date.now() + 8000;
      (function poll() {
        if (dom.window.__undiciResourceLoaded) {
          process.stdout.write('UNDICI_RESOURCE_OK ' + undiciVersion);
          process.exit(0);
        }
        if (Date.now() > deadline) {
          process.stderr.write('TIMEOUT loading subresource');
          process.exit(2);
        }
        setTimeout(poll, 25);
      })();
    `;

    const output = execFileSync(process.execPath, ['-e', driver], {
      cwd: frontendRoot,
      encoding: 'utf8',
      timeout: 20000,
    }).trim();

    expect(output).toMatch(/^UNDICI_RESOURCE_OK /);
    const reportedUndiciMajor = Number(output.split(' ')[1].split('.')[0]);
    expect(reportedUndiciMajor).toBeGreaterThanOrEqual(8);
  });
});
