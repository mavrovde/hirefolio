# Import LinkedIn posts (text + images) into mavrov.de via a standalone importer agent

## Summary
Move all of Sergii's LinkedIn posts — **text and their real images** — into the mavrov.de
blog, and keep them importable on demand. Three pieces:

1. **A hardened ingest endpoint** on the backend that receives one post (text + image
   **bytes**) and stores the image **locally** so it renders on mavrov.de without depending
   on LinkedIn.
2. **A standalone importer agent** — a small, stable, long-running/cron-able process that is
   **NOT part of the A2A team** — which drives the scraper, downloads each post's images, and
   pushes them to the ingest endpoint. It is idempotent, retrying, and logged.
3. **Scraper updates** so it extracts each post's *actual* images (not the profile photo),
   the original post date, and the permalink, and exposes them in a clean, stable JSON contract.

## Background — current state (what already exists)
- **Backend**: `backend/app/api/linkedin.py` has `POST /api/linkedin/transfer-post` and
  `/transfer-posts`. They create a draft `Post` but store the **external** `image_url`
  (`media.licdn.com/...`), which expires and requires LinkedIn auth → **images won't display
  on mavrov.de**. There is **no dedup** (every run creates a new post with a random slug
  suffix), the title is `content[:50]`, summary is hardcoded `"Imported from LinkedIn"`, and
  `language` is hardcoded `"en"`.
- **Model**: `backend/app/models/post.py` `Post` already supports **local image storage**
  (`image_blob: LargeBinary`, `image_type: str`) served via `GET /api/posts/{id}/image`, with
  `display_image_url` preferring the local blob. The ingest path must use this.
- **Scraper**: `scraper/scrape-posts.js` produces `posts_data.json` with
  `{id, content, imageUrl, urn, url, time}` — but `imageUrl` is currently the **profile
  photo**, not the post's image (bug). It is **not** wired into `scraper/package.json`
  (only `scrape`/`scrape:debug` → `scrape-linkedin.js` exist). Session lives in
  `scraper/session.json` / `.chrome-profile/`.
- **No standalone importer** exists today. `agents/` is the A2A delivery team and must stay
  untouched by this feature (explicitly out of scope).

## Goals
- Every LinkedIn post ends up as a mavrov.de blog post with its **text** and its **image(s)
  stored locally** on mavrov.de.
- Re-running the importer is **safe** (idempotent) — it updates existing posts instead of
  duplicating them.
- The importer is **stable and independent**: it does not import from, depend on, or run
  inside the `agents/` A2A team; it survives transient failures (retries) and logs clearly.

## Scope
- **In:**
  - New backend ingest endpoint that accepts a post **with image bytes** and stores them locally.
  - `Post` idempotency by LinkedIn URN + capturing original post date & source URL (DB migration).
  - Scraper: extract real post image URL(s), original date, permalink; add an npm script; stable JSON schema.
  - A new **standalone importer** process (own folder, own deps, own tests) that: runs/reads the
    scraper → downloads images (authenticated) → posts each item to the ingest endpoint →
    idempotent, retrying, logged. Runnable one-shot and on a schedule.
  - Config/env for the importer and the endpoint auth token.
  - Tests: pytest for the endpoint (and importer, if Python); scraper parse tests.
- **Out:**
  - Any change to the `agents/` A2A team (roster, orchestrator, autonomous pipeline).
  - Frontend UI changes (the existing admin "transfer" UI may keep calling the old endpoints;
    no new UI is required). Rendering already works via `/api/posts/{id}/image`.
  - Auto-**publishing**: imported posts are created as **drafts** (`published=false`) for review.
  - LinkedIn comments/reactions/analytics; video posts (images only in v1 — see Open decisions).

