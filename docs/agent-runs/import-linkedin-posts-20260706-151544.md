# Autonomous run — Implement the feature specified below (from specs/inbox/import-linkedin-posts.md). Follow the spec exactly; keep the change minimal and consistent.

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


- Started: 2026-07-06T15:15:44
- Branch: agent/import-linkedin-posts


## 15:15:44 — Setup

Isolated worktree `/tmp/mavrov-wt-agent-import-linkedin-posts` on branch `agent/import-linkedin-posts`.


## 15:17:45 — Research (researcher)

# Research Report: Import LinkedIn Posts Feature

## 1. Repository Reality — What Actually Exists

### 1a. Backend: `backend/app/api/linkedin.py`
**Observed** (`read_file`): The file has four endpoints:
- `POST /linkedin/login` — dynamic LinkedIn login (admin JWT required)
- `GET /linkedin/status` — session check (admin JWT)
- `GET /linkedin/profile-sync` — profile fetch (admin JWT)
- `GET /linkedin/posts` — fetch posts via scraper (admin JWT)
- `POST /linkedin/transfer-post` — creates a **new** `Post` every call (no dedup), stores external `image_url`, title = `content[:50]`, summary hardcoded `"Imported from LinkedIn"`, language hardcoded `"en"`, random slug suffix
- `POST /linkedin/transfer-posts` — bulk version of the above

**All endpoints require `get_current_admin_user` (JWT).** No machine-token path exists. No `source_urn`, `source_url`, or `posted_at` fields exist on `Post`.

### 1b. Backend: `backend/app/models/post.py`
**Observed** (`read_file`): `Post` already has:
- `image_blob: Mapped[Optional[bytes]]` — deferred `LargeBinary`
- `image_type: Mapped[Optional[str]]` — `String(50)`
- `display_image_url` property: returns `{api_prefix}/posts/{id}/image` if `image_type` is set, else falls back to `image_url`
- `UniqueConstraint("slug", "language", name="ux_post_slug_lang")`
- Max 5 tags enforced in `PostCreate` validator in `posts.py`

**Missing** (must be added): `source_urn`, `source_url`, `posted_at`.

### 1c. Backend: `backend/app/config.py`
**Observed** (`read_file`): `Settings` has LinkedIn email/password/cookie fields but **no** `linkedin_import_token` and **no** `import_max_image_mb`. These must be added.

### 1d. Backend: `backend/app/main.py`
**Observed** (`read_file`): All routers mount under `settings.api_prefix` = `/api/app`. The LinkedIn router mounts as `app.include_router(linkedin_router, prefix=settings.api_prefix)` — so the full public path for the new endpoint is **`/api/app/linkedin/import-post`**. The spec's acceptance criteria say `/api/linkedin/import-post` in one place but the architecture section correctly states `/api/app/linkedin/import-post`. The real prefix is `/api/app`.

### 1e. Backend: `backend/app/api/posts.py`
**Observed** (`read_file`): Contains `upload_post_image` (multipart `UploadFile`) and `get_post_image` endpoints. The upload pattern: reads `await file.read()`, stores to `post.image_blob` + `post.image_type`. The slug-uniqueness retry pattern uses a `while True` loop with `random.randint` suffix, catching `IntegrityError`. These are the exact patterns the spec says to reuse.

### 1f. Backend: `backend/app/services/auth.py`
**Observed** (`read_file`): `get_current_admin_user` depends on `get_current_user` which depends on `oauth2_scheme` (Bearer JWT). The new endpoint needs **dual auth**: either `X-Import-Token` header OR admin JWT. This requires a new dependency function — it cannot simply reuse `get_current_admin_user` as-is.

### 1g. Backend: `backend/app/services/embeddings.py`
**Observed** (`read_file`): `get_embedding(text: str) -> Optional[List[float]]` — async, calls Ollama. Already mocked globally in `backend/tests/conftest.py` via `mocker.patch("app.api.posts.get_embedding", ...)`. The new endpoint in `linkedin.py` will need its own patch path: `"app.api.linkedin.get_embedding"`.

### 1h. Backend: Migrations
**Observed** (`list_dir`): Two Alembic migrations exist under `backend/migrations/versions/`:
- `68db39a6f58e_add_image_url_to_posts.py`
- `d45b3e9ce716_add_image_blob_to_posts.py`

A **third migration** is needed to add `source_urn` (unique, nullable), `source_url` (nullable), `posted_at` (timestamptz, nullable). The `env.py` uses async Alembic with `asyncpg`. The `main.py` lifespan uses `Base.metadata.create_all` for new tables — but for the partial unique index on `source_urn`, an explicit Alembic migration is the right path.

### 1i. Backend: Test Infrastructure
**Observed** (`read_file` of `backend/conftest.py` and `backend/tests/conftest.py`):
- `conftest.py` (root): mocks `tiktoken`, `langchain`, `pgvector`, `crewai` before any app import. `MockVector` is a `UserDefinedType` subclass.
- `tests/conftest.py`: `client` fixture overrides `get_db`, `get_current_admin_user`, `get_current_user_optional`, `get_current_user` with a mock admin. **The new endpoint's dual-auth dependency must be patchable** — the test for the token path needs a `clean_client` (no auth override) or a custom fixture.
- `mock_embedding_global` autouse fixture patches both `app.services.embeddings.get_embedding` and `app.api.posts.get_embedding`. The new endpoint in `linkedin.py` imports `get_embedding` directly, so tests must also patch `app.api.linkedin.get_embedding`.
- `test_posts_image_scenarios.py`: shows the image endpoint test pattern.
- Coverage is enforced at 100% (gate floor 95%).

