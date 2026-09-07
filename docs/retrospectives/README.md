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

| Release | PRs merged | Verdicts (loose / heading-anchored) | Mean rounds | Approved r1 | Rework share of verdicts | "Claim not measured" findings | Median files/PR | Tokens | Agent-time |
|---|---|---|---|---|---|---|---|---|---|
| [v1.12.0](v1.12.0.md) | 10 | 24 / n-a¹ | **2.4** | 20% (2/10) | 58% | **9** | 17 | 9.07M² | 28.1h² |
| [v1.13.0](v1.13.0.md) | 16 | 52 / **48** | **3.00** | 6% (1/16) | 67% | **12** | 14 | not recorded³ | 23.5h tag→tag |

¹ v1.12.0's verdict headings predate the mandated form, so the heading-anchored matcher undercounts
that window (15). From v1.13.0 the heading is charter-mandated **and** gate-enforced, so the
heading-anchored column is exact and becomes the primary one at v1.14.0.
² Console session estimates, not Project 3 fields — labelled as estimates.
³ **Project 3's `Tokens (k)` and `Time of processing (min)` are empty for every item in the repo**,
and `Review rounds` is unset for all six issues v1.13.0 shipped. Inventing a comparable number would
be the exact defect these retros keep finding; the measurable GitHub-side proxies are in the table
instead (PR count, verdicts, rounds, PR size, wall clock). Either the fields get filled at
close-the-loop or the columns should be dropped — decide it at v1.14.

**v1.12.0's prediction: FAILED.** It asked for mean rounds < 2.0 and ≥40% round-1 approvals;
measured 3.00 and 6%. Its own falsification test (PR size) was also refuted — median size FELL 17→14
while rounds rose. See [v1.13.0.md §5](v1.13.0.md) for the diagnosis (the release's material changed:
credential-, billing- and container-configuration-shaped features produced 9 blockers in classes that
barely existed at v1.12.0), and note the counter-evidence to a "churn" reading: **zero review rounds
found nothing**.

**Standing prediction (set by v1.13.0, checked at v1.14):** zero class-A findings ("a documented knob
never reaches the container"); zero merges on a stale approval (newest heading-anchored verdict at
merge time is an APPROVE, for every merged PR); round-1 approvals **≥20%**; mean rounds **≤2.7**
heading-anchored.

**Falsification stated up front:** if classes A, C and D go to zero while mean rounds stay ≥3.0, then
author-side discipline was never the constraint — the next retro should look at reviewer scope
(a single reviewer serialising four rounds on security-shaped PRs) instead of editing charters.

## How to count consistently

So the series stays comparable, count the same way every time:

- **Verdicts** = posted review bodies containing the UPPERCASE marker `APPROVE` or
  `REQUEST CHANGES`, counted over the release's **merged** PRs. Count these, **not** the Project 3
  `Review rounds` field — v1.12.0 found that field disagreeing with the thread (5 recorded vs 3
  posted on #240). **Run this, do not count by hand** — four hand counts (30, 32, 34, 29)
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

  **The loose matcher over-counts, measurably, and v1.13.0 quantified it.** A body containing a
  marker is not necessarily a verdict: on #291 it returns 11 where the thread holds **8** reviewer
  verdicts, because three of the marker-bearing comments are the AUTHOR's fix reports (`## Round 4 —
  the three blockers, each measured against the unfixed hook`, whose first marker is `APPROVED`);
  #282 returns 5 for 4. Reviewer and author post under the SAME identity here, so no author filter
  can separate them — only the marker's POSITION can. Since v1.13.0 `pr-reviewer` MUST state the
  verdict in the body's first non-empty line and `pre-merge-gate.sh` reads exactly that line, so
  count with the heading-anchored filter and report the loose number alongside it while the series
  still contains pre-mandate releases:

  ```bash
  gh pr list --state merged --limit 100 --json number,mergedAt,reviews,comments \
    --jq "[.[] | select(.mergedAt > \"$PREV\" and .mergedAt <= \"$CUR\")]
          | map([(.reviews[]?.body),(.comments[]?.body)]
                | map(select(split(\"\n\") | map(select(test(\"\\\\S\"))) | (.[0]//\"\")
                             | test(\"REQUEST CHANGES|APPROVED?\"))) | length)
          | add"
  ```

  Do NOT retro-fit the heading-anchored number onto pre-v1.13.0 releases: it returns 15 for v1.12.0's
  24, an undercount caused by format drift, not a correction.
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
