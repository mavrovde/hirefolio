/**
 * Config-driven `sitemap.xml` / `robots.txt` (#71).
 *
 * Both used to be STATIC files in `projects/public/public/` hardcoded to
 * `https://mavrov.de`, listing a fixed route set and no blog posts — wrong for
 * every forker and stale for this deployment. They are now rendered per request
 * by the SSR Express server (`src/server.ts`) from the runtime site config
 * (`SITE_URL`, #65) plus the live published-post list.
 *
 * The static files were DELETED on purpose: the frontend nginx does
 * `try_files $uri @ssr` (`frontend/nginx.conf`), so as long as
 * `/robots.txt` / `/sitemap.xml` existed in the browser bundle nginx would keep
 * serving those bytes and the Express routes would never run.
 *
 * Everything except the three-line Express wiring lives here so it is covered
 * by unit tests — `src/server.ts` is excluded from coverage as a
 * framework-generated bootstrap entry point.
 */

import { SSR_BACKEND_ORIGIN } from '../ssr-backend-origin';

/** Injected JSON fetcher, so the render functions are testable without network. */
export type JsonFetcher = (path: string) => Promise<unknown>;

/** Container-internal backend origin during SSR — same address `SsrHttpBackend` rewrites to. */
export { SSR_BACKEND_ORIGIN };

const API_PREFIX = '/api/app';
/** `page_size` is capped at 100 by the backend (`backend/app/api/posts.py`). */
const POSTS_PAGE_SIZE = 100;
/** Hard bound so a mis-reported `total_pages` can never loop the request forever. */
const MAX_POST_PAGES = 20;

/** Static public routes, mirroring `app.routes.ts` (`/blog/:slug` is expanded from the API). */
export const STATIC_ROUTES: readonly { path: string; changefreq: string; priority: string }[] = [
    { path: '/', changefreq: 'weekly', priority: '1.0' },
    { path: '/blog', changefreq: 'weekly', priority: '0.8' },
    { path: '/cv', changefreq: 'monthly', priority: '0.8' },
    { path: '/llm', changefreq: 'monthly', priority: '0.5' },
];

export interface SitemapPost {
    slug: string;
    lastmod?: string;
}

/** Only the fields we consume; anything else on the wire is ignored. */
interface SiteConfigWire {
    site_url?: string;
}
interface PostWire {
    slug?: string;
    created_at?: string;
}
interface PostPageWire {
    items?: PostWire[];
    total_pages?: number;
}

const XML_ESCAPES: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&apos;',
};