### 1j. Scraper: `scraper/scrape-posts.js`
**Observed** (`read_file`): 
- **Bug confirmed**: `imageUrl` is extracted from `.update-components-image__image, .ivm-view-attr__img--centered` — but the `posts_data.json` shows all `imageUrl` values are the **profile photo URL** (`profile-displayphoto-scale_100_100`), not post media. The selector is either wrong or falls back to the profile photo.
- `urn` extracted from `data-urn` attribute on the container.
- `time` extracted from `.update-components-actor__sub-description .visually-hidden`.
- **No `postedAt` ISO field** — only human-readable `time` string.
- **No `language` field** in output.
- `package.json` scripts: only `scrape` and `scrape:debug` (pointing to `scrape-linkedin.js`, not `scrape-posts.js`). **`scrape:posts` script is missing.**

### 1k. Scraper: `scraper/posts_data.json` (live sample)
**Observed** (`read_file`): Confirms the dirty text format:
```
…guiding signal amidst the AI noise?\n​\nhashtag\n#EngineeringManagement \nhashtag\n#SoftwareArchitecture …
```
Zero-width space (`​` = U+200B) present. Literal `hashtag\n` before each tag. This is the exact normalization input the spec describes.

### 1l. Scraper: `.gitignore`
**Not yet read** — spec says `session.json`, `.chrome-profile/`, `posts_data.json` must be git-ignored. Need to verify.

### 1m. `agents/` directory
**Observed** (`list_dir`): Exists. Spec says **do not touch**. Confirmed out of scope.

---

## 2. External References

### 2a. FastAPI `UploadFile` + `Form` multipart
The spec requires `multipart/form-data` with both form fields and a file. FastAPI supports this via `Form(...)` + `UploadFile` parameters in the same endpoint function. **Cannot mix P


## 15:18:54 — Specification (spec-analyst)

# Requirements & Acceptance Criteria: Import LinkedIn Posts

**Feature:** `specs/inbox/import-linkedin-posts.md`
**Analyst read:** `backend/app/api/linkedin.py`, `backend/app/models/post.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/api/posts.py`, `backend/app/services/auth.py`, `backend/tests/conftest.py`, `backend/tests/api/test_api_linkedin.py`, `backend/tests/api/test_linkedin.py`, `backend/tests/test_posts_image_scenarios.py`, `backend/migrations/versions/d45b3e9ce716_*`, `backend/migrations/env.py`, `scraper/scrape-posts.js`, `scraper/package.json`, `scraper/posts_data.json`, `scraper/.gitignore`

---

## 1. Concrete Requirements

### 1A — Backend: Model additions (`backend/app/models/post.py`)

**R-M1.** Add three nullable columns to `Post`, all backward-compatible (existing rows get `NULL`):
- `source_urn: Mapped[Optional[str]]` — `String(255)`, nullable, **partial unique index** (unique where not null). This is the idempotency key.
- `source_url: Mapped[Optional[str]]` — `String(512)`, nullable. The LinkedIn permalink.
- `posted_at: Mapped[Optional[datetime]]` — `DateTime(timezone=True)`, nullable. The original LinkedIn publish time.

**R-M2.** Provide an Alembic migration under `backend/migrations/versions/` (revision chained after `d45b3e9ce716`) that adds these three columns and the partial unique index on `source_urn`. The migration must be reversible (`downgrade()`). The `env.py` already uses async Alembic — follow the same pattern exactly.

**R-M3.** The `main.py` lifespan uses `Base.metadata.create_all` for new tables but does **not** create partial indexes — the Alembic migration is the authoritative path for the index. No inline migration code in `main.py` for these columns.

---

### 1B — Backend: Config additions (`backend/app/config.py`)

**R-C1.** Add to `Settings`:
- `linkedin_import_token: str = ""` — the machine auth secret. Empty string = disabled (token path blocked).
- `import_max_image_mb: int = 10` — image size cap in MB for the ingest endpoint.

Both are read from env, never committed.

---

### 1C — Backend: New endpoint (`backend/app/api/linkedin.py`)

**R-E1. Route:** `POST /linkedin/import-post` (full public path: `POST /api/app/linkedin/import-post`). Content-type: `multipart/form-data`. Added to the existing `linkedin_router` — no new router, no new file.

**R-E2. Auth — dual path (new dependency function, not a reuse of `get_current_admin_user` as-is):**
- Path A: `X-Import-Token` header present → compare with `settings.linkedin_import_token` using `secrets.compare_digest` (constant-time). If `settings.linkedin_import_token` is empty/blank, this path is **always rejected** regardless of what header value is sent. Never log the token value.
- Path B: valid admin JWT (reuse `get_current_admin_user` / `get_current_user_optional`).
- If neither path authenticates → `401 {"detail": "Not authenticated"}`.
- The dependency must be a standalone async function (e.g. `require_import_auth`) so it is independently patchable in tests.

**R-E3. Form fields:**

