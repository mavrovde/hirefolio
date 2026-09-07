import { test, expect, APIRequestContext } from '@playwright/test';

/**
 * The configured identity of the stack under test (#65/#71). Nothing here may
 * hardcode a domain or an owner: this suite runs against the demo persona in
 * CI and against a forker's own config anywhere else.
 */
async function siteConfig(request: APIRequestContext) {
    const response = await request.get('/api/app/config/site');
    expect(response.ok()).toBe(true);
    return (await response.json()) as { site_url: string; owner_name: string };
}

test.describe('SEO & SSR Verification', () => {
    // 1. robots.txt — generated from SITE_URL, still welcoming the AI crawlers
    test('should serve a config-driven robots.txt with AI bot rules', async ({ request }) => {
        const { site_url } = await siteConfig(request);
        const response = await request.get('/robots.txt');
        expect(response.ok()).toBe(true);
        const text = await response.text();

        expect(text).toContain('User-agent: GPTBot');
        expect(text).toContain('Allow: /');
        expect(text).toContain(`Sitemap: ${site_url}/sitemap.xml`);
    });

    // 2. sitemap.xml — generated from SITE_URL and the live published posts (#71)
    test('should serve a config-driven sitemap.xml listing blog posts', async ({ request }) => {
        const { site_url } = await siteConfig(request);
        const response = await request.get('/sitemap.xml');
        expect(response.ok()).toBe(true);
        const text = await response.text();

        expect(text).toContain('<?xml version="1.0" encoding="UTF-8"?>');
        expect(text).toContain('<urlset');
        for (const route of ['/', '/blog', '/cv', '/llm']) {
            expect(text).toContain(`<loc>${site_url}${route}</loc>`);
        }

        // The blog list is the source of truth for what MUST be in the sitemap.
        const posts = await request.get('/api/app/posts?published_only=true&page=1&page_size=5');
        const { items } = (await posts.json()) as { items: { slug: string }[] };
        expect(items.length).toBeGreaterThan(0);
        for (const item of items) {
            expect(text).toContain(`<loc>${site_url}/blog/${item.slug}</loc>`);
        }
    });

    // 3. Verify SSR (Home Page Initial Paint)
    test('should provide pre-rendered HTML for home page', async ({ request }) => {
        const { owner_name } = await siteConfig(request);
        const response = await request.get('/');
        expect(response.ok()).toBe(true);
        const html = await response.text();

        // Check for rendered content (not just a blank app-root)
        expect(html).toContain('<app-root');
        expect(html).toContain(owner_name);

        // Verify Meta Tags are in the initial HTML (Proof of SSR)
        expect(html).toContain(`<title>Home | ${owner_name}</title>`);
        expect(html).toContain('description');
        expect(html).toContain('og:title');
        expect(html).toContain('twitter:card');

        // Verify Structured Data (JSON-LD)
        expect(html).toContain('application/ld+json');
        expect(html).toContain('"@type"');
        expect(html).toContain('"Person"');
        expect(html).toContain(`"${owner_name}"`);
    });

    // 4. The enriched Person node crawlers actually read, in the SERVER HTML (#71)
    test('should server-render enriched Person structured data', async ({ request }) => {
        const { site_url } = await siteConfig(request);
        const html = await (await request.get('/')).text();

        const match = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
        expect(match, 'no JSON-LD block in the server-rendered HTML').not.toBeNull();
        const person = JSON.parse(match![1]) as Record<string, unknown>;

        expect(person['@context']).toBe('https://schema.org');
        expect(person['@type']).toBe('Person');
        expect(person['url']).toBe(site_url);
        for (const field of ['hasOccupation', 'knowsAbout', 'alumniOf', 'worksFor', 'address']) {
            expect(person[field], `Person.${field} missing`).toBeTruthy();
        }
        expect(person['hasOccupation']).toMatchObject({ '@type': 'Occupation' });
        expect(person['address']).toMatchObject({ '@type': 'PostalAddress' });
        expect(person['worksFor']).toMatchObject({ '@type': 'Organization' });
        // Open-to-work signal: emitted unless the owner is not looking (#71 AC5).
        expect(person['seeks']).toMatchObject({ '@type': 'Demand' });
    });

    // 5. Every public route: unique title + description + canonical + OG/Twitter (#71 AC2)
    for (const [route, path] of [
        ['/', '/'],
        ['/blog', '/blog'],
        ['/cv', '/cv'],
        ['/llm', '/llm'],
    ]) {
        test(`should server-render canonical + OG tags for ${route}`, async ({ request }) => {
            const { site_url } = await siteConfig(request);
            const html = await (await request.get(route)).text();

            expect(html).toContain(`<link rel="canonical" href="${site_url}${path}">`);
            expect(html).toContain(`<meta property="og:url" content="${site_url}${path}">`);
            expect(html).toContain(
                `<meta property="og:image" content="${site_url}/assets/og-image.png">`,
            );
            expect(html).toContain(
                `<meta name="twitter:image" content="${site_url}/assets/og-image.png">`,
            );
            expect(html).toMatch(/<meta name="description" content="[^"]+">/);
        });
    }

    // 6. The OG image must actually exist — it did not before #71
    test('should serve the referenced Open Graph image', async ({ request }) => {
        const response = await request.get('/assets/og-image.png');
        expect(response.ok()).toBe(true);
        expect(response.headers()['content-type']).toContain('image/png');
    });

    // 7. Verify SSR (Blog list Initial Paint)
    test('should provide pre-rendered HTML for a blog post', async ({ request }) => {
        const { owner_name } = await siteConfig(request);
        const html = await (await request.get('/blog')).text();

        // This confirms the blog list is SSR'd
        expect(html).toContain('blog');
        expect(html).toContain(`<title>Blog | ${owner_name}</title>`);
    });

    // 8. Verify semantic HTML in SSR output
    test('should have an h1 tag in initial SSR output', async ({ request }) => {
        const response = await request.get('/');
        const html = await response.text();
        expect(html).toContain('<h1');
        expect(html.match(/<h1/g)?.length).toBe(1);
    });
});