## Architecture overview
```
scraper/ (Node + Playwright)                 importer/ (standalone, NOT the A2A team)
  scrape:posts  ──► posts_data.json  ──►  read JSON ─► normalize text + detect lang ─►
                    profile_data.json         download image bytes (authenticated)
                                                            │
                                                            ▼
              POST https://mavrov.de/api/app/linkedin/import-post  (TLS, multipart, X-Import-Token)
                                                            │
                                        nginx proxy ─► backend:8000 (internal, not publicly exposed)
                                                            │
                                                            ▼
                                        backend: upsert Post by source_urn, store image_blob
                                                            │
                                                            ▼
                                          mavrov.de blog (image served from our own domain)
```

## The flow in plain words
Here is the whole thing described as a story, start to finish — no jargon.

**The problem today.** Your posts live on LinkedIn. There *is* a "transfer" button in your
admin already, but it cheats: it copies the *link* to the LinkedIn image, not the image itself.
LinkedIn image links expire and are locked behind a login, so a few days later your blog shows
broken pictures. On top of that, if you press transfer twice you get the same post twice, and
the imported posts get an ugly auto-title and today's date instead of the day you actually
posted them.

**What we're building.** Think of it as a little delivery service with three workers:

1. **The scraper** is the *reader*. It logs into LinkedIn once (in a real browser window, so
   you can pass any MFA/CAPTCHA by hand), remembers that session, and from then on quietly
   reads your posts. For each post it writes down the text, the real picture(s) attached to
   that post (today it mistakenly grabs your profile photo — we fix that), the original date,
   and the permalink. It saves all of this to a plain file (`posts_data.json`). The scraper
   only *reads and records* — it never talks to your website.

2. **The importer** is the *courier*, and it's the new stable piece you asked for. It is a
   small standalone program that runs on its own (by hand, or on a timer) and has **nothing to
   do with the A2A agent team**. It opens the file the scraper produced and, for each post,
   does three things: it downloads the actual image bytes from LinkedIn (using the saved login,
   because those images need auth), and then it hands the post — text **plus the image file
   itself** — to your website's new "inbox" endpoint. It carries a secret token so the website
   knows it's really you and not a stranger. If the network hiccups, it waits and retries; if
   one post fails, it shrugs and keeps going with the rest; and it keeps a little notebook of
   what it already delivered so running it again doesn't re-send everything.

3. **The endpoint** is the *receiving desk* on mavrov.de. When the courier hands over a post,
   the desk checks the token, then asks one question: *"Have I seen this LinkedIn post before?"*
   (it recognises posts by their LinkedIn ID, the "URN"). If it's new, it creates a **draft**
   blog post, stores the **image on your own server** (so it will always load, forever), sets
   the real original date, and builds the search embedding so it's findable. If it's a post it
   has seen before, it just **updates** the existing one instead of making a duplicate.

**The end result.** You run the importer, wait a moment, and open your blog admin. All your
LinkedIn posts are sitting there as drafts — correct text, correct pictures hosted on your own
domain, correct dates. You read through them, tidy anything you want, and hit publish on the
ones you like. Run the importer again next month and only the *new* LinkedIn posts show up;
nothing gets duplicated. That's the whole loop: **LinkedIn → scraper reads → importer carries →
your site receives → you review and publish.**

Two deliberate safety choices worth calling out: imported posts are **never auto-published**
(you always get the final say), and images are **copied onto your server** rather than
hot-linked, so your blog never depends on LinkedIn staying up or keeping a link alive.

## Component 1 — Backend: ingest endpoint + model

### 1a. Model / migration (`backend/app/models/post.py` + Alembic)
Add idempotency + provenance to `Post` (all nullable, backward compatible):
- `source_urn: Optional[str]` — LinkedIn activity URN, e.g. `urn:li:activity:7434...`; **unique**
  when not null (partial unique index / `UniqueConstraint`).
- `source_url: Optional[str]` — the LinkedIn permalink.
- `posted_at: Optional[datetime(tz)]` — the original LinkedIn publish time (falls back to `created_at`).

Provide an Alembic migration under `backend/migrations/`. Existing rows: new columns null.