| Field | Type | Required | Default / Notes |
|---|---|---|---|
| `content` | `str` (Form) | **Yes** | Full post text |
| `urn` | `str` (Form) | **Yes** | Idempotency key → `source_urn` |
| `title` | `str` (Form) | No | First line / first 60 chars of `content`, trimmed on word boundary |
| `summary` | `str` (Form) | No | First ~200 chars of `content` |
| `language` | `str` (Form) | No | Default `"en"` |
| `posted_at` | `str` (Form) | No | ISO 8601 → parsed to `datetime` with tz |
| `source_url` | `str` (Form) | No | → `post.source_url` |
| `tags` | `str` (Form) | No | Comma-separated; default `["LinkedIn"]`; capped at 5 |
| `published` | `bool` (Form) | No | Default `False` (always draft) |
| `image` | `UploadFile` (File) | No | Post image bytes → `image_blob` + `image_type` |

**R-E4. Image validation (when `image` is provided):**
- Allowlist content-types: `image/jpeg`, `image/png`, `image/webp`, `image/gif`. Anything else → `415 Unsupported Media Type`. Trust the `content_type` from the upload, not the filename extension.
- Size cap: `settings.import_max_image_mb * 1024 * 1024` bytes. Exceed → `413 Request Entity Too Large`. Read the bytes first, then check size (consistent with how `upload_post_image` in `posts.py` works).
- Store validated bytes in `post.image_blob` and content-type in `post.image_type`.

**R-E5. Upsert logic (by `source_urn`):**
- Query `select(Post).where(Post.source_urn == urn)`.
- **Existing post found (update path):** update `content`, `summary`, `posted_at`, `source_url`; update `image_blob`/`image_type` **only if a new image was sent** (do not wipe an existing image if no image is in this request); regenerate embedding; do **not** flip `published`; do **not** create a duplicate. Return `{"id": ..., "slug": ..., "created": false, "message": "Post updated"}`.
- **No existing post (create path):** derive `title` (first line or first 60 chars, word-boundary trim), derive `summary` (first ~200 chars), parse `tags` (comma-split, strip `#`, dedupe case-insensitively, prepend `"LinkedIn"`, cap at 5), set `language`, `published=False`, `source_urn`, `source_url`, `posted_at`. Generate slug from title using the **existing random-suffix retry pattern** from `posts.py` (catch `IntegrityError` on `(slug, language)` unique constraint, retry with new suffix). Generate embedding via `get_embedding(f"{title}\n\n{content}")`. Store image bytes if provided. Return `201 {"id": ..., "slug": ..., "created": true, "message": "Post created"}`.

**R-E6. Responses:**
- Create: `201` with `{"id": int, "slug": str, "created": true, "message": str}`
- Update: `200` with `{"id": int, "slug": str, "created": false, "message": str}`
- `401` — missing/invalid auth
- `413` — image too large
- `415` — unsupported image type
- `422` — FastAPI validation (missing required fields)

**R-E7. Back-compat:** existing `/transfer-post` and `/transfer-posts` endpoints are **not modified**. They remain functional. They may have a deprecation note added in their docstring only.

**R-E8. Embedding patch path:** the new endpoint imports `get_embedding` directly into `linkedin.py` (already done for the existing endpoints). Tests must patch `"app.api.linkedin.get_embedding"` — the `mock_embedding_global` autouse fixture in `tests/conftest.py` currently only patches `app.services.embeddings.get_embedding` and `app.api.posts.get_embedding`. The new endpoint's tests must add `"app.api.linkedin.get_embedding"` to the patch set (or the autouse fixture must be extended).

---

### 1D


## 15:20:03 — Plan (planner)

# Implementation Plan: Import LinkedIn Posts

## Reality check summary (from codebase inspection)

| Observation | Impact on plan |
|---|---|
| `Post` model has `image_blob`/`image_type` + `display_image_url` but **no** `source_urn`, `source_url`, `posted_at` | Migration required |
| Last migration: `d45b3e9ce716` (adds image blob) | New migration chains after it |
| `config.py` has no `linkedin_import_token` or `import_max_image_mb` | Two new settings fields |
| `linkedin.py` router prefix is `/linkedin`, mounted at `settings.api_prefix` → full path `/api/app/linkedin/...` | Endpoint goes in existing file/router |
| `conftest.py` autouse mock patches `app.services.embeddings.get_embedding` + `app.api.posts.get_embedding` — **not** `app.api.linkedin.get_embedding` | Conftest must be extended |
| `posts_data.json` confirms `imageUrl` is the **profile photo** URL (same URL on every post) | Scraper bug confirmed |
| `scraper/package.json` has no `scrape:posts` script | Must be added |
| `scraper/.gitignore` does **not** ignore `posts_data.json` | Must add it |
| No `importer/` directory exists | New top-level directory |
| `agents/` is untouched throughout | Confirmed out of scope |

---

## Ordered task list

Tasks are sequenced so each one's dependencies are already done. Backend tasks (1–5) are the CI-gated primary deliverable. Scraper (6–7) and importer (8–10) are independent tracks that can run in parallel after task 1.

---

### TASK 1 — Backend: Model + Migration
**Owner:** Backend | **Depends on:** nothing

**Files to change:**
- `backend/app/models/post.py` — add three nullable columns
- `backend/migrations/versions/<new_rev>_add_linkedin_provenance_to_posts.py` — new migration file

