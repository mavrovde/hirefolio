/**
 * The container-internal address of the backend on the compose network, used by
 * everything that talks to the API from inside the SSR process.
 *
 * It lives alone in this module because it is a DEPLOYMENT fact with two
 * independent consumers — `interceptors/ssr-http-backend.ts` (rewrites the
 * Angular app's relative API URLs during SSR) and `seo/sitemap.ts` (reads the
 * site config and post list for `sitemap.xml`/`robots.txt`). Neither can own it:
 * `sitemap.ts` is server-only, so importing it into the interceptor would drag
 * the XML renderer into the BROWSER bundle, and importing the interceptor into
 * `sitemap.ts` would put an `@Injectable` inside a deliberately DI-free module.
 * A third, dependency-free module lets both share one copy — two copies of one
 * deployment fact drift (#317 review round 1).
 *
 * Note the *test* specs deliberately keep the literal spelled out: an assertion
 * that imports the value it asserts would pass against any value.
 */
export const SSR_BACKEND_ORIGIN = 'http://backend:8000';
