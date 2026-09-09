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
# Scope of check B — EVERYTHING TRACKED, MINUS an explicit exclusion list.
#
# This is inverted on purpose, and the inversion is the round-2 fix. Rounds 1 and
# 2 of #318 both shipped an INCLUDE list, and both times the reviewer found
# guidance surfaces that were branded or unguarded because nobody had thought to
# add them — round 1: README_TESTING.md, SECURITY.md, the copilot and prompt
# files, importer/README.md; round 2 (positive control: append the domain, watch
# the guard stay green): AGENTS.md, AI.md, .cline.md, .github/instructions/*,
# scraper/WORKFLOW.md. An include list fails OPEN for every file nobody
# remembered. An exclude list fails CLOSED: a new doc, a new agent charter, a new
# per-tool rule file is guarded from the moment it exists, and adding an exemption
# is a visible diff to this list.
#
# So the list below is what remains after #330 EXECUTED #313's deferred list —
# every former runtime-fallback exclusion (compose files, proxy defaults,
# workflows, CLAUDE.md, backend/, frontend/, agents/, importer/, the proxy
# verifiers) was renamed to the product identity and is now IN SCOPE:
#   CHANGELOG.md, docs/retrospectives/
#       — immutable history; the old identity is part of the record.
#   scripts/check_no_pii.sh, scripts/check_no_pii.test.sh
#       — this checker and its fixtures carry the patterns by construction (§46).
#
# A line inside the scope may keep the domain ONLY if it carries one of three
# NAMESPACED annotations, on the SAME line (an exception must be deliberate and
# visible in the diff, not implicit):
#   * `<!-- de-brand:canonical: … -->`  — an explicitly-marked canonical-deployment-instance aside
#   * `<!-- de-brand:historical: … -->` — a historical record; the comment annotates an
#                                         incident narrative WITHOUT rewriting it
#   * ghcr.io/mavrovde/mavrov.de        — a pre-#88-rename GHCR image path
#   * ghcr.io/mavrovde/hirefolio        — a pre-#330-rename GHCR image path (tags ≤ 1.14.0)
#
# The `de-brand:` namespace and the exact lowercase spelling are load-bearing, and
# so is matching CONTENT ONLY. Round 1 of #318 shipped this as three BARE words
# (`canonical|historical|…`) matched against the whole `git grep` output line, and
# the reviewer walked three violations straight through it — the decisive one being
# a REVERT of the very README row this change fixed, which passed because the cell
# said "canonical". Those words are ordinary English here — measured on this
# branch, inside check B's scope and excluding real markers: 33 lines say
# "canonical" ("preserves the canonical behavior", "the canonical URL for every
# page"), 9 say "historical", 41 say either. Matching the whole
# output line added a second hole: any file under a `docs/canonical-urls/`-style
# PATH was exempt forever. And it corrupted the prose — two doc lines had the word
# "historical" inserted purely to satisfy the matcher. An annotation mechanism that
# rewrites documentation to appease itself is the wrong mechanism (lessons §47).
#
# KNOWN LIMITS of check B, stated so nobody mistakes them for guarantees:
#   * The exemption is LINE-LEVEL. A marker exempts its entire line, so a line
#     that legitimately carries an annotation AND also introduces a fresh,
#     unrelated branded reference is not caught. Keep annotated lines short and
#     single-purpose; the diff is the real review.
#   * The marker is a BARE TOKEN anywhere in the line's content — including inside
#     a fenced code block, a quoted example, or a sentence merely *describing* the
#     mechanism. Documenting the marker on the same line as a branded reference
#     therefore exempts that line. (This file and its self-test are excluded for
#     exactly that reason; other docs should put the token and the example domain
#     on separate lines.)
#   * Text only, like check A. A domain baked into an image, a PDF, or any binary
#     asset is invisible to `git grep` and needs eyeball review at PR time.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

PATTERNS='serg\.mavrov|smavrov|sergii|G-1QSMT6N045'

# Allowlist: legal/historical records and the one negative assertion.
#   LICENSE            — the copyright holder is the real author (correct).
#   CHANGELOG.md       — immutable history.
#   this script        — carries the patterns.
hits=$(git grep -inE "$PATTERNS" -- . \
  ':(exclude)LICENSE' \
  ':(exclude)CHANGELOG.md' \
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
# Case-SENSITIVE and namespaced on purpose (see the header): only a deliberate
# `de-brand:` marker, or the literal legacy GHCR path, exempts a line.
GUIDANCE_ANNOTATIONS='de-brand:(canonical|historical)|ghcr\.io/mavrovde/(mavrov\.de|hirefolio)'

# Ask git only for the FILE LIST, then let awk read each file and judge its lines.
# The marker is therefore tested against file CONTENT and nothing else. Filtering
# `git grep -n` output instead (round 1 of #318) tests `path:line:content`, so a
# directory named `canonical-urls/` exempts everything inside it — and stripping
# the prefix textually does not fix that, because a path may itself contain `:`.
# Reading the file is the only formulation with no prefix to parse. `-z` keeps
# paths with spaces intact; the report re-creates `path:line:content` itself.
brand=$(git grep -zilE 'mavrov\.de|hirefolio' -- '.' \
  ':(exclude)CHANGELOG.md' \
  ':(exclude)docs/retrospectives/*' \
  ':(exclude)scripts/check_no_pii.sh' \
  ':(exclude)scripts/check_no_pii.test.sh' \
  2>/dev/null | while IFS= read -r -d '' f; do
    awk -v f="$f" -v pat="$GUIDANCE_ANNOTATIONS" '
      tolower($0) ~ /mavrov\.de|hirefolio/ && $0 !~ pat { printf "%s:%d:%s\n", f, FNR, $0 }
    ' "$f"
  done)

if [ -n "$brand" ]; then
  echo "✗ De-brand guard (#313/#330): a retired identity (mavrov.de or the old product"
  echo "  name hirefolio) appears, unannotated, on a CURRENT-GUIDANCE surface:"
  printf '%s\n' "$brand"
  echo "  Fix it one of three ways (the marker must be on the SAME line, exactly as spelled):"
  echo "    * write the product voice instead — 'Beaconfolio', '<your-domain>', 'example.com';"
  echo "    * if the line is genuinely an aside about the canonical deployment INSTANCE,"
  echo "      append '<!-- de-brand:canonical: … -->' — README keeps exactly one such aside;"
  echo "    * if it is a historical record, annotate WITHOUT rewriting the narrative:"
  echo "      append '<!-- de-brand:historical: … -->' to the line."
  echo "  Prose that merely CONTAINS the words 'canonical' or 'historical' is not a marker."
  rc=1
else
  echo "✓ De-brand guard: current-guidance surfaces speak in the product's voice."
fi

exit "$rc"