**Exact model changes** (surgical, append to `Post` class before the closing of `__table_args__` / after existing columns):
```python
source_urn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=False)
source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
posted_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```
The partial unique index (`UNIQUE WHERE source_urn IS NOT NULL`) cannot be expressed as a `UniqueConstraint` in SQLAlchemy's ORM layer — it must live in the Alembic migration only (not in `__table_args__`).

**Migration** (chains `down_revision = "d45b3e9ce716"`):
```python
def upgrade():
    op.add_column("posts", sa.Column("source_urn", sa.String(255), nullable=True))
    op.add_column("posts", sa.Column("source_url", sa.String(512), nullable=True))
    op.add_column("posts", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_posts_source_urn_unique",
        "posts", ["source_urn"],
        unique=True,
        postgresql_where=sa.text("source_urn IS NOT NULL"),
    )

def downgrade():
    op.drop_index("ix_posts_source_urn_unique", table_name="posts")
    op.drop_column("posts", "posted_at")
    op.drop_column("posts", "source_url")
    op.drop_column("posts", "source_urn")
```

**Tests to add:** none for the migration itself (schema changes are covered by the endpoint tests that create/query `Post` rows with these columns). The model columns are exercised by Task 5 tests.

---

### TASK 2 — Backend: Config additions
**Owner:** Backend | **Depends on:** nothing (parallel with Task 1)

**Files to change:**
- `backend/app/config.py` — add two fields to `Settings`

```python
# LinkedIn import
linkedin_import_token: str = ""
import_max_image_mb: int = 10
```

**Tests to add:**
- `backend/tests/test_config.py` already exists — add two assertions: `settings.linkedin_import_token` defaults to `""`, `settings.import_max_image_mb` defaults to `10`. (Pure attribute checks, no DB needed.)

---

### TASK 3 — Backend: Conftest patch extension
**Owner:** Backend | **Depends on:** nothing (parallel with Tasks 1–2)

**Files to change:**
- `backend/tests/conftest.py` — extend `mock_embedding_global` autouse fixture to also patch `"app.api.linkedin.get_embedding"`

**Why:** the new endpoint calls `get_embedding` imported directly into `linkedin.py`. Without this patch the test suite would attempt a real Ollama call and fail. This is a one-line addition to the existing `mocker.patch` block.

**Tests to add:** none — this is infrastructure for Task 5's tests.

---

### TASK 4 — Backend: Content normalization utility
**Owner:** Backend | **Depends on:** nothing (pure function, no DB)

**Files to change:**
- `backend/app/api/linkedin.py` — add a module-level pure function `normalize_linkedin_text(raw: str) -> tuple[str, list[str]]` that returns `(clean_text, tags)`.

**Normalization rules (exactly per spec):**
1. Strip zero-width / bidi chars: `\u200b \u200e \u200f \ufeff`; normalize `\u00a0` → space.
2. Remove LinkedIn's literal `hashtag\n` label before each tag (regex: `hashtag\s*\n`).
3. Collapse 3+ consecutive blank lines → double newline (paragraph break).
4. Strip leading/trailing whitespace.
5. Extract hashtags from cleaned text: find all `#Word` tokens, strip `#`, dedupe case-insensitively, prepend `"LinkedIn"`, cap at 5.

**Helper functions also added to `linkedin.py`:**
- `_derive_title(content: str, explicit: str | None) -> str` — first non-empty line or first 60 chars trimmed on word boundary; fallback `"LinkedIn Post"`.
- `_derive_summary(content: str, explicit: str | None) -> str` — first ~200 chars.
- `_parse_posted_at(value: str | None) -> datetime | None` — `datetime.fromisoformat` with UTC fallback; returns `None` on parse error.

**Tests to add** (new file `backend/tests/test_linkedin_normalization.py`, pure unit, no DB, no HTTP):
```
test_normalize_removes_hashtag_label          # "hashtag\n#Foo" → no "hashtag" token
test_normalize_removes_zero_width_chars       # \u200b stripped
test_normalize_preserves_paragraph_breaks     # double \n preserved
test_normalize_collapses_excess_blank_lines   # 4 blank lines → 1 paragraph break
test_normalize_extracts_tags_deduped_capped   # >5 hashtags → 5 tags, LinkedIn prepended
test_normalize_empty_text_returns_empty       # "" → ("", ["LinkedIn"])
test_derive_title_first_line                  # multiline → first line
test_derive_title_60_char_word_boundary       # long single line → trimmed at word
test_derive_title_fallback                    # blank content → "LinkedIn Post"
test_derive_summary_200_chars                 # truncates at ~200
test_parse_posted_at_valid_iso               # parses correctly
test_parse_posted_at_invalid_returns_none    # bad string → None
```
These are table-driven, fast, zero-dependency — they directly satisfy the spec's "content normalization — pytest, gate-enforced" requirement.

---

### TASK 5 — Backend: New `/import-post` endpoint
**Owner:** Backend | **Depends on:** Tasks


## 15:21:23 — Design (architect)

# Technical Design: Import LinkedIn Posts into mavrov.de

## Reality baseline (observed from codebase)

