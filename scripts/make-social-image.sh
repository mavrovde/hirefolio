#!/usr/bin/env bash
# make-social-image.sh — regenerate the project's marketing artwork (#311).
#
# Thin repo-root entry point for `frontend/scripts/make-social-image.mjs`. The
# renderer lives under `frontend/` because it drives the workspace's own
# Playwright Chromium (`frontend/node_modules`); this wrapper is what a forker
# runs, from the repo root, alongside the other `scripts/*.sh` self-checks.
#
# Outputs (all committed):
#   docs/assets/social-preview.png            1280x640  GitHub Settings -> Social preview
#                                                       + the README hero banner
#   docs/assets/social-preview-thumbnail.png   320x160  legibility evidence (a link unfurl)
#   frontend/projects/public/src/assets/og-image.png
#                                             1200x630  the site's og:image / twitter:image
#
# Re-brand it for your own fork (nothing here is baked into the renderer):
#   BRAND_NAME=Yourfolio BRAND_HOST=yourfolio \
#   BRAND_TAGLINE="what your product does" \
#   BRAND_FEATURES="one,two,three" \
#   BRAND_URL=github.com/you/yourfolio bash scripts/make-social-image.sh
#
# Then upload docs/assets/social-preview.png at
#   GitHub -> Settings -> General -> Social preview -> Upload an image...
# (GitHub exposes no API for that setting; it is the one manual step.)
set -eu
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules/playwright ]; then
  echo "✗ frontend/node_modules/playwright is missing — run 'npm ci' in frontend/ first." >&2
  exit 1
fi

exec node scripts/make-social-image.mjs "$@"
