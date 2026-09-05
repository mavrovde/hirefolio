---
description: True deploy state — pipeline, published images, live prod version, and a live/not-live verdict
---

Report the TRUE deploy state of mavrov.de. The core doctrine (#112/#120): **a green `deploy.yml`
run means images were PUBLISHED to ghcr; the prod host is updated only if the secrets-gated
`Roll Out To Prod Host` job actually ran** (it skips silently — still green — when
`DEPLOY_HOST`/`DEPLOY_USER`/`DEPLOY_SSH_KEY` are unset). Never report "deployed" from pipeline
color alone.

Gather all four facts, then give the verdict:

1. **Pipeline**: latest `deploy.yml` run on `main` —
   `gh run list --workflow deploy.yml --branch main --limit 1 --json databaseId,status,conclusion,headSha,url`
   Then check whether the rollout actually EXECUTED. The job and its gate step report
   `success` even when the gate disabled the rollout — the tell is the gated steps being
   `skipped` (measured on run 33352162273: job success, gate success, `Roll out validated
   images` skipped, live still behind):
   `gh run view <id> --json jobs --jq '.jobs[] | select(.name=="Roll Out To Prod Host") | [.steps[] | select(.name=="Roll out validated images" or .name=="Health + freshness gate")] | map({name, conclusion})'`
   `skipped` here = images published, nothing rolled out.
2. **Repo version**: `cat VERSION` and the latest tag `git tag --sort=-v:refname | head -1`.
3. **Published images**: the tags the green run pushed (`sha-<headSha>` + version tag) — cite the
   run's publish jobs rather than assuming.
4. **Live prod version**: `curl -s --max-time 10 https://mavrov.de/api/app/stats/public | jq -r .backend_version`
   (cross-check the site footer `BE: vX.Y.Z` if the endpoint is unreachable).

**Verdict — state it plainly, one of:**
- `LIVE = <v>` and it equals VERSION → "prod is on the current version" (only claim this when the
  rollout job's conclusion was success OR the live version itself proves it).
- live < VERSION → "prod is BEHIND: live <live-v>, published <VERSION> — images published, host
  rollout pending (DEPLOY_* secrets not configured — see docs/DEPLOYMENT.md, #112/#156)". This is
  the expected state until the rollout secrets are provisioned; do not call it a failure, and do
  NOT call it deployed.
- pipeline red or unreachable endpoint → report exactly what was measured and what could not be.

Notes:
- `deploy.yml` has a concurrency guard (#147) that QUEUES a second run rather than cancelling —
  overlapping merges wait; never trigger overlapping deploys manually.
- Report what you measured, not what you expect (CLAUDE.md issue rule 7): every number in the
  verdict must come from a command run in THIS invocation. $ARGUMENTS
