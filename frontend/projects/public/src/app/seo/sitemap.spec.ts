import { describe, it, expect, vi, afterEach } from 'vitest';
import {
    buildRobotsTxt,
    buildSitemapXml,
    createJsonFetcher,
    escapeXml,
    fetchPublishedPosts,
    JsonFetcher,
    renderRobotsTxt,
    renderSitemapXml,
    requestOrigin,
    resolveSiteUrl,
    SSR_BACKEND_ORIGIN,
    stripTrailingSlash,
} from './sitemap';

const CONFIG_PATH = '/api/app/config/site';
const postsPath = (page: number) =>
    `/api/app/posts?published_only=true&page=${page}&page_size=100`;

/** A fetcher answering from a path→payload map; unmapped paths reject like a 404 would. */
const fetcherFor = (routes: Record<string, unknown>): JsonFetcher =>
    vi.fn(async (path: string) => {
        if (!(path in routes)) {
            throw new Error(`unexpected ${path}`);
        }
        return routes[path];
    });

describe('escapeXml / stripTrailingSlash', () => {
    it('escapes every XML metacharacter', () => {
        expect(escapeXml(`a&b<c>d"e'f`)).toBe('a&amp;b&lt;c&gt;d&quot;e&apos;f');
    });

    it('strips trailing slashes and surrounding whitespace', () => {
        expect(stripTrailingSlash('  https://example.com//  ')).toBe('https://example.com');
        expect(stripTrailingSlash('https://example.com')).toBe('https://example.com');
    });
});

describe('requestOrigin', () => {
    it('prefers the forwarded proto/host injected by the proxy', () => {
        expect(
            requestOrigin(
                { 'x-forwarded-proto': 'https', 'x-forwarded-host': 'mavrov.de', host: 'frontend' },
                'http',
            ),
        ).toBe('https://mavrov.de');
    });

    it('takes the first hop when a header carries a chain', () => {
        expect(
            requestOrigin(
                { 'x-forwarded-proto': 'https, http', 'x-forwarded-host': 'outer.example, frontend' },
                'http',
            ),
        ).toBe('https://outer.example');
    });

    it('unwraps repeated headers delivered as arrays', () => {
        expect(
            requestOrigin({ 'x-forwarded-proto': ['https'], 'x-forwarded-host': ['a.example'] }, 'http'),
        ).toBe('https://a.example');
    });

    it('falls back to the express protocol and Host header', () => {
        expect(requestOrigin({ host: 'localhost:4000' }, 'http')).toBe('http://localhost:4000');
    });

    it('falls back to localhost when there is no host at all', () => {
        expect(requestOrigin({}, 'http')).toBe('http://localhost');
    });
});

describe('createJsonFetcher', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('requests the backend origin and returns the parsed body', async () => {
        const json = vi.fn().mockResolvedValue({ site_url: 'https://example.com' });
        const fetchSpy = vi.fn().mockResolvedValue({ ok: true, status: 200, json });
        vi.stubGlobal('fetch', fetchSpy);

        await expect(createJsonFetcher()(CONFIG_PATH)).resolves.toEqual({
            site_url: 'https://example.com',
        });
        expect(fetchSpy).toHaveBeenCalledWith(`${SSR_BACKEND_ORIGIN}${CONFIG_PATH}`, {
            headers: { accept: 'application/json' },
        });
    });

    it('rejects on a non-2xx response so the caller can degrade', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: vi.fn() }));

        await expect(createJsonFetcher('http://other:9000')(CONFIG_PATH)).rejects.toThrow('503');
    });
});

describe('resolveSiteUrl', () => {
    it('uses the configured SITE_URL, normalized', async () => {
        const fetchJson = fetcherFor({ [CONFIG_PATH]: { site_url: 'https://example.com/' } });
        await expect(resolveSiteUrl(fetchJson, 'http://localhost')).resolves.toBe('https://example.com');
    });

    it('falls back to the request origin when the backend is unreachable', async () => {
        const fetchJson: JsonFetcher = vi.fn().mockRejectedValue(new Error('ECONNREFUSED'));
        await expect(resolveSiteUrl(fetchJson, 'https://forked.example/')).resolves.toBe(
            'https://forked.example',
        );
    });

    it.each([[{}], [{ site_url: '' }], [null]])(
        'falls back when the payload carries no site_url (%#)',
        async (payload) => {
            const fetchJson = fetcherFor({ [CONFIG_PATH]: payload });
            await expect(resolveSiteUrl(fetchJson, 'http://localhost')).resolves.toBe('http://localhost');
        },
    );
});