| Fact | Source |
|---|---|
| `Post` has `image_blob`/`image_type`/`display_image_url` but **no** `source_urn`, `source_url`, `posted_at` | `backend/app/models/post.py` |
| Last migration `d45b3e9ce716` adds image blob; chains from `68db39a6f58e` | `backend/migrations/versions/` |
| `config.py` has no `linkedin_import_token` or `import_max_image_mb` | `backend/app/config.py` |
| LinkedIn router prefix `/linkedin` mounted at `settings.api_prefix` → full path `/api/app/linkedin/...` | `backend/app/main.py` |
| `conftest.py` autouse mock patches `app.services.embeddings.get_embedding` and `app.api.posts.get_embedding` — **not** `app.api.linkedin.get_embedding` | `backend/tests/conftest.py` |
| `posts_data.json` confirms `imageUrl` is the **profile photo** (identical URL on every post) | `scraper/posts_data.json` |
| `scraper/package.json` has only `scrape` / `scrape:debug` scripts | `scraper/package.json` |
| `scraper/.gitignore` does **not** ignore `posts_data.json` | `scraper/.gitignore` |
| Image upload/serve pattern exists: `PUT /posts/{id}/image` → `image_blob`+`image_type`; `GET /posts/{id}/image` → blob response | `backend/tests/image_tests/test_api_posts_image.py` |
| `agents/` is a separate A2A team; must remain untouched | `agents/` directory |
| nginx routes `location /api/app/ → http://backend:8000/api/app/`; backend has **no published port** | `proxy/default.conf`, `docker-compose.prod.yml` |
| Two existing LinkedIn test files: `tests/api/test_api_linkedin.py` (sync TestClient) and `tests/api/test_linkedin.py` (async httpx) — both use mock DB sessions | `backend/tests/api/` |

---

## Affected components

```
backend/app/models/post.py                  ← 3 new nullable columns
backend/migrations/versions/<new>.py        ← Alembic migration (chains d45b3e9ce716)
backend/app/config.py                       ← 2 new settings fields
backend/app/api/linkedin.py                 ← normalization helpers + new endpoint
backend/tests/conftest.py                   ← extend autouse mock to cover linkedin module
backend/tests/test_config.py                ← 2 new assertions
backend/tests/test_linkedin_normalization.py ← new, pure-unit, no DB
backend/tests/api/test_linkedin_import.py   ← new, endpoint integration tests
scraper/scrape-posts.js                     ← fix imageUrl bug + add postedAt + imageUrls[]
scraper/package.json                        ← add scrape:posts / scrape:posts:debug scripts
scraper/.gitignore                          ← add posts_data.json
importer/                                   ← new top-level directory (Python)
  __main__.py, client.py, normalize.py,
  language.py, ledger.py, config.py,
  tests/
```

`agents/` — **zero changes**.

---

## Component 1 — Backend model + migration

### 1a. Model changes (`backend/app/models/post.py`)

Three nullable columns appended to `Post` after the existing `embedding` column:

```
source_urn  : Optional[str]      String(255), nullable, no ORM-level unique constraint
source_url  : Optional[str]      String(512), nullable
posted_at   : Optional[datetime] DateTime(timezone=True), nullable
```

**Why no `UniqueConstraint` in `__table_args__`:** SQLAlchemy's `UniqueConstraint` applies unconditionally. A partial unique index (`UNIQUE WHERE source_urn IS NOT NULL`) cannot be expressed there — it must live exclusively in the Alembic migration as a `postgresql_where` index. Adding a full unique constraint would break existing rows that all have `source_urn = NULL` (they would collide). The ORM layer therefore carries no uniqueness declaration; the DB enforces it only for non-null values.

### 1b. Migration (`backend/migrations/versions/<rev>_add_linkedin_provenance_to_posts.py`)

```
down_revision = "d45b3e9ce716"

upgrade():
  add_column posts.source_urn  String(255) nullable
  add_column posts.source_url  String(512) nullable
  add_column posts.posted_at   DateTime(tz) nullable
  create_index "ix_posts_source_urn_unique"
    on posts(source_urn), unique=True,
    postgresql_where="source_urn IS NOT NULL"

downgrade():
  drop_index  "ix_posts_source_urn_unique"
  drop_column posts.posted_at
  drop_column posts.source_url
  drop_column posts.source_urn
```

Existing rows: all three columns default to NULL — fully backward compatible.

---

## Component 2 — Config additions (`backend/app/config.py`)

Two new fields in `Settings`, both with safe defaults:

```
linkedin_import_token : str = ""    # empty → machine-token path disabled
import_max_image_mb   : int = 10    # image size cap for /import-post
```

**Security invariant:** if `linkedin_import_token == ""` the header auth path is unconditionally rejected — a blank token never authenticates. This is enforced in the endpoint, not in config.

---

## Component 3 — New endpoint (`backend/app/api/linkedin.py`)

### 3a. Pure helper functions (module-level, no I/O)

**`normalize_linkedin_text(raw: str) -> tuple[str, list[str]]`**

Transformation pipeline (order matters):
1. Strip zero-width / bidi chars: `U+200B U+200E U+200F U+FEFF`; normalize `U+00A0` → space.
2. Remove LinkedIn's literal `hashtag\n` label: regex `r"hashtag\s*\n"` → `""`.
3. Collapse 3+ consecutive blank lines → `"\n\n"` (one paragraph break).
4. Strip leading/trailing whitespace.
5. Extract hashtags: `re.findall(r"#(\w+)", cleaned)`, dedupe case-insensitively, prepend `"LinkedIn"`, cap list at 5.

Returns `(clean_text, tags)`. Pure function — no side effects, fully unit-testable.