### 1b. Endpoint
> **API prefix:** all routers mount under `settings.api_prefix` = **`/api/app`** (see
> `backend/app/main.py`). So the paths below are the *full* public paths; the LinkedIn router's
> own prefix is `/linkedin`. (The README's `/api/...` examples are stale — the real prefix is
> `/api/app`.)

`POST /api/app/linkedin/import-post` — `multipart/form-data`
- **Auth:** accept **either** a machine token header `X-Import-Token: <token>` (compared to a
  new `settings.linkedin_import_token`) **or** an admin JWT (existing `get_current_admin_user`).
  If `linkedin_import_token` is empty/unset, the header path is disabled (JWT only) — never
  allow a blank token to authenticate. Compare the token with **`secrets.compare_digest`**
  (constant-time; no timing oracle) and **never log the token value**.
- **Image validation:** if an `image` is sent, reject non-image content types (allowlist:
  `image/jpeg|png|webp|gif`) with `415`, and enforce a size cap (e.g. `IMPORT_MAX_IMAGE_MB`,
  default 10 MB) with `413`. Store the validated bytes + content type; do not trust the
  filename/extension.
- **Form fields:**
  | field | type | required | notes |
  |---|---|---|---|
  | `content` | str | yes | post text |
  | `urn` | str | yes | idempotency key → `source_urn` |
  | `title` | str | no | default: first line / first 60 chars of `content`, trimmed on word boundary |
  | `summary` | str | no | default: first ~200 chars of `content` |
  | `language` | str(2) | no | default `"en"` (importer may pass detected lang) |
  | `posted_at` | ISO 8601 str | no | → `posted_at` |
  | `source_url` | str | no | → `source_url` |
  | `tags` | str | no | comma-separated; default `LinkedIn`; capped at model's max 5 |
  | `published` | bool | no | default `false` (draft) |
  | `image` | file | no | the post's real image bytes → `image_blob` + `image_type` |
- **Behavior (upsert by `urn`):**
  - If a `Post` with `source_urn == urn` exists → **update** its `content`, `summary`,
    `image_blob`/`image_type` (only if a new image is sent), `posted_at`, `source_url`, and
    regenerate the embedding. Do **not** duplicate. Do **not** silently flip `published`.
  - Else → **create** a new draft `Post`, generate the embedding
    (`get_embedding(f"{title}\n\n{content}")`, reusing the existing pattern), store the image
    bytes locally (like `upload_post_image` does), and set `source_urn/url` + `posted_at`.
  - Slug: derive from title; ensure uniqueness on the `(slug, language)` constraint (reuse the
    existing random-suffix retry pattern already in `posts.py`).
- **Responses:**
  - `200 {"id": int, "slug": str, "created": bool, "message": str}`
  - `401` on missing/invalid token when no valid JWT.
  - `413` image too large; `415` unsupported image type.
  - `422` on missing required fields (FastAPI validation).

> Keep the existing `/transfer-post` and `/transfer-posts` endpoints working (back-compat).
> They may be documented as deprecated in favour of `/import-post`.

### 1c. Content handling — the post TEXT is the primary payload
The **full post text is always transferred** and is the required core of every import; the
image is optional and rides along. The text must arrive **clean and readable**, not as the raw
scrape. Today's `scraper/posts_data.json` shows exactly what to fix — LinkedIn injects a literal
`hashtag\n` label before every tag and sprinkles zero-width chars, e.g.:

```
…guiding signal amidst the AI noise?​\nhashtag\n#EngineeringManagement \nhashtag\n#SoftwareArchitecture
```

**Normalization rules (applied by the importer before POST; the scraper may pre-clean):**
- Strip LinkedIn's literal `hashtag` label that precedes each tag → `#EngineeringManagement …`.
- Remove zero-width / bidi artifacts (`​`, `‎`, `‏`, `﻿`); normalize NBSP → space.
- Collapse 3+ blank lines to a paragraph break; **preserve** intentional paragraph breaks.
- Trim leading/trailing whitespace. Store as clean UTF-8 text (Markdown-friendly).
- Derive `tags` from the post's hashtags: drop `#`, de-dupe case-insensitively, keep `LinkedIn`
  as a base tag, **cap at the model's 5**. Hashtags may stay inline in the body as well.
