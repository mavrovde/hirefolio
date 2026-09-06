#!/usr/bin/env bash
# PII guard (#66/#257): the repo must stay free of the former owner's personal
# identifiers — this is the regression gate the demo-persona swap was missing
# ("nothing fails if the PII comes back"). Wired into the pre-push docs leg and
# the CI Version Consistency job, like the other repo-contract self-checks.
#
# Patterns are IDENTIFIERS (name, email, LinkedIn handle, GA id) — deliberately
# NOT the mavrov.de domain, which remains a legitimate infra default for the
# canonical deployment.
set -u
cd "$(dirname "$0")/.."

PATTERNS='serg\.mavrov|smavrov|sergii|G-1QSMT6N045'

# Allowlist: legal/historical records and the one negative assertion.
#   LICENSE            — the copyright holder is the real author (correct).
#   CHANGELOG.md       — immutable history.
#   specs/done/        — historical spec documents.
#   test_email_service — contains an `assert "Sergii" not in …` negative pin.
#   this script        — carries the patterns.
hits=$(git grep -inE "$PATTERNS" -- . \
  ':(exclude)LICENSE' \
  ':(exclude)CHANGELOG.md' \
  ':(exclude)specs/done/*' \
  ':(exclude)backend/tests/test_email_service.py' \
  ':(exclude)scripts/check_no_pii.sh' \
  2>/dev/null)

if [ -n "$hits" ]; then
  echo "✗ PII guard: former-owner identifiers found in tracked files:"
  printf '%s\n' "$hits"
  echo "The repo ships the anonymized demo persona (#66); personal identity"
  echo "belongs in the deployment's .env / uploaded content, never in source."
  exit 1
fi
echo "✓ PII guard: no former-owner identifiers in tracked sources."
