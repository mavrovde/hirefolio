# Add POST /api/app/linkedin/import-post

## Summary
The core ingest endpoint: receive one LinkedIn post (text + optional image bytes), store the
image **locally**, and **upsert by URN** so re-imports don't duplicate. Depends on specs 01–03
being merged first.

## Prerequisites (must already be on main)
- 01: `Post.source_urn` (unique), `source_url`, `posted_at`.
- 02: `settings.linkedin_import_token`, `settings.import_max_image_mb`.
- 03: `normalize_linkedin_text`, `extract_hashtags` in `services/linkedin.py`.

## Contract / behaviour
`POST /api/app/linkedin/import-post` — `multipart/form-data` (router `/linkedin` under
`settings.api_prefix` = `/api/app`; add to `backend/app/api/linkedin.py`).
- **Auth:** header `X-Import-Token` compared to `settings.linkedin_import_token` with
  `secrets.compare_digest` (blank token never authenticates), **or** an admin JWT
  (`get_current_admin_user`). Never log the token.
- **Form fields:** `content` (str, required), `urn` (str, required → `source_urn`),
  `title` (optional; default = first ~60 chars of content on a word boundary),
  `summary` (optional; default = first ~200 chars), `language` (optional, default `"en"`),
  `posted_at` (ISO 8601, optional), `source_url` (optional),
  `tags` (optional CSV; default from `extract_hashtags(content)` + `"LinkedIn"`, capped 5),
  `published` (bool, default `false`), `image` (file, optional).
- **Behaviour:** run `content` through `normalize_linkedin_text` before storing. **Upsert by
  `urn`:** if a `Post` with that `source_urn` exists → update content/summary/image/posted_at/
  source_url and regenerate embedding (`get_embedding`); else create a new **draft** post. Store
  image bytes into `image_blob`/`image_type` (like `upload_post_image`). Slug from title with the
  existing random-suffix uniqueness retry.
- **Image validation:** allowlist `image/jpeg|png|webp|gif` else `415`; enforce
  `import_max_image_mb` else `413`.
- **Responses:** `200 {"id","slug","created": bool,"message"}`; `401` bad/missing token & no JWT;
  `413`/`415` image; `422` missing required fields.

## Acceptance criteria (testable)
- [ ] Valid token + `content` + `urn` + image → 200, draft created, image served at
      `GET /api/app/posts/{id}/image`, `display_image_url` points at our domain.
- [ ] Text-only (no image) imports with full body intact.
- [ ] Same `urn` twice → one row (`created:false` on the 2nd), no duplicate.
- [ ] Missing/blank/wrong token and no JWT → 401; blank configured token never authenticates.
- [ ] Oversized image → 413; non-image type → 415.
- [ ] `content` is normalized (no literal `hashtag`/zero-width); tags derived from hashtags.
- [ ] `source_urn`/`source_url`/`posted_at` persisted; existing endpoints unaffected; suite green 100%.

## Notes / constraints
- Reuse existing patterns (embeddings, local image storage, slug retry) — see `_full-reference.md`
  §1b/§1c. Keep `/transfer-post(s)` working. Extend the autouse embedding mock in `conftest.py` to
  also patch `app.api.linkedin.get_embedding` if needed. Add tests in `backend/tests/`.
</content>


---
## Result (2026-07-08)
- Implemented directly (console mode); PR #13, merged.
- Shipped in release **v1.4.0**.
