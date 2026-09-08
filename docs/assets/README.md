# Marketing artwork (#311)

Binary assets in a repo are opaque, so their provenance lives here.

| File | Size | Bytes | Where it is used |
| --- | --- | --- | --- |
| `social-preview.png` | 1280×640 | 278 KB (284,616 B) | GitHub **Settings → General → Social preview** (uploaded by hand — no API) and the README hero banner (`README.md:1`) |
| `social-preview-thumbnail.png` | 320×160 | 27 KB (27,686 B) | Legibility evidence: the same card downscaled the way a Slack/X unfurl downscales it |
| `../../frontend/projects/public/src/assets/og-image.png` | 1200×630 | 269 KB (275,794 B) | The site's `og:image`/`twitter:image` (`SeoService`, #71) — asserted live by `frontend/e2e/public/seo-ssr.spec.ts` |

## Regenerating

```bash
bash scripts/make-social-image.sh
```

The renderer is `frontend/scripts/make-social-image.mjs` (headless Chromium from the workspace's
Playwright install). It composes one picture at both sizes, then downscales the 1280×640 result for
the thumbnail. All three files above are rewritten in place; commit the diff.

Re-brand a fork with `BRAND_NAME` / `BRAND_HOST` / `BRAND_TAGLINE` / `BRAND_FEATURES` / `BRAND_URL`
(see `scripts/make-social-image.sh`). Rows that would overflow the terminal frame are shrunk to fit
automatically, so an arbitrary product name or tagline still renders inside the box.

## Design constraints (do not regress these)

- **Product identity, never a persona.** The site's hero renders `profile.name` and
  `assets/images/profile.png` from runtime config (#65), so a screenshot of the running site would
  propagate the maintainer's name and face into every fork (#66, #311). The card carries the
  product only.
- **The site's own visual language**, not a generic banner: `#33ff00` on `#050505`, VT323, matrix
  grid, scanlines, terminal prompt — cited from `frontend/projects/public/src/styles.css:3-24,27-57`
  and `frontend/projects/public/src/app/components/hero/hero.component.html:2-19`.
- **Safe area.** The meaningful content sits inside the central ~2:1 terminal frame, because GitHub,
  Slack and X each crop differently and edge text is the usual casualty.
- **No metadata.** The renderer writes `IHDR`/`IDAT`/`IEND` only — no EXIF, no author, no text
  chunks, and it fails the run if that ever stops being true. This matters because
  `scripts/check_no_pii.sh` is text-only and cannot see inside a PNG (`scripts/check_no_pii.sh:9-11`),
  so metadata leaked here would pass every gate in the repo. To re-check by hand, pipe
  `strings docs/assets/social-preview.png` through the guard's own identifier list
  (`scripts/check_no_pii.sh:15`) — deliberately not copied here, so there is one source of truth —
  and expect no output. Pixels are a separate question: the rendered content needs eyeball review
  at PR time.
- **VT323 is fetched once and cached** at `frontend/scripts/.cache/vt323.woff2` (gitignored), then
  embedded as a data URI so the render does not depend on the browser's network stack. Offline with
  a cold cache the script still succeeds, loudly warning that it fell back to Courier — that render
  is *not* what is committed here.
