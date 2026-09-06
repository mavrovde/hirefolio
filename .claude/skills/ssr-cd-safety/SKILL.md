---
name: ssr-cd-safety
description: >-
  The SSR + zoneless change-detection contract for frontend/projects/public — the silent-failure
  class unit tests CANNOT catch (they bundle zone.js; the app does not). Consult BEFORE writing or
  reviewing any public-app component that updates from subscribe/setInterval/setTimeout/fetch
  callbacks, and before touching HttpBackend / interceptors / the transfer cache / SSR hydration.
  Encodes: async mutation ⇒ markForCheck | signal | async pipe; SSR URL rewrite lives in an
  HttpBackend delegating to HttpXhrBackend (never FetchBackend); E2E — not unit tests — is the only
  gate that sees violations.
---

# SSR + zoneless CD safety (#118)

The class behind #94 (footer frozen at `BE: vUnknown` while the fetch returned 200) and the #84
revert. Unit tests pass while the browser silently breaks, because `test-setup.ts` bundles
`zone.js` and the shipped app does not.

## The zoneless contract (public app)

`frontend/projects/public/src/app/app.config.ts:23` — `provideZonelessChangeDetection()` (#105).
No `zone.js` at runtime. Therefore **nothing repaints on its own**: change detection runs only for
signals, the `async` pipe, template events, and explicit `markForCheck()`.

**Rule: every async mutation needs an explicit repaint path.** A component property assigned inside
`subscribe(…)`, `setInterval(…)`, `setTimeout(…)`, a promise `.then`, or an `await` continuation
will render **once and never again** unless one of these holds:
1. the value is a **signal** (`this.count.set(...)` / `update`), or
2. the template consumes an **Observable via the `async` pipe** (preferred house style —
   `value$ | async`, composed with `switchMap`/`catchError`/`shareReplay`), or
3. the callback ends with `this.cdr.markForCheck()` (inject `ChangeDetectorRef`; pattern in
   `stats.component.ts`, `blog.component.ts`).

Audit grep (what the reviewer runs): in `projects/public`, find `subscribe(`/`.then(`/
`setInterval(`/`setTimeout(` callbacks that assign `this.<prop> =` with no `markForCheck` in the
same callback and no signal/async-pipe consumption of that property — `npm run lint:cd-safety`
automates exactly this. An `await`-then-assign continuation is the heuristic's known blind spot
(needs the #234 AST lint) — check those by eye.

**Rule (the READ direction, #255): never read an async-populated field synchronously in
`ngOnInit` — compose off the stream.** The mirror image of the repaint rule: a constructor
subscription filling `this.site` looks done by `ngOnInit`, but on SSR the router resolves in a
microtask while the config HTTP response is a macrotask — `ngOnInit` reads the placeholder, bakes
it into interpolated strings (SEO meta, JSON-LD), and NO later re-apply can repair strings already
built. Fix: `config$.pipe(take(1)).subscribe(cfg => updateSeo(...))` so SSR's stability tracking
waits for the value. Unit-pin it with a NOT-yet-emitted `ReplaySubject` (assert nothing applied,
then emit, assert applied) — every eager `of(config)` mock emits during construction and hides the
race, which is why 321 green tests missed it. E2E only asserts the `<title>`, so it can't see a
wrong meta description either — this class is invisible to both gates without that specific pin.

## The SSR HTTP contract

- The SSR relative→absolute URL rewrite lives in a custom **`HttpBackend`**
  (`interceptors/ssr-http-backend.ts`, wired `{provide: HttpBackend, useClass: SsrHttpBackend}`) —
  NOT in an interceptor. An `HttpInterceptorFn` runs before Angular's transfer-cache interceptor,
  so the server would key the cache on the rewritten absolute URL while the browser keys the
  relative one → keys never match → hydration re-fetches everything (#25 "flash to home").
- **Delegate to `HttpXhrBackend`, never `FetchBackend`.** The app has always been XHR on both
  platforms; #84 switched to Fetch, was 100% green in unit tests and review, and deterministically
  broke the browser's only real fetch in the prod E2E across 4 deploy attempts. Only the revert
  greened it.
- Guard all DOM access with `isPlatformBrowser()`.

## Why your tests lie to you

- Unit tests bundle zone.js → the anti-pattern repaints in tests and freezes in production.
- PR CI runs CodeQL only → a violation sails through review.
- **The full Docker E2E is the only automated gate that sees this class** — run it before merging
  any change touching this file's subject matter (`/e2e`, lessons-learned §1–§3). When you change
  user-visible behavior, grep ALL e2e specs for assertions on the OLD behavior (#108→#110).

## When adding a new public component

Default to the house style: expose `Observable` fields consumed with `value$ | async`. Reach for
signals for small local state. If you must assign imperatively in a callback, inject
`ChangeDetectorRef` and `markForCheck()` — and say in the PR why the async pipe didn't fit.