**`_derive_title(content: str, explicit: str | None) -> str`**

If `explicit` is non-empty → use it. Else: take first non-empty line; if longer than 60 chars, trim at last word boundary before char 60. Fallback: `"LinkedIn Post"`.

**`_derive_summary(content: str, explicit: str | None) -> str`**

If `explicit` is non-empty → use it. Else: first ~200 chars of content, trimmed at word boundary.

**`_parse_posted_at(value: str | None) -> datetime | None`**

`datetime.fromisoformat(value)` with UTC fallback; returns `None` on any parse error. Never raises.

### 3b. Endpoint contract

```
POST /api/app/linkedin/import-post
Content-Type: multipart/form-data
```

**Auth (dual-path, evaluated in order):**
1. Header `X-Import-Token` present → `secrets.compare_digest(header_value, settings.linkedin_import_token)`. Passes only if both are non-empty and equal. Token value is **never logged**.
2. Else → fall through to `get_current_admin_user` (existing JWT dependency). If that also fails → `401`.

**Form fields:**

| Field | Type | Required | Default |
|---|---|---|---|
|


## 15:22:26 — Stories (story-writer)

Now I have a thorough grounding in the actual codebase. Here are the user stories with testable acceptance criteria.

---

## User Stories: Import LinkedIn Posts into mavrov.de

---

### Story 1 — Idempotent ingest endpoint with local image storage

**As a site owner, I want a secure backend endpoint that accepts a LinkedIn post (text + image bytes) and upserts it by URN, so that I can import posts repeatedly without creating duplicates and without depending on LinkedIn's expiring image URLs.**

**Acceptance Criteria:**

- **Given** a valid `X-Import-Token` header matching `settings.linkedin_import_token`, `content`, `urn`, and a JPEG `image` file under 10 MB,
  **When** `POST /api/app/linkedin/import-post` is called,
  **Then** the response is `201` with `{"id": <int>, "slug": <str>, "created": true, "message": "Post created"}`, the post is saved as a draft (`published=false`), `image_blob` is populated, and `GET /api/app/posts/{id}/image` returns the image bytes with the correct content-type (not a `media.licdn.com` URL).

- **Given** the same `urn` is posted a second time (with or without a new image),
  **When** `POST /api/app/linkedin/import-post` is called again,
  **Then** the response is `200` with `{"created": false, "message": "Post updated"}`, there is exactly **one** row in the database for that `urn`, and `published` is not changed.

- **Given** a valid token and `content` + `urn` but **no** `image` field,
  **When** `POST /api/app/linkedin/import-post` is called,
  **Then** the response is `201`/`200`, the full `content` text is stored intact, and no image-related error is raised.

- **Given** `settings.linkedin_import_token` is empty **or** the `X-Import-Token` header is missing/wrong and no valid admin JWT is present,
  **When** `POST /api/app/linkedin/import-post` is called,
  **Then** the response is `401 {"detail": "Not authenticated"}`. A blank configured token never authenticates any request.

- **Given** an `image` whose `content_type` is not in `{image/jpeg, image/png, image/webp, image/gif}`,
  **When** `POST /api/app/linkedin/import-post` is called,
  **Then** the response is `415 Unsupported Media Type`.

- **Given** an `image` whose byte size exceeds `settings.import_max_image_mb * 1024 * 1024`,
  **When** `POST /api/app/linkedin/import-post` is called,
  **Then** the response is `413 Request Entity Too Large`.

- **Given** `posted_at` (ISO 8601), `source_url`, and `urn` are included in the form,
  **When** the post is created,
  **Then** `post.posted_at`, `post.source_url`, and `post.source_urn` are persisted and match the submitted values.

- **Given** the existing `/transfer-post` and `/transfer-posts` endpoints,
  **When** any existing test or client calls them,
  **Then** they continue to return `200` with their current response shape — no regression.

- **Given** the new endpoint code is merged,
  **When** the backend pytest suite runs,
  **Then** coverage remains at 100% (gate floor 95%) and all existing tests pass.

---

### Story 2 — Clean text normalisation and tag extraction

**As a site owner, I want every imported LinkedIn post's text to be clean and readable — free of LinkedIn's injected artefacts — and its hashtags automatically converted to blog tags, so that posts are publication-ready without manual cleanup.**

**Acceptance Criteria:**

- **Given** raw content containing the literal string `hashtag\n#EngineeringManagement` and a zero-width space character (`​`),
  **When** the normalisation function is applied,
  **Then** the output contains `#EngineeringManagement` with no literal `hashtag` token and no zero-width characters anywhere in the string.

- **Given** content with intentional paragraph breaks (two or more newlines between sections) and three or more consecutive blank lines in one place,
  **When** normalisation is applied,
  **Then** intentional paragraph breaks are preserved and the run of 3+ blank lines is collapsed to a single paragraph break.

- **Given** content containing `#EngineeringManagement`, `#engineeringmanagement` (duplicate, different case), `#SoftwareArchitecture`, `#Leadership`, `#AI`, and `#ProductManagement` (six hashtags total),
  **When** tags are derived,
  **Then** the resulting tag list contains `"LinkedIn"` plus at most four of the hashtag-derived tags (total ≤ 5), with `#` stripped, deduplicated case-insensitively.

- **Given** a post whose cleaned text is empty (e.g. a bare reshare with no commentary),
  **When** the importer processes it,
  **Then** no post is created or updated in the database, and the run log records `skipped:empty` for that URN.

