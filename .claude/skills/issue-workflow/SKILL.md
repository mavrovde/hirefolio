---
name: issue-workflow
description: >-
  Guides issue-driven development for mavrov.de — creating, triaging, labeling, and
  milestoning GitHub issues and linking PRs. Use when opening/triaging an issue, deciding
  its milestone/labels/priority, wiring `Closes #NN` into a PR, or closing-the-loop after
  work lands. Encodes the issue template, milestone taxonomy, label+priority scheme, the
  "every issue needs milestone+priority+area" invariant, the `gh` commands, and the
  no-secrets rule for this PUBLIC repo (`github.com/mavrovde/hirefolio`).
---

# Issue workflow — mavrov.de

Repo: `mavrovde/hirefolio` (**PUBLIC**). Issues are the project notebook: every idea, plan, bug,
deferred fix, shipped milestone, and research decision lives as an issue — not in chat or personal
memory. Register work up front; close-the-loop when it lands. This skill is the operational
companion to `CLAUDE.md` → *Issue tracking, milestones & labels*.

## Invariant — no orphan issues
**Every issue MUST have: a milestone (theme) + exactly one priority label + ≥1 area label.**
Missing any of these = incomplete; fix before moving on. `/issue-triage` sweeps the backlog for
violations.

## Issue template (all 8 sections)
1. **Summary** — what this is, in one or two lines.
2. **Why it matters** — the motivation.
3. **Impact** — project / developers / visitors.
4. **Current state** — grounded, cite `path:line` (never secret values — see no-secrets rule).
5. **Proposed action** — the plan.
6. **Acceptance criteria** — a checkable `- [ ]` list.
7. **How to verify (test steps)** — concrete steps to confirm done.
8. **Links** — related issues/PRs/docs.

## Milestones — reusable thematic buckets (NOT per-version)
Reuse an existing theme for similar work; add a new milestone only for a genuinely new theme.
- **Dependency modernization** — dep upgrades + upstream-blocked bumps (every dependency task → here).
- **Security & hardening** — vuln remediation, rate-limiting, secret hygiene.
- **Reliability & bug fixes** — flakes, schema/data drift, session bugs.
- **CI/CD, tooling & docs** — pipeline, gates, tooling, doc accuracy.
- **Content & localization** — content + translations.
- **Transfer to general portfolio** — the product/template transformation.

## Label scheme = type + area + priority
- **type**: `bug` · `enhancement` · `documentation` · `dependencies` · `security`
- **area** (≥1): `backend` · `frontend` · `infra` · `ci-cd` · `performance` · `tech-debt` ·
  `architecture` · `content` · `i18n`
- **priority** (exactly one): `P0-critical` · `P1-high` · `P2-medium` · `P3-low`

## `gh` commands

Create a fully-tagged issue (body from a file so the template renders cleanly):
```bash
gh issue create \
  --title "Upgrade FastAPI to latest 0.11x" \
  --body-file /tmp/issue-body.md \
  --milestone "Dependency modernization" \
  --label "dependencies" --label "backend" --label "P2-medium"
```

Add/fix labels or set the milestone on an existing issue (use during triage):
```bash
gh issue edit 74 --add-label "documentation" --add-label "ci-cd" --add-label "P1-high"
gh issue edit 74 --milestone "CI/CD, tooling & docs"
```

Inspect and list:
```bash
gh issue view 74
gh issue list --state open --json number,title,milestone,labels
gh label list --limit 100        # confirm a label exists before adding
gh api repos/mavrovde/hirefolio/milestones --jq '.[].title'
```

Comment + close (close-the-loop):
```bash
gh issue comment 74 --body "Shipped in #NN (run <url>, tag vX.Y.Z). Acceptance criteria met: …"
gh issue close 74
```

The `github` MCP server does the same operations when `gh` isn't preferred. The `security-guidance`
plugin supports triage of `security`-labelled issues.

## Effort report (owner directive 2026-09-06 — REQUIRED on every delivery)

Every delivery-status and close-the-loop comment carries an effort table; numbers come from the
agent task telemetry (`subagent_tokens` / `duration_ms` / `tool_uses` in the task notification —
record them IMMEDIATELY, they are not retrievable later). Mirror the totals to Project 3
(`users/mavrovde/projects/3`) fields: `Tokens (k)`, `Time of processing (min)`, `Review rounds`,
`Agent`, `Skills`; set Status=Done at close-the-loop. New issues are added to the board with a
`Release` bucket on creation.

```markdown
### 📈 Effort report
| Step | Agent | Model | Tokens | Time | Tool uses | Prompt (gist) |
|---|---|---|---|---|---|---|
| implement + fix rounds | main-orchestrator | Fable 5 | ~700k (est.) | 2.5h | — | build X per ACs |
| review round 1 | pr-reviewer | Opus 5 | 116.9k | 13m00s | 79 | full verdict vs ACs |
```

**Record the MODEL for every step** (owner directive 2026-09-06) — it is the input to model
effectiveness comparison: which model, at what cost, produced how many review rounds and how many
defects caught. The agent's model comes from its charter frontmatter (`model:`) or the explicit
override at spawn time; the main loop's model is this session's. Mirror it to the Project 3
`Model` field (`fable-5` / `opus-5` / `sonnet-5` / `haiku-4.5` / `mixed` when an item spans an
orchestrator and subagents on different models).

Mark estimates as estimates; measured beats claimed (CLAUDE.md issue rule 7).

## PR ↔ issue linking
- `Closes #NN` / `Fixes #NN` in the PR body for issues the merge resolves (auto-closes on merge).
- `Refs #NN` for partial/related work (issue stays open).
- State in the PR **how each acceptance criterion is met**; keep the PR checklist current.

## Close-the-loop (verify before closing)

> A `Closes #NN` auto-close is **not** close-the-loop — it leaves no visible record. Always post a
> comment naming the **PR, the merge SHA, the pipeline result**, and each acceptance criterion with
> **who verified it and what they ran** (author vs the independent reviewer, and the actual command
> and result). If a criterion is unmet, say so and keep the issue open.
When work lands: comment on the issue with what was done + links (PR, green run URL, release tag),
**verify against the issue's acceptance criteria / How-to-verify steps**, then close it (or note the
remaining status if partial). **Never close on assumption** — confirm the real result first.

## No secrets (PUBLIC repo)
Never paste credentials, tokens, private keys, or step-by-step live-exploit instructions into issues
or PRs. Reference config locations (`path:line`) instead of the secret values.
