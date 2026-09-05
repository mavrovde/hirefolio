---
description: Pre-PR hygiene gate — stale-main, CHANGELOG duplicates, stale old-behavior assertions, issue links, gates summary
---

Run the pre-PR hygiene checks on the CURRENT branch and report a pass/fail table. These encode the
mechanical mistakes that have cost real red deploys (#103/#104 changelog duplicate; #108→#110 stale
E2E assertion). Consult the `env-gotchas` skill for platform pitfalls while running these.

1. **Stale main.** `git fetch origin main` then `git merge-base --is-ancestor origin/main HEAD`.
   If not, FLAG: the branch is behind `origin/main` — rebase (or merge main) before opening the PR;
   branching off stale main is how duplicate CHANGELOG sections happen.
2. **CHANGELOG hygiene.** Exactly ONE `## [Unreleased]` block
   (`grep -c '^## \[Unreleased\]' CHANGELOG.md` → 1), no duplicated `### Added/Changed/Fixed`
   headers within it, and the block actually mentions this branch's change. FLAG any duplicate
   section (the #103/#104 failure).
3. **Stale old-behavior assertions.** If the diff changes user-visible behavior, grep the WHOLE
   relevant spec tree (`frontend/e2e`, `frontend/projects/*/src/**/*.spec.ts`, `backend/tests`) for
   assertions on the OLD behavior — search for the old strings/routes/status codes the diff removes
   (e.g. `toHaveURL('/')` when a redirect becomes a panel — the exact #108 miss that failed the
   deploy E2E). List every hit and check each is updated in this branch.
4. **Issue linkage.** The intended PR body has `Closes #NN`/`Refs #NN` for every issue the branch
   addresses, and each linked issue's acceptance criteria are answerable from the diff (rule: PRs
   link issues; issues have criteria).
5. **Gates summary.** Report the state of the local gates for this diff (what ran, what passed):
   backend ruff/mypy/pytest, frontend project tests, and whether the change class requires the full
   Docker E2E (`/e2e`) before merge (any SSR/HTTP/transfer-cache/zoneless change does —
   lessons-learned §3).
6. **Secrets.** `git diff origin/main... | grep -iE 'password|secret|token|api_key'` — every hit
   must be a variable NAME or placeholder, never a value (public repo, no-secrets rule).

Output: a table of check → PASS/FLAG with one line each on what to fix. Do NOT push or open the PR
from this command; it prepares, the human/agent decides. $ARGUMENTS