- **Given** a `title` is not supplied in the form fields,
  **When** a new post is created,
  **Then** `post.title` is the first line of `content` (or first 60 characters trimmed on a word boundary), never an empty string.

- **Given** a `summary` is not supplied,
  **When** a new post is created,
  **Then** `post.summary` is the first ~200 characters of `content`, not the hardcoded string `"Imported from LinkedIn"`.

---

### Story 3 — Standalone importer: scrape → normalise → deliver → idempotent loop

**As a site owner, I want a standalone importer process (outside the `agents/` A2A team) that reads the scraper's output, downloads real post images, and pushes each post to the ingest endpoint — retrying on failure and never duplicating — so that I can run it on demand or on a schedule and my blog stays in sync with LinkedIn safely.**

**Acceptance Criteria:**

- **Given** a fixture `posts_data.json` with N posts and a mocked backend that returns `201` for each,
  **When** the importer is run once (`python -m importer`),
  **Then** exactly N `POST /api/app/linkedin/import-post` requests are made (one per post), each carrying the normalised text and image bytes, and the run summary reports N created, 0 failed.

- **Given** one post in the batch causes the mocked backend to return `500` on the first two attempts,
  **When** the importer processes that post,
  **Then** it retries with backoff, eventually marks that post as failed, **continues** processing the remaining posts, and exits with a non-zero exit code — the batch is not aborted.

- **Given** the importer has already run successfully over a fixture,
  **When** it is run a second time over the same fixture,
  **Then** no new `POST` requests are made (the local URN ledger prevents re-sending unchanged posts), and the run summary reports 0 created, 0 updated, N skipped.

- **Given** `--dry-run` is passed,
  **When** the importer runs,
  **Then** it logs exactly what it *would* send for each post but makes zero HTTP requests to the backend.

- **Given** the scraper's `posts_data.json` lists posts in newest-first order,
  **When** the importer processes them,
  **Then** it sends them oldest-first so blog IDs and `posted_at` values are chronological.

- **Given** the importer source code,
  **When** it is statically inspected (grep / import guard test),
  **Then** there is no `import` or `from` statement referencing anything under the `agents/` package — the importer has zero dependency on the A2A team.

- **Given** `npm run scrape:posts` is invoked in `scraper/`,
  **When** it completes,
  **Then** it writes `posts_data.json` whose entries each contain `urn`, `url`, `content`, `imageUrls` (array), `imageUrl` (first element, the post's own media — not the author's profile photo), `postedAt` (ISO 8601), and `time`.

- **Given** a post with an attached image in the scraper fixture,
  **When** the scraper's parse function is unit-tested against that fixture,
  **Then** `imageUrls[0]` resolves to the post's media URL, not the author's profile photo URL.

---

Handoff:
- Did: Produced 3 user stories (ingest endpoint, text normalisation, standalone importer) with full Given/When/Then acceptance criteria, grounded in the actual codebase (`backend/app/api/linkedin.py`, `backend/app/models/post.py`, `backend/app/config.py`, `scraper/scrape-posts.js`, `scraper/package.json`, `backend/tests/conftest.py`, `backend/tests/api/test_api_linkedin.py`, `backend/tests/test_posts_image_scenarios.py`).
- Files: none modified (BA output only)
- Verified: All referenced paths, field names, route prefixes (`/api/app`), existing test patterns, and model capabilities confirmed by reading the actual files before writing criteria.
- Next: Engineering can take Story 1 (endpoint + model migration), Story 2 (normalisation pure function), and Story 3 (scraper fix + importer scaffold) as three parallel workstreams. Open decisions in the spec (Python vs Node for importer, first-image-only in v1) should be confirmed by the architect before implementation begins — recommended answers are already stated in the spec.


## 15:23:02 — Implement (backend) (backend-dev)

I have enough context. Here is the complete, minimal, surgical implementation.

---

## What I'll do (in order)

1. **`backend/app/models/post.py`** — add 3 nullable columns  
2. **`backend/migrations/versions/a1b2c3d4e5f6_add_linkedin_provenance_to_posts.py`** — Alembic migration  
3. **`backend/app/config.py`** — 2 new settings fields  
4. **`backend/tests/conftest.py`** — extend autouse mock to patch `app.api.linkedin.get_embedding`  
5. **`backend/app/api/linkedin.py`** — normalization helpers + `/import-post` endpoint  
6. **`backend/tests/test_config.py`** — 2 new assertions  
7. **`backend/tests/test_linkedin_normalization.py`** — pure-unit normalization tests (new file)  
8. **`backend/tests/api/test_linkedin_import.py`** — endpoint integration tests (new file)  

Then run the full test suite and verify 100% coverage.

---


## 15:24:07 — Implement (frontend) (frontend-dev)

Looking at the codebase, this spec is **backend-only** (the spec explicitly says "Frontend UI changes — Out of scope"). My role is Angular/frontend engineer, so let me be precise about what the frontend actually needs here.

---

## Frontend Assessment: Import LinkedIn Posts

### What the spec says about frontend

> **Out of scope:** Frontend UI changes (the existing admin "transfer" UI may keep calling the old endpoints; no new UI is required). Rendering already works via `/api/posts/{id}/image`.

**The frontend requires zero changes to satisfy this spec.** Here is why, grounded in what I observed:

