# Fix the scraper's post image/date extraction + stable JSON contract

> ⚠️ OUTSIDE the deterministic test gate (Node code). The team's green gate will NOT prove this.
> Ships with its own unit test; verify manually (or build directly if the team struggles).

## Summary
Fix `scraper/scrape-posts.js` so it captures each post's **own** image(s), the original date and
the permalink, and emits a stable JSON schema. Today it wrongly records the profile photo as the
image and isn't wired into npm scripts.

## Scope
- **In:** correct image extraction (post media, not the author's profile photo → `imageUrls: []`);
  capture `postedAt` (ISO 8601 if derivable) + `url` + `urn`; add npm scripts `scrape:posts` and
  `scrape:posts:debug` (`HEADLESS=false`); refactor the parse into a **pure function** with a unit
  test on a captured fixture (no live LinkedIn). Gentle scraping: reuse session, small randomized
  delays, `SCRAPE_MAX_POSTS` cap.
- **Out:** no backend changes, no importer.

## Contract / behaviour
`posts_data.json` = array of:
```json
{ "urn": "urn:li:activity:…", "url": "https://www.linkedin.com/feed/update/…/",
  "content": "full post text …", "imageUrls": ["https://media.licdn.com/…"],
  "imageUrl": "https://media.licdn.com/…", "postedAt": "2026-07-04T10:12:00Z",
  "time": "2 days ago • …", "language": "en" }
```
(`imageUrl` = `imageUrls[0]`, kept for back-compat.)

## Acceptance criteria (testable)
- [ ] `npm run scrape:posts` exists and writes `posts_data.json` in the schema above.
- [ ] A pure parse unit test (node:test) on a **fixture** payload asserts `imageUrls[0]` is the
      post's media URL, **not** the profile photo, and that `postedAt`/`urn`/`url` are parsed.
- [ ] No live LinkedIn, sessions, or scraped data committed (`.gitignore` respected).

## Notes / constraints
- See `_full-reference.md` §Component 2. Prefer LinkedIn's Voyager JSON over hashed DOM classes.
</content>
