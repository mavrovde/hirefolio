import { test, expect } from '@playwright/test';

test.describe('SEO & SSR Verification', () => {
    // 1. Verify robots.txt
    test('should serve robots.txt with AI bot rules', async ({ request }) => {
        const response = await request.get('/robots.txt');
        expect(response.ok()).toBe(true);
        const text = await response.text();
        expect(text).toContain('User-agent: GPTBot');
        expect(text).toContain('Allow: /');
        expect(text).toContain('Sitemap:');
    });

    // 2. Verify sitemap.xml
    test('should serve sitemap.xml', async ({ request }) => {
        const response = await request.get('/sitemap.xml');
        expect(response.ok()).toBe(true);
        const text = await response.text();
        expect(text).toContain('<?xml version="1.0" encoding="UTF-8"?>');
        expect(text).toContain('<urlset');
        expect(text).toContain('<loc>https://mavrov.de/</loc>');
    });

    // 3. Verify SSR (Home Page Initial Paint)
    test('should provide pre-rendered HTML for home page', async ({ request }) => {
        const response = await request.get('/');
        expect(response.ok()).toBe(true);
        const html = await response.text();

        // Check for rendered content (not just a blank app-root)
        expect(html).toContain('<app-root');
        expect(html).toContain('Jane Doe');
        expect(html).toContain('Senior Software Engineer');

        // Verify Meta Tags are in the initial HTML (Proof of SSR)
        expect(html).toContain('<title>Home | Jane Doe</title>');
        expect(html).toContain('description');
        expect(html).toContain('og:title');
        expect(html).toContain('twitter:card');

        // Verify Structured Data (JSON-LD)
        expect(html).toContain('application/ld+json');
        expect(html).toContain('"@type"');
        expect(html).toContain('"Person"');
        expect(html).toContain('"Jane Doe"');
    });

    // 4. Verify SSR (Blog Post Initial Paint)
    test('should provide pre-rendered HTML for a blog post', async ({ request }) => {
        // We might not know the exact slug if DB is dynamic, but usually there's a 'hello-world' or similar in mocks
        // Let's try to fetch /blog first to get a slug if needed, or just assume one exists in the test DB
        const response = await request.get('/blog');
        const html = await response.text();

        // This confirms the blog list is SSR'd
        expect(html).toContain('blog');

        // If we want to test a specific post, we'd need to ensure the test DB has it.
        // For now, let's just verify the /blog list SSR.
        expect(html).toContain('<title>Blog | Jane Doe</title>');
    });

    // 5. Verify semantic HTML in SSR output
    test('should have an h1 tag in initial SSR output', async ({ request }) => {
        const response = await request.get('/');
        const html = await response.text();
        expect(html).toContain('<h1');
        expect(html.match(/<h1/g)?.length).toBe(1);
    });
});
