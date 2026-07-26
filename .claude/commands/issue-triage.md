---
description: Triage the open GitHub issue backlog — find orphan issues (missing milestone/priority/area) and propose fixes
---

Triage open issues on `mavrovde/mavrov.de` per the **`issue-workflow`** skill and `CLAUDE.md` →
*Issue tracking, milestones & labels*. Report findings and **propose** fixes; only apply label/
milestone edits the user approves. $ARGUMENTS

1. **Fetch the backlog:**
   `gh issue list --state open --limit 200 --json number,title,milestone,labels`
2. **Flag orphans** — every issue MUST have a **milestone**, exactly one **priority** label
   (`P0-critical`/`P1-high`/`P2-medium`/`P3-low`), and **≥1 area** label
   (`backend`/`frontend`/`infra`/`ci-cd`/`performance`/`tech-debt`/`architecture`/`content`/`i18n`).
   List each issue missing any of these, and note issues with no **type** label
   (`bug`/`enhancement`/`documentation`/`dependencies`/`security`) or >1 priority.
3. **Propose fixes** — for each flagged issue suggest the milestone/labels from its title/body,
   reusing an existing thematic milestone (e.g. dependency work → *Dependency modernization*). Give
   the exact command, e.g.
   `gh issue edit <NN> --milestone "Reliability & bug fixes" --add-label "backend" --add-label "P2-medium"`.
4. **Apply** only what's approved; re-run step 1 to confirm no orphans remain.

Output a short table: issue # · title · what's missing · proposed milestone+labels. Never paste
secrets (the repo is public).