| Concern | Reality | Action |
|---|---|---|
| New `/import-post` endpoint | Called by the standalone importer (server-to-server), not the browser | None |
| Image rendering | `display_image_url` already returns `/api/app/posts/{id}/image` when `image_type` is set; the existing `PostListResponse`/`PostResponse` models already surface this | None |
| New `source_urn`, `source_url`, `posted_at` columns | Not displayed in any current UI component; admin list shows `created_at` | None |
| Existing `/transfer-post` UI | Spec says keep it working (back-compat); backend preserves it | None |
| Draft posts | Already handled — admin can see drafts via `published_only=false`; no new UI needed | None |

### What would be needed IF a frontend task were scoped

If a future ticket adds UI for the import flow, the minimal touches would be:

1. **`PostService`** — add `importPost(formData: FormData): Observable<ImportPostResponse>` calling `POST /api/app/linkedin/import-post` with multipart.
2. **Admin post list** — surface `source_urn` / `posted_at` columns (read-only display).
3. **Vitest specs** — 100% coverage on the new service method (mock `HttpClient`, assert correct URL + headers).

But **none of that is in scope for this spec**, and adding it now would violate the "minimal, correct changes" rule.

### Verdict

**No frontend files to touch. No Vitest tests to add.** The implementation is entirely backend + scraper + importer. Handing off to the backend engineer.

---

Handoff:
- Did: Assessed the spec against the actual frontend codebase; confirmed zero frontend changes are required or in scope
- Files: none
- Verified: Spec §Scope "Out" explicitly excludes frontend UI; `display_image_url` already routes local blobs correctly; existing admin UI keeps working via unchanged endpoints
- Next: Backend engineer implements Tasks 1–5 (model/migration, config, conftest, normalization helpers, `/import-post` endpoint + tests); scraper engineer handles Tasks 6–7; importer engineer handles Tasks 8–10. Frontend is ready when those are done.


## 15:26:17 — Test gate (attempt 1)

[backend] PASS
   100%
backend/app/api/tags.py                 52      0   100%
backend/app/api/years.py                51      0   100%
backend/app/config.py                   30      0   100%
backend/app/database.py                 10      0   100%
backend/app/logger.py                    6      0   100%
backend/app/main.py                    114      0   100%
backend/app/models/__init__.py           4      0   100%
backend/app/models/cv_document.py       13      0   100%
backend/app/models/cv_request.py        20      0   100%
backend/app/models/post.py              32      0   100%
backend/app/models/user.py              16      0   100%
backend/app/services/__init__.py         0      0   100%
backend/app/services/ai.py             220      1    99%   50
backend/app/services/auth.py            70      0   100%
backend/app/services/chat.py            30      0   100%
backend/app/services/email.py           43      0   100%
backend/app/services/embeddings.py      15      0   100%
backend/app/services/linkedin.py       116      0   100%
backend/app/services/multi_chat.py     154      0   100%
------------------------------------------------------------------
TOTAL                                 1865      2    99%
Coverage HTML written to dir htmlcov
Required test coverage of 95% reached. Total coverage: 99.89%
================== 606 passed, 7 skipped in 128.88s (0:02:08) ==================


> **Critical decision (15:26:17):** Deterministic test gate (≥95% coverage): GREEN.


## 15:26:28 — Code review (code-reviewer)

It looks like the diff wasn't attached to your message. **Please paste the diff** (or describe the implementation) you'd like reviewed, and I'll get straight into it — the codebase context is already loaded.

---
Handoff:
- Did: Attempted to begin review; codebase structure loaded and ready
- Files: none
- Verified: n/a
- Next: Awaiting the actual diff from the user — please paste it in your next message


## 15:26:34 — Security review (security-reviewer)

I'll need to see the diff to review it. It looks like the diff content wasn't included in your message.

Could you please paste the diff you'd like me to review? Once you share it, I'll:

1. **Read the relevant source files** to understand the surrounding context
2. **Check for injection, authz, secrets, and dependency risks**
3. **Cross-reference any new endpoints or data flows**
4. **Deliver a precise, grounded verdict** — APPROVE or REQUEST-CHANGES

Please go ahead and share the diff.

---
Handoff:
- Did: Requested the missing diff from the user
- Files: none
- Verified: n/a
- Next: User must provide the diff content; once received, full security review will proceed immediately


> **Critical decision (15:26:34):** Reviews — code: unclear, security: REQUEST-CHANGES/NO-GO => CHANGES REQUESTED.


## 15:27:34 — Documentation (documentation-writer)

I have all the information I need from the files already read. Let me produce the documentation now.


## 15:28:12 — Release decision (release-manager)

(agent 'release-manager' unavailable: HTTP Error 503: Network communication error fetching agent card from http://localhost:8021/.well-known/agent.json: )


> **Critical decision (15:28:12):** Release Manager: NO-GO — (agent 'release-manager' unavailable: HTTP Error 503: Network communication error fetching agent card from http://localh


## Critical decisions (summary)

- **15:26:17** Deterministic test gate (≥95% coverage): GREEN.
- **15:26:34** Reviews — code: unclear, security: REQUEST-CHANGES/NO-GO => CHANGES REQUESTED.
- **15:28:12** Release Manager: NO-GO — (agent 'release-manager' unavailable: HTTP Error 503: Network communication error fetching agent card from http://localh
