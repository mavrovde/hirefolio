import { STATIC_ROUTES, SsrSiteConfig, buildRobotsTxt, buildSitemapXml } from './sitemap';

/**
 * Tailored links must stay OUT of every index (#250, criterion 3).
 *
 * Kept in its own file rather than appended to `sitemap.spec.ts` because #252
 * was rewriting that spec at the same time. #252 has since landed (#322) and
 * turned `buildRobotsTxt(siteUrl)` into `buildRobotsTxt(site)` with `/for/` in
 * its own `DISALLOWED_PATHS` list — so this file now guards the #250 invariant
 * against THAT implementation: whatever the AI-crawler policy does to the rest
 * of robots.txt, the tailored space stays excluded and no tailored URL can
 * reach the sitemap.
 */
const siteConfig = (overrides: Partial<SsrSiteConfig> = {}): SsrSiteConfig => ({
    siteUrl: 'https://example.com',
    siteName: 'Example',
    ownerName: 'Owner',
    ownerHeadline: 'Headline',
    ownerDescription: 'Description',
    availability: 'open',
    aiCrawlerPolicy: 'allow',
    ...overrides,
});

describe('tailored links are never advertised (#250)', () => {
    it.each(['allow', 'deny'] as const)(
        'robots.txt disallows /for/ for the wildcard agent (policy: %s)',
        (aiCrawlerPolicy) => {
            const txt = buildRobotsTxt(siteConfig({ aiCrawlerPolicy }));

            expect(txt).toContain('Disallow: /for/');
            // The general Allow must survive — this excludes ONE path space, it
            // does not turn the site invisible. #252's AI policy switches the
            // named-agent blocks below; it must never reach this one.
            expect(txt).toContain('User-agent: *\nAllow: /\nDisallow: /for/');
        }
    );

    it('no tailored URL can reach the sitemap', () => {
        // The sitemap is built from STATIC_ROUTES + the published posts. Neither
        // source can carry a tailored slug, and this pins that: adding /for/ to
        // STATIC_ROUTES later fails here instead of leaking a private link.
        expect(STATIC_ROUTES.map((route) => route.path)).not.toContain('/for/');
        expect(STATIC_ROUTES.some((route) => route.path.startsWith('/for'))).toBe(false);

        const xml = buildSitemapXml('https://example.com', [
            { slug: 'a-post', lastmod: '2026-01-01' },
        ]);
        expect(xml).not.toContain('/for/');
    });
});
