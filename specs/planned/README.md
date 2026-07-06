# LinkedIn import — decomposed delivery plan

The full feature (`_full-reference.md`) proved too large for the autonomous team to build
in one shot (it plans well but flails when a single spec touches 8+ files). It's split here
into small, single-concern specs — each about the size of a change the team has **reliably**
delivered before (e.g. the `/api/app/ping` endpoint: one file + a test).

## Run order (each depends on the ones before it)

| # | Spec | Layer | Gate-covered? |
|---|------|-------|---------------|
| 1 | `01-post-provenance-columns.md`      | backend model + migration | ✅ yes |
| 2 | `02-import-config-settings.md`       | backend config            | ✅ yes |
| 3 | `03-linkedin-content-normalization.md` | backend pure helper     | ✅ yes |
| 4 | `04-linkedin-import-post-endpoint.md`  | backend endpoint (needs 1–3) | ✅ yes |
| 5 | `05-scraper-post-extraction.md`      | Node scraper              | ❌ no (outside gate) |
| 6 | `06-linkedin-importer-agent.md`      | standalone importer       | ❌ no (outside gate) |

## Workflow — ONE at a time, merge between each

```bash
export A2A_LLM_PROVIDER=anthropic A2A_MODEL=claude-sonnet-4-6
export ANTHROPIC_API_KEY="$(security find-generic-password -s anthropic-api-key -w)"

mv specs/planned/01-*.md specs/inbox/
python -m agents.intake --once      # -> opens a PR
# review + MERGE the PR to main
mv specs/planned/02-*.md specs/inbox/   # only after 01 is merged
python -m agents.intake --once
# ... repeat in order
```

**Do not drop them all into `specs/inbox/` at once.** The team branches every spec from
`main`, so spec 4 (the endpoint) would branch off a `main` that lacks spec 1's columns and
fail its gate. Each PR must be **merged to main** before the next dependent spec runs.

Specs **5 and 6 are outside the deterministic test gate** (Node / standalone process), so a
"green gate" won't prove them. Expect to verify those manually — or build them directly if the
team struggles (it's weakest exactly where the gate can't check it).

Full contracts, the prod-connection design, and the test strategy live in `_full-reference.md`.
</content>
