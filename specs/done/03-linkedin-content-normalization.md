# LinkedIn post text normalization helper

## Summary
Add pure functions that clean raw scraped LinkedIn text and extract its hashtags. Pure, no I/O —
an ideal, fully gate-coverable unit.

## Scope
- **In:** in `backend/app/services/linkedin.py` (module-level functions, no network):
  - `normalize_linkedin_text(text: str) -> str`
  - `extract_hashtags(text: str) -> list[str]`
- **Out:** no endpoint, no DB, no scraper/HTTP calls.

## Contract / behaviour
`normalize_linkedin_text`:
- Removes LinkedIn's literal `hashtag` label that precedes each tag. Raw scrape looks like
  `"…noise?​\nhashtag\n#EngineeringManagement \nhashtag\n#SoftwareArchitecture"` → the literal
  `hashtag` tokens must be gone, leaving `#EngineeringManagement #SoftwareArchitecture` inline.
- Strips zero-width / bidi chars (`​`, `‎`, `‏`, `﻿`); NBSP → normal space.
- Collapses 3+ consecutive blank lines to a single blank line; preserves normal paragraph breaks.
- Trims leading/trailing whitespace. Returns clean UTF-8.

`extract_hashtags`:
- Returns the post's hashtags without `#`, de-duplicated case-insensitively, in first-seen order,
  **capped at 5**. E.g. from the sample above → `["EngineeringManagement", "SoftwareArchitecture"]`.

## Acceptance criteria (testable)
- [ ] Table-driven tests including the real dirty sample above assert: no literal `hashtag` token
      and no zero-width chars remain; paragraph breaks preserved.
- [ ] `extract_hashtags` dedupes, strips `#`, caps at 5, and returns `[]` for text with no tags.
- [ ] Empty/whitespace input → `""` / `[]` (no crash).
- [ ] New code fully covered; backend suite green at 100%.

## Notes / constraints
- Keep them pure and importable (no dependency on the LinkedIn client). New test file, e.g.
  `backend/tests/test_linkedin_normalization.py`. Minimal, no unrelated changes.
</content>


---
## Intake result (2026-07-06 17:31)
- branch: `agent/03-linkedin-content-normalization`
- gate green: True
- outcome: opened PR: pull request create failed: HTTP 401: Requires authentication (https://api.github.com/graphql)
Try authenticating with:  gh auth refresh -h github.com
- run log: `docs/agent-runs/03-linkedin-content-normalization-20260706-164510.md`
