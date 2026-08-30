# Frontend — Angular workspace

Angular 22 workspace (Angular CLI `^22.1.4`) with **three projects**:

| Project | Path | What it is |
| --- | --- | --- |
| `public` | `projects/public` | Visitor-facing app with **native SSR** (`server.ts` → `dist/public/server/server.mjs`), zoneless change detection |
| `admin` | `projects/admin` | Admin console — client-side-rendered SPA |
| `shared` | `projects/shared` | `@mavrov/shared` library consumed by both apps (build it **first**) |

The apps consume `@mavrov/shared` via the `SHARED_ENVIRONMENT` and
`AUTH_TOKEN_PROVIDER` injection tokens (public passes a null token provider;
admin wires it to its `AuthService`).

## Development servers

```bash
npm start            # public app  -> http://localhost:4200
npm run start:admin  # admin app   -> http://localhost:4300
```

## Building

`shared` must be built before either app; the aggregate script handles the order:

```bash
npm run build          # shared -> public -> admin
npm run build:shared   # or build one project
npm run build:public
npm run build:admin

npm run serve:ssr:public   # run the built SSR server (dist/public/server/server.mjs)
```

## Unit tests (Vitest)

Unit tests run with [Vitest](https://vitest.dev/) (not Karma/Jasmine), one
config per project. Coverage is **enforced at 100%** (statements, branches,
functions, lines) for each project.

```bash
npm test                   # all three projects (shared, public, admin)
npm run test:shared        # one project
npm run test:public
npm run test:admin

npm run test:coverage      # all three, with coverage (the CI gate)
npm run test:coverage:public   # per-project coverage
```

To run a single spec file, pass the project's config explicitly:

```bash
npx vitest run --config projects/public/vitest.config.ts src/app/services/api.service.spec.ts
```

## End-to-end tests (Playwright)

Playwright **is** configured (`playwright.config.ts`) with two projects:

- `public-e2e` — tests in `e2e/public` against the public app
- `admin-e2e` — tests in `e2e/admin` against the admin app

```bash
npm run e2e                                # everything
npx playwright test --project=public-e2e   # one suite
npx playwright test --project=admin-e2e
```

The full-stack E2E run (real backend + DB + Ollama) is driven by the repo-root
`./verify_all.sh` / the Docker compose E2E stack — see the root `README.md`
and `README_TESTING.md`.

## Environments

Per-app environment files live at `projects/public/src/environments/` and
`projects/admin/src/environments/`.

## Additional resources

Project conventions (RxJS-first state, SSR safety, zoneless change-detection
gotchas) are documented in the repo-root `CLAUDE.md` and
`.claude/skills/lessons-learned/`. For Angular CLI reference, see the
[Angular CLI Overview](https://angular.dev/tools/cli).
