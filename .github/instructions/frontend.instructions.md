---
applyTo: "frontend/**"
---

# Frontend (Angular 22 workspace)

- Three projects under `frontend/projects/`: `public` (SSR visitor app), `admin` (CSR-only SPA),
  `shared` (`@mavrov/shared` ng-packagr lib). Standalone components, native SSR, TailwindCSS 4.
- Apps consume shared code via the `SHARED_ENVIRONMENT` + `AUTH_TOKEN_PROVIDER` injection tokens
  (public passes a null token; admin wires it to `AuthService`).
- **State is RxJS Observables rendered with the `async` pipe** (compose with
  `switchMap`/`catchError`/`shareReplay`). Signals only sparingly for local component state.
  Do NOT refactor RxJS code to signals; RxJS is the primary mechanism here by design.
- **Explicit TypeScript interfaces mirroring backend Pydantic models — no `any`.**
- Components stay dumb; logic lives in injected services. No raw `fetch`/`HttpClient` in components.

## Zoneless & SSR traps (unit tests hide these; only the Docker E2E catches them)

- **Both browser apps are zoneless** (no zone.js at runtime) — public explicitly
  (`provideZonelessChangeDetection()`, #105) and admin by default (no `polyfills` entry in
  `angular.json`, so Angular's `ZONELESS_ENABLED` default applies, #276). Mutating a plain property
  inside `subscribe`/`setInterval`/`setTimeout` will silently never repaint. Use the `async` pipe,
  signals, or inject `ChangeDetectorRef` + `markForCheck()` after each async mutation.
- Guard all DOM access (`window`, `document`, `localStorage`) with `isPlatformBrowser()`.
- The SSR relative→absolute URL rewrite lives in `SsrHttpBackend` (an `HttpBackend`, terminal in
  the chain) delegating to `HttpXhrBackend`. Never move it into an interceptor (breaks
  transfer-cache keying) and never delegate to `FetchBackend` (reverted once already).
- Any change to SSR/HTTP wiring, interceptors, or transfer cache must be validated against the
  full Docker E2E before merge — PR CI runs CodeQL only.
- When changing user-visible behavior, grep ALL e2e specs for assertions on the OLD behavior;
  a stale sibling spec will pass PR CI and fail the deploy E2E.
- `@angular/*` framework packages pin exact peer versions: update every `@angular/*` dep and
  devDep in one pass; if resolution still fails, regenerate the lockfile from ranges.

## Tests & gates (all must pass before a PR)

- `npm run test:coverage` — **100% coverage** (statements/branches/functions/lines) per project.
  Genuinely unreachable branches may use `/* v8 ignore next */`.
- `npm run build` — build `shared` before `public`/`admin`.
- E2E: `npx playwright test` (`public-e2e` on `BASE_URL`, `admin-e2e` on `ADMIN_BASE_URL`).
  Local proxy HTTPS is on host port **10443** (`https://localhost:10443`).
- Never mock-free-call a paid API from a spec — use `page.route` or an empty/dummy credential.
- Never lower coverage thresholds or skip tests. Fix the code.
