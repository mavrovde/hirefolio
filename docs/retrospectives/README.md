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
| [v1.12.0](v1.12.0.md) | 12 | 30 | **2.5** | 17% (2/12) | **75%** | **9** | 9.07M | 28.1h |

**Standing prediction (set by v1.12.0, checked at v1.13):** mean rounds below **2.0**, ≥40%
approved on round 1, zero blocker-level "claim asserted rather than measured", zero "the fix has no
failing-first test" blockers.

**Falsification stated up front:** if rounds stay near 2.5 while claim-discipline blockers go to
zero, the bottleneck was never author discipline — it is PR size (v1.12.0 median: 20 changed files),
and the next retro should look there instead.

## How to count consistently

So the series stays comparable, count the same way every time:

- **Verdicts** = posted review bodies containing `APPROVE` or `REQUEST CHANGES`, counted from
  `gh pr view <n> --json reviews,comments`. Count these, **not** the Project 3 `Review rounds`
  field — v1.12.0 found that field disagreeing with the thread (5 recorded vs 3 posted on #240).
- **Rework share** = tokens spent in rounds 2+ ÷ total measured review tokens. Only rounds with
  real telemetry count; estimates are excluded and the sample size is stated.
- **Release attribution** = the tag the work actually **shipped in**, not the one it was planned
  for. v1.12.0 found #235 filed under v1.11.1 although its PR merged after that tag, understating
  the release by ~11%.
