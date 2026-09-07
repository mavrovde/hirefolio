#!/usr/bin/env bash
# PII guard (#66/#257) + de-branding guard (#313). Two contracts, one script,
# both wired into the pre-push docs leg and the CI Version Consistency job.
#
# CHECK A — PII: the repo must stay free of the former owner's personal
# identifiers (name, email, LinkedIn handle, GA id). This is the regression gate
# the demo-persona swap was missing ("nothing fails if the PII comes back").
# KNOWN LIMIT: text-only — PII inside binaries (a PDF's FlateDecode streams,
# image EXIF) is invisible to git grep; binary assets need eyeball review.
#
# CHECK B — de-branding (#313, owner directive 2026-09-07 "stop orienting all
# docs to mavrov and mavrov.de, it is an open project"). This REVERSES the
# stance check A used to carry in this very header: `mavrov.de` was excluded
# from the patterns as "a legitimate infra default for the canonical
# deployment". It still is — in infra defaults and history — but NOT in the
# surfaces that instruct a forker or an agent. So the domain is not a global PII
# pattern; it is banned only on CURRENT-GUIDANCE surfaces, and there only when
# it is unannotated.
#
# Scope of check B (the acceptance grep of #313, plus the agent playbook):
#   README.md, docs/ (minus retrospectives/ + agent-runs/), .claude/,
#   .env.example, agents/PLAYBOOK.md
# Deliberately OUT of scope, because the domain legitimately lives there:
#   CHANGELOG.md, docs/retrospectives/, docs/agent-runs/  — immutable history
#   docker-compose*.yml, proxy/entrypoint.sh                — real runtime fallbacks; changing
#                                                             them repoints a live deployment
#   CLAUDE.md, agents/ (A2A roster/README)                  — not de-branded yet; see #313 PR notes
#
# A line inside the scope may keep the domain ONLY if it carries one of three
# annotations, on the SAME line (this is the whole point: an exception must be
# deliberate and visible in the diff, not implicit):
#   * "canonical"  — an explicitly-marked canonical-deployment-instance aside
#   * "historical" — a historical record; either the plain word in prose or a
#                    trailing `<!-- de-brand:historical: … -->` comment, which
#                    annotates an incident narrative WITHOUT rewriting it
#   * ghcr.io/mavrovde/mavrov.de — a pre-rename GHCR image path (#88)
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

PATTERNS='serg\.mavrov|smavrov|sergii|G-1QSMT6N045'

# Allowlist: legal/historical records and the one negative assertion.
#   LICENSE            — the copyright holder is the real author (correct).
#   CHANGELOG.md       — immutable history.
#   specs/done/        — historical spec documents.
#   this script        — carries the patterns.
hits=$(git grep -inE "$PATTERNS" -- . \
  ':(exclude)LICENSE' \
  ':(exclude)CHANGELOG.md' \
  ':(exclude)specs/done/*' \
  ':(exclude)scripts/check_no_pii.sh' \
  2>/dev/null)

rc=0
if [ -n "$hits" ]; then
  echo "✗ PII guard: former-owner identifiers found in tracked files:"
  printf '%s\n' "$hits"
  echo "The repo ships the anonymized demo persona (#66); personal identity"
  echo "belongs in the deployment's .env / uploaded content, never in source."
  rc=1
else
  echo "✓ PII guard: no former-owner identifiers in tracked sources."
fi

# --- CHECK B: no maintainer-domain branding on current-guidance surfaces -----
GUIDANCE_ANNOTATIONS='canonical|historical|ghcr\.io/mavrovde/mavrov\.de'

brand=$(git grep -inE 'mavrov\.de' -- \
  'README.md' 'docs' '.claude' '.env.example' 'agents/PLAYBOOK.md' \
  ':(exclude)docs/retrospectives/*' \
  ':(exclude)docs/agent-runs/*' \
  2>/dev/null | grep -ivE "$GUIDANCE_ANNOTATIONS" || true)

if [ -n "$brand" ]; then
  echo "✗ De-brand guard (#313): the maintainer's domain appears, unannotated, on a"
  echo "  CURRENT-GUIDANCE surface — docs written for whoever deploys Hirefolio:"
  printf '%s\n' "$brand"
  echo "  Fix it one of three ways:"
  echo "    * write the product voice instead — 'Hirefolio', '<your-domain>', 'example.com';"
  echo "    * if it is genuinely the canonical deployment INSTANCE, say so on the line"
  echo "      (the word 'canonical' is the marker) — README keeps exactly one such aside;"
  echo "    * if it is a historical record, annotate WITHOUT rewriting the narrative:"
  echo "      append '<!-- de-brand:historical: … -->' to the line."
  rc=1
else
  echo "✓ De-brand guard: current-guidance surfaces speak in the product's voice."
fi

exit "$rc"