export function escapeXml(value: string): string {
    return value.replace(/[&<>"']/g, (char) => XML_ESCAPES[char]);
}

export function stripTrailingSlash(url: string): string {
    return url.trim().replace(/\/+$/, '');
}

/**
 * The origin this request arrived on, used only as a fallback when the backend
 * (and therefore `SITE_URL`) is unreachable — a sitemap needs ABSOLUTE URLs, so
 * "no origin at all" is not an option. Behind the two nginx layers the raw
 * `Host` is the internal service name, hence the forwarded headers first.
 */
export function requestOrigin(
    headers: Readonly<Record<string, string | string[] | undefined>>,
    protocol: string,
): string {
    const first = (value: string | string[] | undefined): string =>
        (Array.isArray(value) ? value[0] : value) ?? '';
    const proto = first(headers['x-forwarded-proto']).split(',')[0].trim() || protocol;
    const host =
        first(headers['x-forwarded-host']).split(',')[0].trim() || first(headers['host']) || 'localhost';
    return `${proto}://${host}`;
}

/**
 * Per-request bound on the SSR→backend reads below.
 *
 * A REFUSED backend rejects instantly, but a HUNG one has no bound of its own:
 * `/robots.txt` and `/sitemap.xml` would then block until nginx's
 * `proxy_read_timeout 300` (`frontend/nginx.conf`) instead of degrading to the
 * routes-only file that `resolveSiteUrl`/`fetchPublishedPosts` already fall back
 * to — the module's "degrade, never 500" contract would hold in principle and
 * fail in practice.
 *
 * 5s matches the house convention for the mirror-image call: the backend reads
 * profile JSON out of the frontend container with
 * `profile_data_timeout_seconds` (`backend/app/config.py:238`, default 5.0,
 * applied at `backend/app/api/years.py:57`). Kept a module constant rather than
 * an env knob because it bounds a container-to-container hop on the compose
 * network, where the deployment has no reason to tune it per-host.
 */
export const SSR_FETCH_TIMEOUT_MS = 5000;

/** A `fetch`-backed JSON fetcher for API paths (`/api/app/...`). */
export function createJsonFetcher(origin: string = SSR_BACKEND_ORIGIN): JsonFetcher {
    return async (path: string) => {
        const response = await fetch(`${origin}${path}`, {
            headers: { accept: 'application/json' },
            signal: AbortSignal.timeout(SSR_FETCH_TIMEOUT_MS),
        });
        if (!response.ok) {
            throw new Error(`GET ${path} failed with ${response.status}`);
        }
        return response.json();
    };
}

/** Configured `SITE_URL`, falling back to the request's own origin. */
export async function resolveSiteUrl(
    fetchJson: JsonFetcher,
    fallbackOrigin: string,
): Promise<string> {
    try {
        const config = (await fetchJson(`${API_PREFIX}/config/site`)) as SiteConfigWire | null;
        const siteUrl = stripTrailingSlash(config?.site_url ?? '');
        if (siteUrl) {
            return siteUrl;
        }
    } catch {
        // Identity degrades, the file never 500s — same contract as SiteConfigService.
    }
    return stripTrailingSlash(fallbackOrigin);
}

/** Every published post, paged. A failure yields the routes-only sitemap, never an error page. */
export async function fetchPublishedPosts(fetchJson: JsonFetcher): Promise<SitemapPost[]> {
    const posts: SitemapPost[] = [];
    try {
        let totalPages = 1;
        for (let page = 1; page <= totalPages && page <= MAX_POST_PAGES; page++) {
            const wire = (await fetchJson(
                `${API_PREFIX}/posts?published_only=true&page=${page}&page_size=${POSTS_PAGE_SIZE}`,
            )) as PostPageWire | null;
            for (const item of wire?.items ?? []) {
                if (item.slug) {
                    const lastmod = (item.created_at ?? '').slice(0, 10);
                    posts.push(lastmod ? { slug: item.slug, lastmod } : { slug: item.slug });
                }
            }
            totalPages = typeof wire?.total_pages === 'number' ? wire.total_pages : 1;
        }
    } catch {
        // A sitemap listing the static routes beats a 500 on /sitemap.xml.
    }
    return posts;
}

export function buildSitemapXml(siteUrl: string, posts: readonly SitemapPost[]): string {
    const base = stripTrailingSlash(siteUrl);
    const urls = [
        ...STATIC_ROUTES.map(
            (route) =>
                `  <url>\n` +
                `    <loc>${escapeXml(`${base}${route.path}`)}</loc>\n` +
                `    <changefreq>${route.changefreq}</changefreq>\n` +
                `    <priority>${route.priority}</priority>\n` +
                `  </url>`,
        ),
        ...posts.map(
            (post) =>
                `  <url>\n` +
                `    <loc>${escapeXml(`${base}/blog/${post.slug}`)}</loc>\n` +
                (post.lastmod ? `    <lastmod>${escapeXml(post.lastmod)}</lastmod>\n` : '') +
                `    <changefreq>monthly</changefreq>\n` +
                `    <priority>0.6</priority>\n` +
                `  </url>`,
        ),
    ];
    return (
        `<?xml version="1.0" encoding="UTF-8"?>\n` +
        `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
        `${urls.join('\n')}\n` +
        `</urlset>\n`
    );
}

/** Crawlers we explicitly welcome — classic search plus the AI search crawlers. */
const AI_CRAWLERS = [
    'GPTBot',
    'ChatGPT-User',
    'Google-Extended',
    'CCBot',
    'anthropic-ai',
    'Claude-Web',
    'PerplexityBot',
    'YouBot',
];

export function buildRobotsTxt(siteUrl: string): string {
    const base = stripTrailingSlash(siteUrl);
    const blocks = [
        'User-agent: *',
        'Allow: /',
        '',
        '# Specifically allow AI search crawlers',
        ...AI_CRAWLERS.flatMap((agent) => [`User-agent: ${agent}`, 'Allow: /', '']),
        `Sitemap: ${base}/sitemap.xml`,
    ];
    return `${blocks.join('\n')}\n`;
}

export async function renderRobotsTxt(
    fetchJson: JsonFetcher,
    fallbackOrigin: string,
): Promise<string> {
    return buildRobotsTxt(await resolveSiteUrl(fetchJson, fallbackOrigin));
}

export async function renderSitemapXml(
    fetchJson: JsonFetcher,
    fallbackOrigin: string,
): Promise<string> {
    const [siteUrl, posts] = await Promise.all([
        resolveSiteUrl(fetchJson, fallbackOrigin),
        fetchPublishedPosts(fetchJson),
    ]);
    return buildSitemapXml(siteUrl, posts);
}
