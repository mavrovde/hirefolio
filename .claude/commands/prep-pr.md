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
4. **Issue linkage and the `Closes`/`Refs` decision.** For every issue the branch addresses, run
   `gh issue view NN --json body` and READ the acceptance-criteria checkboxes. `Closes #NN` only if
   every box is ticked and you can say what you ran for each; otherwise `Refs #NN` and name the
   unmet criterion in the PR. A `Closes` against an unticked box was a blocker in four v1.12.0 PRs
   and is now refused at merge by `.claude/hooks/pre-merge-gate.sh`. The intended PR body has
   `Closes #NN`/`Refs #NN` for every issue the branch addresses, and each linked issue's acceptance criteria are answerable from the diff (rule: PRs
   link issues; issues have criteria).
5. **Gates summary.** Report the state of the local gates for this diff (what ran, what passed):
   backend ruff/mypy/pytest, frontend project tests, and whether the change class requires the full
   Docker E2E (`/e2e`) before merge (any SSR/HTTP/transfer-cache/zoneless change does —
   lessons-learned §3).
6. **Secrets.** `git diff origin/main... | grep -iE 'password|secret|token|api_key'` — every hit
   must be a variable NAME or placeholder, never a value (public repo, no-secrets rule).

7. **Re-measure every number.** List every count or claim in the PR body, the commit message and the
   `[Unreleased]` CHANGELOG block — "N tests", "N cases", "N passed", "grep returns nothing", "X is
   fixed" — then RUN the thing that produces each one, AT THIS HEAD, and correct it. This is the
   single most frequent review finding in the repo's history: **all 14 v1.12.0 PRs carried at least
   one claim that did not reproduce, nine at blocker level** (15→18, 43/320→44/332, 13→12, "0 stale
   hits"→2, "2280 samples / 0 errors"→2160 with 20 real failures, and a "grep returns nothing" that
   returned 41 hits). Numbers quoted from an earlier head are the commonest form.
   `pytest --collect-only -q` and `npx playwright test --list` settle most of them.
8. **Layer evidence (rule 12).** For each layer that can see this change's failure mode, state what
   you ran and what it printed: backend `pytest -n auto --cov-fail-under=100`; the three Vitest
   projects; `./verify_all.sh` or `/e2e` for a user-facing surface; `./run_integration_tests.sh` for
   a composed API/AI path. `deploy.yml` gates E2E and the integration tier on `push`, so PR CI shows
   them `skipping` — a LOCAL run is the only pre-merge evidence, and all 14 merged v1.12.0 PRs
   closed with the reviewer noting its absence. Name any layer that does not apply, and why.


Output: a table of check → PASS/FLAG with one line each on what to fix. Do NOT push or open the PR from this command; it prepares, the human/agent decides. $ARGUMENTS
