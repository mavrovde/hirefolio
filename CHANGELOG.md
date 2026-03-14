# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Implemented `ssr.interceptor.ts` in Angular to properly route relative API calls during SSR (Server-Side Rendering) by correctly resolving `http://backend:8000` via the internal Docker DNS.
- Extended unit tests in Frontend to achieve 100% coverage on `blog-post.component.ts` and intercepted logic.
- Extended unit tests in Backend `app/api/posts.py` to achieve full coverage on draft permissions, image uploading logic, and retry generation cases.
- E2E Testing configuration adjusted to run Playwright tests against proper `BASE_URL` target inside local Docker environment.

### Changed

- Improved fallback SEO metadata handling in the blog component in case the post summary is missing.
- Reorganized `APP_CONFIG` interceptors to include SSR functionality implicitly without manual code workarounds.

### Security

- **CRITICAL**: Removed `NODE_TLS_REJECT_UNAUTHORIZED=0` parameter from the `frontend` container in `docker-compose.prod.yml`. The application no longer overrides Node TLS certificate validation checks; the SSR Interceptor properly avoids self-signed SSL certificate issues by rendering data directly from the unencrypted Docker DNS internal network (`http://backend:8000`).

### Fixed

- Fixed bug where blog posts were returning `302 Found` Redirects or `404 Not Found` when directly opening their URLs due to relative pathing issues during Express server-side rendering.
- Fixed `window.location` references resolving incorrectly in the Vitest frontend suite.