- **Skip** posts whose cleaned text is empty (e.g. a bare reshare with no commentary) — log as
  `skipped:empty`, do not create an empty post.

A backend/importer unit test must assert that a raw sample containing `hashtag\n#Foo` and a
zero-width char round-trips to clean text (no literal `hashtag` token, no `​`).

### 1d. Connecting to production — how the importer reaches mavrov.de
Prod topology (from `docker-compose.prod.yml` + `proxy/default.conf`): the **backend has no
published port** — it lives only on the internal `app-network` as `backend:8000`. Public
traffic enters the **nginx `proxy`** (real TLS cert for `mavrov.de`), which routes
`location /api/app/ → http://backend:8000/api/app/`. So the only way in from outside is the
public HTTPS host.

**Mode A — remote (recommended default): the importer runs on your machine / a cron box and
talks to prod over HTTPS.**
- `MAVROV_API_URL=https://mavrov.de`
- Calls `POST https://mavrov.de/api/app/linkedin/import-post`, authenticated with the
  `X-Import-Token: <secret>` header (no browser, no JWT, no cookies needed).
- Standard TLS verification (valid public cert) — no `verify=False`.
- **CORS does not apply** (that's browser-only; this is a server-to-server client).
- This pairs naturally with the scraper, which must run where you can do the one-time
  interactive LinkedIn login (MFA) — i.e. your machine — so the whole importer runs there too.

**Mode B — co-located: the importer runs as a container inside the prod compose.**
- Add an `importer` service on `app-network`; set `MAVROV_API_URL=http://backend:8000` and it
  reaches the backend **directly, internally** (no TLS, never traverses the public internet).
- Still sends `X-Import-Token` (defense in depth). Downside: the scraper needs a Chromium +
  a logged-in LinkedIn session in that environment, which is heavier headless — so in practice
  scrape on your machine (Mode A) and reserve Mode B for a pre-scraped `posts_data.json`.

**Deployment prerequisite (both modes):** set `LINKEDIN_IMPORT_TOKEN` on the **backend** service
in `docker-compose.prod.yml` (via the host `.env`) so `settings.linkedin_import_token` is
populated in prod, and give the importer the **same** value. Generate a strong random token
(e.g. `openssl rand -hex 32`); never commit it. Because the image bytes are downloaded by the
importer (using the LinkedIn session) and uploaded to prod, **the prod backend never needs any
LinkedIn access** for images.

## Component 2 — Scraper updates (`scraper/`)
- **Fix image extraction** in `scrape-posts.js`: capture the **post's own image(s)** (the
  media attached to the activity), not the author's profile photo. Support multiple images →
  emit `imageUrls: string[]` (keep `imageUrl` = first, for back-compat).
- **Capture** the original post date/time as a machine-usable value (`postedAt`, ISO 8601 if
  derivable from the DOM/Voyager payload; otherwise keep the human `time` string too) and the
  `url` permalink and `urn`.
- **Add npm script** `scrape:posts` (and `scrape:posts:debug` with `HEADLESS=false`) to
  `scraper/package.json`.
- **Stable output contract** for `posts_data.json` (array of):
  ```json
  {
    "urn": "urn:li:activity:7434116504088055808",
    "url": "https://www.linkedin.com/feed/update/urn:li:activity:.../",
    "content": "full post text …",
    "imageUrls": ["https://media.licdn.com/…", "…"],
    "imageUrl": "https://media.licdn.com/…",
    "postedAt": "2026-07-04T10:12:00Z",
    "time": "2 days ago • Edited • Visible to anyone",
    "language": "en"
  }
  ```
