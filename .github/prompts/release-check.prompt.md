---
mode: agent
description: Pre-release checklist — SemVer by content, changelog rotation, gates, and the published-vs-live doctrine
---

Prepare and check a release of mavrov.de (see `.claude/commands/release.md` for the full runbook;
`CLAUDE.md` rule 8 governs). Do not take irreversible steps (merge to `main`, tag push) without
explicit user go-ahead.

1. **SemVer by content** of `CHANGELOG.md` `[Unreleased]` — never by reflex:
   major = breaking change; minor = a genuine `### Added` user-facing feature; patch = everything
   else (dependency bumps, fixes, refactors, docs, tooling).
2. **Version set**: `VERSION`, `backend/app/main.py`, `frontend/package.json` (+ shared),
   `frontend/projects/public/src/app/version.ts`, and the `docker-compose.prod.yml` image tags —
   all must match. Rotate `[Unreleased]` into `[X.Y.Z] - YYYY-MM-DD` (real date), add a fresh
   `[Unreleased]` stub, no duplicate headers.
3. **Gates**: full local suite green (backend ruff/format + mypy + bandit + pytest at 100%,
   frontend test:coverage + build, Docker E2E). Check `pgrep -f pytest` before any pytest run.
4. **PR-based release**: bump on a feature branch → PR → independent review verdict → merge to
   `main` (the sanctioned prod trigger). Never push the release directly to `main`.
5. **Babysit `deploy.yml`** to green end-to-end; fix forward on red. Only then tag `vX.Y.Z` on the
   merge commit (full SHA) and publish the GitHub Release.
6. **Published ≠ live (#112/#156)**: a green pipeline publishes images but does NOT roll the prod
   host. The rollout (`docker compose -f docker-compose.prod.yml up -d` on the host) is a separate
   required step — verify the live site shows the new version before claiming the release is live.
7. **Security check every release**: review open CodeQL + Dependabot alerts, triage each, and
   confirm alerts the release fixed now show `fixed`.
