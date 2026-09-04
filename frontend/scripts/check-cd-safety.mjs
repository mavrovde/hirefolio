#!/usr/bin/env node
/**
 * cd-safety lint (#118): flag the imperative subscribe-and-assign anti-pattern
 * in the ZONELESS public app.
 *
 * The public app ships no zone.js (provideZonelessChangeDetection, #105), so a
 * component property assigned inside a subscribe/setInterval/setTimeout
 * callback renders once and then silently never repaints — the exact class
 * behind #94 (footer frozen at "BE: vUnknown" while the fetch returned 200).
 * Unit tests bundle zone.js and therefore CANNOT catch it; only the browser /
 * Docker E2E can. This check catches it at authoring time instead.
 *
 * Heuristic, deliberately dependency-free (the workspace has no ESLint today —
 * adopting angular-eslint is a separate, deliberate effort per the dependency
 * policy; tracked as a follow-up). It flags a callback of subscribe( /
 * setInterval( / setTimeout( that assigns `this.<prop> = …` when the callback
 * body contains no markForCheck( and the assignment is not a signal update
 * (.set( / .update(). Suppress a justified case with a
 * `// cd-safety-ok: <reason>` comment on the assignment's line or the line
 * above it — the reason is required reading for the reviewer.
 *
 * Scope: projects/public runtime sources only. The admin app is zone-based CSR
 * and the shared lib is consumed by both; neither has the zoneless footgun.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const SCAN_ROOT = join(ROOT, "projects", "public", "src");

const TRIGGERS = /\.(subscribe)\s*\(|(?<![.\w])(setInterval|setTimeout)\s*\(/g;
const ASSIGN = /this\.[A-Za-z_$][\w$]*(?:\.[\w$]+)*\s*=(?![=>])/;
const REPAINT = /markForCheck\s*\(|detectChanges\s*\(/;
const SIGNAL_WRITE = /this\.[A-Za-z_$][\w$]*\.(set|update)\s*\(/;
const SUPPRESS = /cd-safety-ok:/;

function* tsFiles(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* tsFiles(p);
    else if (
      name.endsWith(".ts") &&
      !name.endsWith(".spec.ts") &&
      !name.endsWith(".server.ts")
    )
      yield p;
  }
}

/** Extract the balanced-paren argument span starting at openParen index. */
function argSpan(src, openParen) {
  let depth = 0;
  for (let i = openParen; i < src.length; i++) {
    const c = src[i];
    if (c === "(") depth++;
    else if (c === ")" && --depth === 0) return src.slice(openParen, i + 1);
  }
  return src.slice(openParen);
}

const violations = [];
for (const file of tsFiles(SCAN_ROOT)) {
  const src = readFileSync(file, "utf8");
  const lines = src.split("\n");
  let m;
  TRIGGERS.lastIndex = 0;
  while ((m = TRIGGERS.exec(src))) {
    const open = src.indexOf("(", m.index + m[0].length - 1);
    if (open < 0) continue;
    const body = argSpan(src, open);
    if (!ASSIGN.test(body)) continue;
    if (REPAINT.test(body)) continue;
    // A callback that only writes signals repaints by definition.
    const nonSignalAssigns = body
      .split("\n")
      .filter((l) => ASSIGN.test(l) && !SIGNAL_WRITE.test(l));
    if (nonSignalAssigns.length === 0) continue;
    const line = src.slice(0, m.index).split("\n").length;
    const suppressed =
      SUPPRESS.test(lines[line - 2] ?? "") ||
      body.split("\n").some((l) => ASSIGN.test(l) && SUPPRESS.test(l)) ||
      body
        .split("\n")
        .some(
          (l, i, arr) => ASSIGN.test(l) && SUPPRESS.test(arr[i - 1] ?? ""),
        );
    if (suppressed) continue;
    violations.push(
      `${relative(ROOT, file)}:${line}  ${m[0].trim()}…) assigns this.* with no markForCheck/signal — zoneless app never repaints (#94/#118). Use the async pipe, a signal, or ChangeDetectorRef.markForCheck(); or add "// cd-safety-ok: <reason>".`,
    );
  }
}

if (violations.length) {
  console.error("cd-safety: FAIL — zoneless repaint hazards in projects/public\n");
  for (const v of violations) console.error("  " + v);
  console.error(`\n${violations.length} violation(s).`);
  process.exit(1);
}
console.log("cd-safety: OK (projects/public imperative-callback assignments all have a repaint path)");
