import { STATIC_ROUTES, buildRobotsTxt, buildSitemapXml } from './sitemap';

/**
 * Tailored links must stay OUT of every index (#250, criterion 3).
 *
 * Kept in its own file rather than appended to `sitemap.spec.ts`: #252 is
 * rewriting that spec at the same time, and a regression this specific should
 * not be lost in a merge resolution.
 */
describe('tailored links are never advertised (#250)', () => {
    it('robots.txt disallows /for/ for the wildcard agent', () => {
        const txt = buildRobotsTxt('https://example.com');

        expect(txt).toContain('Disallow: /for/');
        // The general Allow must survive — this excludes ONE path, it does not
        // turn the site invisible.
        expect(txt).toContain('User-agent: *\nAllow: /\nDisallow: /for/');
    });

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
