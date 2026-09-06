# Release retrospectives

One file per release, `vX.Y.Z.md`, committed. This directory exists so the retrospectives can be
**compared across releases** — an analysis that lives only in a GitHub comment can be read once but
never trended, and trending is the whole point: the defect classes, the review-round average and
the rework share only mean something as a series.

Written by the `ai-integration` agent at every release (CLAUDE.md rule 8, `/retro`, and the
`release-retro` skill). The issue comment on the roadmap issue is the announcement; **this file is
the record**.

## What each file contains

The five questions from the `release-retro` skill, always in the same order so columns line up
across releases:

1. **Acceptance criteria** — unachievable ones, silently-skipped ones, `Closes` against unmet ACs
2. **Issue quality** — grounding accuracy, whether the implementer had to re-research
3. **Code quality** — review blockers clustered by CLASS, with counts
4. **Review actions** — what reviewers caught that authors missed, and what repeated
5. **Cost** — tokens, wall time, rounds, and the share spent on rework

…then the change list (what was edited in the AI configuration and why), and a **prediction** that
the next retrospective checks.

## The trend table

Update this when you add a retro. These are the numbers worth watching; everything else is context.

| Release | PRs merged | Verdicts | Mean rounds | Approved r1 | Rework share of review tokens | Blocker-level "claim not measured" | Tokens | Agent-time |
|---|---|---|---|---|---|---|---|---|
| [v1.12.0](v1.12.0.md) | 10 | 24 | **2.4** | 20% (2/10) | **75%** | **9** | 9.07M | 28.1h |

**Standing prediction (set by v1.12.0, checked at v1.13):** mean rounds below **2.0**, ≥40%
approved on round 1 — both restated against the CORRECTED baseline (2.4 rounds, 20% r1 — #275 and #281 both
opened with an APPROVE; the
original 2.5/17% came from the wrong corpus), zero blocker-level "claim asserted rather than measured", zero "the fix has no
failing-first test" blockers.

**Falsification stated up front:** if rounds stay near 2.5 while claim-discipline blockers go to
zero, the bottleneck was never author discipline — it is PR size (v1.12.0 median: 20 changed files),
and the next retro should look there instead.

## How to count consistently

So the series stays comparable, count the same way every time:

- **Verdicts** = posted review bodies containing the UPPERCASE marker `APPROVE` or
  `REQUEST CHANGES`, counted over the release's **merged** PRs. Count these, **not** the Project 3
  `Review rounds` field — v1.12.0 found that field disagreeing with the thread (5 recorded vs 3
  posted on #240). **Run this, do not count by hand** — four different hand counts (30, 32, 34, and a 29 from a mis-drawn corpus)
  were reported for v1.12.0 and none reproduced:

  ```bash
  # The corpus is every PR MERGED BETWEEN THE TAGS — not `git log <prev>..<tag>`,
  # which cites issue numbers as well as PRs and sweeps in PRs that merged before
  # the previous tag. Both published counts for v1.12.0 (29/14 and 32/12) came
  # from getting the CORPUS wrong, not the matcher.
  PREV=$(git log -1 --format=%aI <prev-tag>); CUR=$(git log -1 --format=%aI <tag>)
  gh pr list --state merged --limit 100 --json number,mergedAt,reviews,comments \
    --jq "[.[] | select(.mergedAt > \"$PREV\" and .mergedAt <= \"$CUR\")]
          | map([(.reviews[]?.body),(.comments[]?.body)]
                | map(select(test(\"APPROVE|REQUEST CHANGES\"))) | length)
          | add"
  ```

  Case matters: a lowercase "approve" in prose is not a verdict, and matching case-insensitively
  inflated the v1.12.0 count by one.
- **Rework share** = tokens spent in rounds 2+ ÷ total measured review tokens. Only rounds with
  real telemetry count; estimates are excluded and the sample size is stated.
- **Release attribution** = the tag the work actually **shipped in**, not the one it was planned
  for. v1.12.0 found #235 filed under v1.11.1 although its PR merged after that tag, understating
  the release by ~11%.
- **A multi-phase item's bucket is where its REMAINING work lands**, not where its first phase
  shipped. Otherwise a phase-1 delivery keeps its release open forever: v1.12.0 read "in progress"
  for hours after it was tagged because #247 (phase 1 shipped, phases 2–3 pending) and #61 (blocked
  on an owner-gated deploy) still sat in its bucket, and the roadmap tracker — which spans every
  release — was bucketed at all. **Move the item when a phase ships; a tracking issue gets no
  release bucket.**