describe('fetchPublishedPosts', () => {
    it('collects slugs and lastmod dates across every page', async () => {
        const fetchJson = fetcherFor({
            [postsPath(1)]: {
                total_pages: 2,
                items: [{ slug: 'first', created_at: '2026-01-02T10:00:00+00:00' }],
            },
            [postsPath(2)]: { total_pages: 2, items: [{ slug: 'second', created_at: '2026-02-03' }] },
        });

        await expect(fetchPublishedPosts(fetchJson)).resolves.toEqual([
            { slug: 'first', lastmod: '2026-01-02' },
            { slug: 'second', lastmod: '2026-02-03' },
        ]);
    });

    it('skips slugless items and omits lastmod when created_at is absent', async () => {
        const fetchJson = fetcherFor({
            [postsPath(1)]: { items: [{ created_at: '2026-01-02' }, { slug: 'only' }] },
        });

        await expect(fetchPublishedPosts(fetchJson)).resolves.toEqual([{ slug: 'only' }]);
    });

    it.each([[{ items: [] }], [null]])(
        'treats a payload without items as no posts (%#)',
        async (payload) => {
            await expect(fetchPublishedPosts(fetcherFor({ [postsPath(1)]: payload }))).resolves.toEqual(
                [],
            );
        },
    );

    it('stops at the page cap even if the backend reports more pages', async () => {
        const fetchJson: JsonFetcher = vi
            .fn()
            .mockResolvedValue({ total_pages: 999, items: [{ slug: 'p' }] });

        await expect(fetchPublishedPosts(fetchJson)).resolves.toHaveLength(20);
        expect(fetchJson).toHaveBeenCalledTimes(20);
    });

    it('degrades to no posts when the API fails', async () => {
        const fetchJson: JsonFetcher = vi.fn().mockRejectedValue(new Error('boom'));
        await expect(fetchPublishedPosts(fetchJson)).resolves.toEqual([]);
    });
});

describe('buildSitemapXml', () => {
    it('lists the static routes and every post against the configured domain', () => {
        const xml = buildSitemapXml('https://example.com/', [
            { slug: 'hello-world', lastmod: '2026-02-03' },
            { slug: 'no-date' },
        ]);

        expect(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>\n<urlset')).toBe(true);
        for (const loc of [
            'https://example.com/',
            'https://example.com/blog',
            'https://example.com/cv',
            'https://example.com/llm',
            'https://example.com/blog/hello-world',
            'https://example.com/blog/no-date',
        ]) {
            expect(xml).toContain(`<loc>${loc}</loc>`);
        }
        expect(xml).toContain('<lastmod>2026-02-03</lastmod>');
        // The dateless post must not emit an empty <lastmod/>.
        expect(xml.match(/<lastmod>/g)).toHaveLength(1);
        expect(xml).not.toContain('mavrov.de');
        expect(xml.trimEnd().endsWith('</urlset>')).toBe(true);
    });

    it('escapes XML metacharacters in a slug', () => {
        expect(buildSitemapXml('https://example.com', [{ slug: 'a&b' }])).toContain(
            '<loc>https://example.com/blog/a&amp;b</loc>',
        );
    });
});

describe('buildRobotsTxt', () => {
    it('welcomes the AI crawlers and points at the configured sitemap', () => {
        const txt = buildRobotsTxt('https://example.com/');

        expect(txt).toContain('User-agent: *\nAllow: /');
        for (const agent of ['GPTBot', 'ChatGPT-User', 'Google-Extended', 'CCBot', 'anthropic-ai',
            'Claude-Web', 'PerplexityBot', 'YouBot']) {
            expect(txt).toContain(`User-agent: ${agent}`);
        }
        expect(txt).toContain('Sitemap: https://example.com/sitemap.xml');
        expect(txt).not.toContain('mavrov.de');
    });
});

describe('render* (the shape the Express routes serve)', () => {
    it('renders robots.txt from the live config', async () => {
        const fetchJson = fetcherFor({ [CONFIG_PATH]: { site_url: 'https://forked.example' } });
        await expect(renderRobotsTxt(fetchJson, 'http://localhost')).resolves.toContain(
            'Sitemap: https://forked.example/sitemap.xml',
        );
    });

    it('renders sitemap.xml from the live config and post list', async () => {
        const fetchJson = fetcherFor({
            [CONFIG_PATH]: { site_url: 'https://forked.example' },
            [postsPath(1)]: { total_pages: 1, items: [{ slug: 'hello', created_at: '2026-02-03' }] },
        });

        const xml = await renderSitemapXml(fetchJson, 'http://localhost');
        expect(xml).toContain('<loc>https://forked.example/</loc>');
        expect(xml).toContain('<loc>https://forked.example/blog/hello</loc>');
    });
});