- **Be gentle / stay stable** (avoid tripping LinkedIn anti-bot or risking the account):
  reuse the saved session (don't re-login each run), scroll/paginate with small randomized
  delays, cap total posts per run (`SCRAPE_MAX_POSTS`, e.g. 50), and back off on rate-limit
  signals. Prefer LinkedIn's Voyager JSON payload (stable) over hashed DOM classes.
- Do not commit real scraped data or sessions (`session.json`, `.chrome-profile/`,
  `posts_data.json` with live content must stay git-ignored — confirm `.gitignore`).

## Component 3 — Standalone importer agent (`importer/`)
A new top-level directory (proposed name `importer/`), **separate from `agents/`**. It is a
plain process (CLI + optional scheduled loop), not an A2A server, with no dependency on the
A2A team.

- **Recommended language: Python** (reuses the repo's httpx/pytest stack and can be covered by
  tests; the architect may choose Node instead — see Open decisions).
- **Flow (one run):**
  1. Obtain posts: either invoke `npm run scrape:posts` in `scraper/` (subprocess) or read an
     existing `scraper/posts_data.json`. Config flag selects which.
  2. **Normalize** each post's text per the rules in §1c; derive tags; skip empty posts.
  3. **Detect language** (en/de — the site is bilingual) with a lightweight heuristic/lib and
     set `language` accordingly (falls back to `IMPORT_DEFAULT_LANGUAGE`). This matters: it
     drives the `(slug, language)` uniqueness and the semantic-search language filter.
  4. For each post: download each image URL **using the scraper's LinkedIn session cookies**
     (LinkedIn media often needs auth) → raw bytes + content-type.
  5. Process posts **oldest → newest** so blog order and IDs come out chronological; send
     `posted_at` so the displayed date is the original one.
  6. `POST /api/linkedin/import-post` (multipart) with the fields + image bytes and the
     `X-Import-Token`.
  7. Record success/skip/failure per URN; print a **run summary** (created/updated/skipped/
     failed counts) and exit non-zero if any post hard-failed, so a cron wrapper can alert.
- **Stability requirements:**
  - **Idempotent** end-to-end: safe to run repeatedly; relies on the endpoint's URN upsert and
    also keeps a local processed-URN ledger (e.g. `importer/state.json`) to skip unchanged posts.
  - **Retries** with backoff on network/5xx; a single failing post must not abort the batch.
  - **Structured logging** (per-post: urn, action=created|updated|skipped|failed, reason);
    never log the import token or session cookies.
  - **Non-destructive**: if a LinkedIn post is later edited it **updates** the existing post;
    if it's deleted on LinkedIn the importer **never deletes** the mavrov.de post (one-way sync).
  - **Config via env** (see below); no secrets committed.
  - Runnable as: `python -m importer` (one-shot), `--watch <seconds>` scheduled loop, and
    **`--dry-run`** (does everything except the POST — logs exactly what it *would* send).
    `--dry-run` is the safe way to validate against prod. A Dockerfile/compose service is
    **optional** (nice-to-have), not required for v1.
- **"Other info" (Phase 2, optional):** the same agent can push profile/CV updates by reusing
  the existing `GET /api/linkedin/profile-sync` mechanism — keep this out of v1 unless trivial;
  note it as a follow-up so the design leaves room for it.

## Config / environment
Backend (`backend/app/config.py`, all via env, none committed):
- `LINKEDIN_IMPORT_TOKEN` → `settings.linkedin_import_token` (machine auth for `/import-post`).
- `IMPORT_MAX_IMAGE_MB` (default 10) — image size cap for the ingest endpoint.

Importer (`importer/`, via env):
- `MAVROV_API_URL` (e.g. `http://localhost:8000` / prod URL)
- `LINKEDIN_IMPORT_TOKEN` (must match backend)
- `SCRAPER_DIR` (path to `scraper/`), `RUN_SCRAPER` (bool), `POSTS_JSON` (path)
- `IMPORT_DEFAULT_LANGUAGE` (default `en`), `IMPORT_PUBLISH` (default false)
- `SCRAPE_MAX_POSTS` (cap per run), `IMPORT_RETRIES` / `IMPORT_BACKOFF` (retry policy)

## Acceptance criteria (testable)
Backend:
- [ ] `POST /api/linkedin/import-post` with a valid `X-Import-Token`, `content`, `urn`, and an
      `image` file → `201/200`, creates a **draft** post whose image is served from
      `GET /api/posts/{id}/image` (local blob), and `display_image_url` points at our domain
      (not `media.licdn.com`).
- [ ] **Text-only post** (no `image`) with `content` + `urn` imports successfully with its
      **full body intact** — the image is optional, the text is not.
- [ ] Posting the **same `urn` twice** results in **one** post (second call returns
      `created:false` and updates in place). No duplicate rows.
- [ ] Missing/blank/incorrect `X-Import-Token` **and** no admin JWT → `401`. A blank configured
      token never authenticates.
- [ ] An oversized image → `413`; a non-image upload → `415`.
- [ ] `posted_at`, `source_url`, `source_urn` are persisted and returned/queryable.
- [ ] Existing `/transfer-post(s)`, `/posts`, and all other endpoints are unaffected.
- [ ] New/changed backend code has tests; **backend coverage stays at the project bar (100%,
      gate floor 95%)**.

Content:
- [ ] A raw sample containing `hashtag\n#Foo` and a zero-width char imports as clean text —
      **no literal `hashtag` token, no zero-width chars** — with paragraph breaks preserved.
- [ ] Hashtags become `tags` (deduped, `#` stripped, capped at 5, `LinkedIn` retained).
- [ ] A reshare with empty commentary is **skipped** (no empty post created).

Scraper:
- [ ] `npm run scrape:posts` exists and writes `posts_data.json` matching the contract above.
- [ ] For a post with an attached image, `imageUrls[0]` is the **post's** media URL, **not** the
      profile photo. A parse unit test asserts this against a captured fixture payload.

Importer:
- [ ] A one-shot run against a **mocked** backend + fixture `posts_data.json` imports every post
      exactly once, downloads images (mocked), and logs a per-post result.
- [ ] A failing single post (mocked 500) is retried, then skipped, and the run **continues** and
      exits non-zero-but-reported (batch not aborted).
- [ ] A second run over the same input imports **nothing new** (idempotent via ledger + URN upsert).
- [ ] The importer imports **nothing from, and has no import/dependency on, `agents/`**.

## Test strategy — how all of this gets verified
A layered pyramid; **nothing in the automated layers ever touches live LinkedIn or live prod.**

**1. Backend endpoint + model + migration — pytest, gate-enforced (the primary deliverable).**
- FastAPI `TestClient` + the existing test DB/`conftest.py`; mock `get_embedding` (Ollama) as
  current tests do. Mirror the multipart image-upload tests already in `backend/tests/`.
- Cover: image import → local blob served at `/api/app/posts/{id}/image`; **text-only** import;
  **idempotent** upsert (same `urn` twice → one row, `created:false`); auth matrix (valid token,
  blank token rejected, bad token → 401, JWT path); image `413`/`415`; `posted_at`/`source_url`/
  `source_urn` persisted; existing endpoints unaffected. Coverage stays 100% (gate floor 95%).

**2. Content normalization — pytest, gate-enforced (pure function, table-driven).**
- Feed the real dirty sample (`hashtag\n#Foo`, zero-width chars from `posts_data.json`) → assert
  clean text, tags derived (deduped, capped 5), empty reshare skipped.

**3. Scraper (Node) — unit test, NOT gate-enforced.**
- Refactor parse/normalize into a **pure function**; unit-test it (node:test/vitest) against a
  **captured** Voyager/DOM fixture (saved JSON, never live): assert `imageUrls[0]` is the post's
  media (not the profile photo), `postedAt`/`urn`/`url` parsed. The browser-driving part
  (login/scroll) isn't unit-testable — smoke it manually with `npm run scrape:posts:debug`.

**4. Importer — pytest with mocked HTTP, NOT gate-enforced.**
- Mock the backend (httpx `MockTransport`/`respx`) and image downloads; drive from a fixture
  `posts_data.json`. Cover: one POST per post; retry-then-continue on 500 (batch not aborted,
  reported exit code); idempotent ledger (2nd run sends nothing); language detection;
  oldest→newest ordering; run-summary counts; normalization applied; a guard test asserting the
  importer has **no import of `agents/`**.

**5. Local end-to-end — manual/optional, no LinkedIn.**
- Bring the stack up locally (`docker compose up -d db backend`, or full compose), set
  `LINKEDIN_IMPORT_TOKEN`, and run the importer against `http://localhost:8000` with a small
  **fixture** `posts_data.json` (skip the real scrape via `RUN_SCRAPER=false`). Verify drafts
  appear with local images through the admin UI / `GET /api/app/posts`.

**6. Prod validation — safe by construction.**
- First `--dry-run` against `https://mavrov.de` (logs what it would send; posts nothing).
- Then a single throwaway post (e.g. `urn:test:…`): it's created as a **draft**
  (`published=false`) so it's invisible publicly; verify via admin, then delete it.
- Idempotency + one-way non-destructive sync mean a real run is safe to repeat; imports never
  auto-publish, so a mistake is never public.

**CI note:** the team's deterministic gate runs **backend pytest + frontend vitest** only —
layers 1–2 are enforced there. Layers 3–4 (scraper + importer) must be **added as their own
CI jobs** (e.g. `node --test scraper/`, `pytest importer/`) so they don't rot outside the gate.

## Notes / constraints
- Reuse existing patterns, don't reinvent: embeddings via `app.services.embeddings.get_embedding`;
  local image storage exactly like `upload_post_image`/`get_post_image` in `backend/app/api/posts.py`;
  slug-uniqueness retry as already written in `posts.py`.
- Imported posts are **drafts** — the human publishes after review. Do not auto-publish.
- Secrets only via env; never commit tokens, cookies, sessions, or scraped content.
- Keep `agents/` untouched.

## Open decisions for review (please confirm before the team runs this)
1. **Importer language** — Python (recommended: reuses httpx/pytest, testable) vs Node
   (co-located with the scraper). → _Recommend Python._
2. **Endpoint auth** — dedicated machine token `X-Import-Token` (recommended, stable for an
   unattended agent) vs reuse admin JWT login only. → _Recommend the machine token, with JWT
   also accepted._
3. **Images: store bytes locally** (recommended — renders reliably on mavrov.de, model already
   supports it) vs keep external `media.licdn.com` URL (breaks over time). → _Recommend local bytes._
4. **Multiple images per post** — v1 stores the **first** image (model holds one blob); extra
   images appended into content as markdown, or deferred to Phase 2? → _Recommend first-image
   in v1, note the rest as follow-up._
5. **Original post date** — set the blog post's displayed date to LinkedIn's `posted_at`
   (recommended) or to import time? → _Recommend `posted_at`._
6. **"Other info" (profile/CV sync)** — include in v1 or defer to Phase 2 via the existing
   `profile-sync`? → _Recommend defer to Phase 2._

<!-- Saved to specs/inbox/ so it is NOT auto-processed until you run `python -m agents.intake`.
     Review/adjust, resolve the Open decisions above, then run the intake to hand it to the team. -->


---
## Intake result (2026-07-06 15:28)
- branch: `agent/import-linkedin-posts`
- gate green: True
- outcome: opened PR: pull request create failed: GraphQL: Title is too long (maximum is 256 characters) (createPullRequest)
- run log: `docs/agent-runs/import-linkedin-posts-20260706-151544.md`
