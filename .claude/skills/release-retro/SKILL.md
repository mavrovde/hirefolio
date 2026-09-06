---
name: release-retro
description: >-
  The release retrospective — how to analyse a shipped release (its issues, PRs, review
  threads and effort telemetry) and turn what actually happened into edits to the committed
  AI configuration. Use it at every release, right after the tag, and whenever a post-mortem
  is called for. Encodes what to measure (acceptance-criteria quality, issue grounding, code
  defect classes, review-catch patterns, cost and rounds), how to classify a finding into an
  action, and the hard rule that a retro producing no config change must say why.
---

# Release retrospective

A release is not finished when the tag is pushed. It is finished when what the release *taught*
is written into the configuration that governs the next one. Otherwise every release pays for
the same lessons again — and this repo has receipts for that: the same reviewer caught the same
class of defect (a claim asserted rather than measured) in four consecutive PRs before it became
a rule.

**Owner directive (2026-09-06):** the retrospective is part of the release process, not an
optional extra. `release-manager` does not report a release complete without it.

## Inputs — gather before analysing

Everything here is evidence, not opinion. Collect it first, then reason.

```bash
# The release's issues and PRs
gh pr list --repo mavrovde/hirefolio --state merged --search "merged:>=<prev-tag-date>" \
  --json number,title,labels,mergedAt,reviews
gh issue list --repo mavrovde/hirefolio --state closed --search "closed:>=<prev-tag-date>" \
  --json number,title,body,comments

# Every review verdict in the window — the richest signal in the repo.
# BOTH streams: this repo's sanctioned verdict is often a COMMENT, because
# same-identity `gh pr review --approve` is blocked (env-gotchas). Reading
# `reviews` alone silently loses those — the same bug the merge gate's jq had.
gh pr view <n> --repo mavrovde/hirefolio --json reviews,comments \
  --jq '[(.reviews[]?.body),(.comments[]?.body)][]'

# Effort telemetry (recorded at close-the-loop; not retrievable later)
# GitHub Project 3: Tokens (k), Time of processing (min), Review rounds, Agent, Model
```

## The five questions

Answer each with numbers and quotes, never impressions.

### 1. Acceptance criteria — were they checkable, and were they checked?
- Did any AC turn out **unachievable** as written? (v1.12.0: #277's "mutation-pin the refresh
  idiom" — the two forms are observably equivalent, so no test can distinguish them.)
- Did any AC get **silently skipped** and only surface in review? (#279's frontend latch was
  absent from the first implementation entirely.)
- Did a PR claim `Closes #NN` while an AC was unmet? That is a rule-7 violation and a signal
  that the AC was written to be closed rather than to be true.
- **Action shape:** if ACs are being written unachievably, the fix belongs in `issue-author`'s
  charter (how to write a verifiable criterion) — not in a reminder to try harder.

### 2. Issue quality — did the implementer have to re-research?
- Were `path:line` citations present and still accurate at implementation time?
- Did the issue survive contact with the code, or did the diagnosis change on first read?
- **Action shape:** grounding failures → `issue-author`; stale-by-the-time-you-start failures →
  a note about re-verifying citations, in the dev charters.

### 3. Code quality — what classes of defect reached review?
Cluster the review blockers by CLASS, not by count. Three PRs blocked for the same reason is a
charter bug; three unrelated blockers are normal engineering. v1.12.0's classes were:
- **check-then-insert races** (an application-level guard where only a DB constraint holds),
- **fake-green tests** (a mock that never intercepted; an assertion that could not fail),
- **claims asserted rather than measured** (a "no-op" migration path that wasn't, a grep result
  overstated twice),
- **content lost in a rebase** and not re-verified after conflict resolution.
- **Action shape:** a class that a *gate could catch* becomes a hook or lint; a class that needs
  judgement becomes a charter paragraph with the incident named.

### 4. Review actions — what did reviewers catch that authors missed?
This is the highest-value section, because every reviewer catch is a defect the authoring agent
should have caught first.
- Which catches **repeated** across PRs? Those belong in the author-side charter.
- Did reviewers verify by **running** things, or by reading? (The former is what caught the racy
  promote, the vacuous viewport assertion and the duplicate constraint.)
- Did any review round produce **zero** findings? Rounds that find nothing may mean the gate is
  working — or that the reviewer scope was too narrow.
- **Action shape:** a repeated catch → the dev charters gain the check the reviewer performs.

### 5. Cost — where did the tokens and rounds go?
- Tokens and wall time per delivery, and the **share spent on rework** (rounds 2+).
- Rounds per PR: rising average means an instruction is missing.
- Model mix per item, once recorded — cost per delivered issue by model.
- **Action shape:** rework share is the number to drive down; name the single change most likely
  to move it and record the prediction so the NEXT retro can check it.

## Turning findings into changes

Use the enforcement order from the `ai-integration` charter — **hook > skill > charter >
CLAUDE.md > command** — and prefer the cheapest thing that actually prevents recurrence:

| What you observed | What to change |
|---|---|
| A gate could have caught it mechanically | a hook or a lint, with a failing-first case in its `*.test.sh` |
| Reusable knowledge, needed on demand | a `lessons-learned` entry — with the incident, so a future reader can judge whether it still applies |
| One role keeps making one mistake | that agent's charter |
| A project-wide expectation was never written down | a CLAUDE.md rule (and renumber references — grep for every variant, including hyphen and en-dash forms) |
| A repeatable procedure | a command |
| **No existing role owns the work** | propose a NEW agent, with the evidence that the gap is real and recurring — not speculative |

**Deletions count.** An instruction nobody follows, or that fires on the wrong trigger, makes the
configuration worse: it dilutes what matters and costs tokens on every load. Say what you removed.

## Output

1. **The permanent record: `docs/retrospectives/vX.Y.Z.md`**, committed in the same PR as the
   config changes, with the five sections in the same order every time so the numbers line up as a
   series. Then update the trend table in `docs/retrospectives/README.md` — an analysis that lives
   only in a GitHub comment can be read once but never trended, and trending is the point.
2. **A retrospective comment on the roadmap issue** pointing at that file — the announcement, not
   the record.
3. **A PR** carrying the config changes, labelled `ai-config`, reviewed like any other (rule 13 has
   no carve-out for configuration).
4. **A prediction**: name the observable you expect to move (e.g. "review rounds on frontend PRs
   below 2.0") so the next retro can check it rather than re-deciding.

## The hard rule

**A retrospective that produces no configuration change must say why** — in writing, on the issue.
"Nothing came up" is almost never true after a release with review rounds in it; it usually means
the analysis stopped at the summary instead of reading the review threads. If the release genuinely
taught nothing new, say that explicitly and name what you checked.
