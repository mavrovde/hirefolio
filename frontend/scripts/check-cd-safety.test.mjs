#!/usr/bin/env node
/**
 * Self-test for check-cd-safety.mjs (#118, added per the #233 review — a
 * hand-rolled parser needs its own pins, same precedent as
 * .claude/hooks/guard-destructive.test.sh). Each case is a fixture file the
 * checker scans via CD_SAFETY_SCAN_ROOT; expectation is flag / no-flag.
 * Exits non-zero on any regression.
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const CHECKER = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "check-cd-safety.mjs",
);

const CASES = [
  ["flags subscribe-and-assign (the #94 class)", true, `
    this.svc.data$.subscribe((v) => {
      this.value = v;
    });`],
  ["flags setInterval-and-assign", true, `
    setInterval(() => { this.uptime = Date.now() - this.start; }, 1000);`],
  ["flags .then-and-assign", true, `
    fetch('/api').then((r) => { this.result = r; });`],
  ["comment PROSE mentioning markForCheck( does NOT satisfy the repaint rule", true, `
    this.svc.data$.subscribe((v) => {
      // the fallback path repaints via markForCheck( elsewhere
      this.value = v;
    });`],
  ["markForCheck in the callback passes", false, `
    this.svc.data$.subscribe((v) => {
      this.value = v;
      this.cdr.markForCheck();
    });`],
  ["signal writes pass", false, `
    this.svc.data$.subscribe((v) => { this.value.set(v); });`],
  ["cd-safety-ok marker suppresses (with reason)", false, `
    this.svc.data$.subscribe((v) => {
      // cd-safety-ok: SSR-only path, browser branch returns earlier
      this.value = v;
    });`],
  ["no assignment, no flag", false, `
    this.svc.data$.subscribe((v) => { console.log(v); });`],
  ["local (non-this) assignment passes", false, `
    this.svc.data$.subscribe((v) => { const x = v; use(x); });`],
];

let fails = 0;
for (const [desc, expectFlag, snippet] of CASES) {
  const dir = mkdtempSync(join(tmpdir(), "cdsafety-"));
  mkdirSync(join(dir, "app"), { recursive: true });
  writeFileSync(
    join(dir, "app", "fixture.component.ts"),
    `export class Fixture {\n  run() {${snippet}\n  }\n}\n`,
  );
  let flagged = false;
  try {
    execFileSync(process.execPath, [CHECKER], {
      env: { ...process.env, CD_SAFETY_SCAN_ROOT: dir },
      stdio: "pipe",
    });
  } catch {
    flagged = true;
  }
  rmSync(dir, { recursive: true, force: true });
  if (flagged === expectFlag) {
    console.log(`PASS  [${flagged ? "flag" : "ok"}]  ${desc}`);
  } else {
    console.error(`FAIL  got=${flagged ? "flag" : "ok"} want=${expectFlag ? "flag" : "ok"}  ${desc}`);
    fails++;
  }
}

if (fails) {
  console.error(`\n${fails} cd-safety self-test case(s) FAILED.`);
  process.exit(1);
}
console.log("All cd-safety self-test cases passed.");
