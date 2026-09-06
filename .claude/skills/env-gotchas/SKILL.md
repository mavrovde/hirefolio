---
name: env-gotchas
description: >-
  Environment and tooling pitfalls specific to this repo's dev machines (macOS/BSD userland) and
  GitHub setup — macOS has no `timeout`, BSD grep/sed differences, the same-identity
  `gh pr review --approve` block, zsh vs CI-bash differences, and the shared local test-DB rules.
  Consult when writing shell commands meant to run on both a dev Mac and Linux CI, or when a
  gh/git command behaves differently than expected.
---

# Environment gotchas (#119)

Facts about THIS repo's environments that keep costing cycles. Check here before blaming the code.

## macOS / BSD userland (dev machines) vs GNU (CI runners)
- **No `timeout`(1).** Stock macOS ships neither `timeout` nor `gtimeout` (coreutils not installed
  by default). Scripts that need it must guard (`command -v timeout || …`) or use a
  bash-native bound. Anything you *test* with `timeout` locally silently means "the binary was
  missing" — verify the command actually ran (proven live in #225's execution checks: every shape
  but `timeout …` produced its artifact).
- **BSD `grep`/`sed`.** Alternation and `+`/`?` need `-E`; `sed -i` requires
  an explicit backup suffix argument (`sed -i '' 's/…/…/'`) where GNU sed takes bare `-i`; `\b` word
  boundaries are unreliable — use `(^|[^A-Za-z0-9_])` classes. `cat -A` does not exist (use
  `LC_ALL=C od -c` or `cat -evt`). **Watch WHICH grep you test with** (#231 review): on this machine
  the PATH `grep` is ugrep (accepts `-P` and `\b`) while `/usr/bin/grep` is BSD grep (rejects
  both) — a `-P` pattern that passes interactively breaks in scripts/hooks/CI that resolve the
  system grep. `**` globs need bash `globstar` (off by default) — prefer `find`.
- **`date`**: BSD `date` has no `date -d`; use `date -v-1d` forms or python.
- **zsh is the interactive shell**; CI and hooks run bash. `echo ===` in zsh can trigger
  `== not found` (zsh treats `=cmd` as a path expansion); `setopt`-dependent behavior and word
  splitting differ — write scripts for bash, run them with `bash`, don't paste bash-isms into zsh.
- **Sourcing `.env` in zsh** executes unquoted lines that look like commands — prefer
  `set -a; source .env; set +a` and expect noise from bare-word values, or read single vars with
  `grep '^VAR=' .env`.

## GitHub / gh
- **Same-identity approval is blocked**: `gh pr review --approve` on your own PR fails. The
  pr-reviewer posts a clear **COMMENT verdict** (`gh pr review --comment` / `gh pr comment`) — that
  counts as the rule-13 verdict; never work around the block.
- **`gh release create` needs the FULL commit sha** for `--target`, not an abbreviation.
- **A green run ≠ rolled out**: the `Roll Out To Prod Host` job and even its gate step report
  `success` when rollout is disabled — the tell is the gated steps being `skipped` (see
  `/deploy-status`, #120).
- **Repo renames don't move GHCR packages** (lessons-learned §20): container packages keep the old
  visibility/links until touched.

## Local test databases (shared state)
- Backend pytest needs `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/test_mavrov`
  and `HIREFOLIO_GEMINI_API_KEY=""` — without it the suite hangs on (or would wipe) the live dev DB.
- **One suite at a time** on `test_mavrov` (`pgrep -f pytest` first) — two runs clobber each other
  into dozens of spurious failures (lessons-learned §4).
- `seed_e2e_user.py` **obliterates all users and posts** in whatever DB it points at — only ever run
  it in-container against an E2E stack, never against the dev DB.

## Hooks
- The pre-push hook runs the full docs+backend+frontend gate on every `git push` — from worktrees
  too (symlink `backend/venv` + `frontend/node_modules` into a fresh worktree or the backend leg
  cannot run). Legs are env-configurable (`PREPUSH_RUN_*`) — configure, don't `--no-verify`.
- The destruction guard (rule 9) inspects every Bash tool call; oversized commands (>24 KB, or
  analysis past its deadline) are DENIED by design — split the command or write content to a file
  first, don't reach for `GUARD_DESTRUCTIVE=0`.
