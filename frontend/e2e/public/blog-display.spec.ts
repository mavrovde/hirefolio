import { test, expect } from '@playwright/test';
import { config } from '../config';

test.describe('Blog Display on Page Load', () => {
    test.beforeEach(async ({ page }) => {
        // Bypass cookie consent
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });

        // Block analytics
        await page.route('**/google-analytics.com/**', route => route.abort());
        await page.route('**/googletagmanager.com/**', route => route.abort());
    });

    test('blog section exists on home page', async ({ page }) => {
        await page.goto('/');
        await page.waitForLoadState('networkidle');

        // The blog section (#blog) should exist on the home page
        const blogSection = page.locator('#blog');
        await expect(blogSection).toBeVisible({ timeout: 10000 });
    });

    test('blog section exists on standalone /blog page', async ({ page }) => {
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        // The blog section should exist
        const blogSection = page.locator('#blog');
        await expect(blogSection).toBeVisible({ timeout: 10000 });
    });

    test('load more button fetches additional posts', async ({ page }) => {
        // First, create enough posts via admin
        await page.goto(`${config.adminUrl}/login`);
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);

        // Create 15 published posts (enough to trigger load-more after initial 10)
        for (let i = 0; i < 15; i++) {
            const uniqueId = Date.now() + i;
            await page.goto(`${config.adminUrl}/posts`);
            await page.click('.btn-new');

            await page.fill('input[id="title"]', `Blog Display E2E ${uniqueId}`);
            await page.fill('input[id="slug"]', `blog-display-e2e-${uniqueId}`);
            await page.selectOption('select[id="language"]', 'en');
            await page.fill('textarea[id="content"]', `Content for blog display test ${i}`);
            await page.fill('textarea[id="summary"]', `Summary for post ${i}`);

            // Publish the post (uses the Publish button, not a checkbox)
            await page.click('button:has-text("[ Publish ]")');
            await page.waitForURL(/\/posts/);
        }

        // Logout and visit the blog page as a visitor
        await page.click('.logout-btn');
        // Wait for logout to settle (admin origin → /login) before the cross-origin
        // navigation to the public site, so the goto below isn't interrupted mid-flight.
        await page.waitForURL(/\/login/, { timeout: 15000 });
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        // Blog posts are rendered as div.group elements inside #blog
        const blogSection = page.locator('#blog');
        await expect(blogSection).toBeVisible({ timeout: 10000 });

        // Should have posts displayed (div.group contains each post)
        const postGroups = blogSection.locator('.space-y-6 > .group');
        await expect(postGroups.first()).toBeVisible({ timeout: 10000 });

        const initialCount = await postGroups.count();
        expect(initialCount).toBe(10);

        // DEBUG: Log all API responses for posts
        page.on('response', async (response) => {
            const url = response.url();
            if (url.includes('/api/app/posts')) {
                try {
                    const body = await response.text();
                    console.log(`[E2E-DEBUG] Posts API response: ${url} status=${response.status()} body_length=${body.length} body_preview=${body.substring(0, 200)}`);
                } catch (e) {
                    console.log(`[E2E-DEBUG] Posts API response: ${url} status=${response.status()} ERROR reading body: ${e}`);
                }
            }
        });

        // DEBUG: Verify the API works directly from browser context
        const apiResult = await page.evaluate(async () => {
            try {
                const resp = await fetch('/api/app/posts?page=3&page_size=5&published_only=true&sort_by=created_at&sort_order=desc');
                const data = await resp.json();
                return { status: resp.status, total: data.total, items: data.items?.length, itemIds: data.items?.map((i: any) => i.id) };
            } catch (e: any) {
                return { error: e.message };
            }
        });
        console.log('[E2E-DEBUG] Direct fetch result:', JSON.stringify(apiResult));

        // Find the "LOAD MORE RECORDS" button and wait for it to be ENABLED.
        const loadMoreBtn = page.locator('button:has-text("LOAD MORE RECORDS")');
        await expect(loadMoreBtn).toBeVisible({ timeout: 10000 });
        await expect(loadMoreBtn).toBeEnabled({ timeout: 10000 });

        await loadMoreBtn.click();

        // Wait for the post count to increase using Playwright's auto-retrying assertion.
        const allPosts = blogSection.locator('.space-y-6 > .group');
        await expect(allPosts).toHaveCount(15, { timeout: 15000 });
    });

    test('newly created blog post shows title on public page', async ({ page }) => {
        const uniqueId = Date.now();
        const title = `E2E Title Check ${uniqueId}`;

        // Create a post via admin
        await page.goto(`${config.adminUrl}/login`);
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);

        await page.goto(`${config.adminUrl}/posts`);
        await page.click('.btn-new');
        await page.fill('input[id="title"]', title);
        await page.fill('input[id="slug"]', `e2e-title-check-${uniqueId}`);
        await page.selectOption('select[id="language"]', 'en');
        await page.fill('textarea[id="content"]', 'Title check content');
        await page.fill('textarea[id="summary"]', 'Title check summary');
        await page.click('button:has-text("[ Publish ]")');
        await page.waitForURL(/\/posts/);

        // Logout and visit blog
        await page.click('.logout-btn');
        // Wait for logout to settle (admin origin → /login) before the cross-origin
        // navigation to the public site, so the goto below isn't interrupted mid-flight.
        await page.waitForURL(/\/login/, { timeout: 15000 });
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        // The newly created post title should be visible
        const postWithTitle = page.locator('.group', { hasText: title });
        await expect(postWithTitle).toBeVisible({ timeout: 10000 });
    });

    test('post is successfully displayed when navigated directly via slug URL', async ({ page }) => {
        const uniqueId = Date.now();
        const title = `Slug Direct Load Test ${uniqueId}`;
        const slug = `slug-direct-load-${uniqueId}`;

        // Create a post via admin
        await page.goto(`${config.adminUrl}/login`);
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);

        await page.goto(`${config.adminUrl}/posts`);
        await page.click('.btn-new');
        await page.fill('input[id="title"]', title);
        await page.fill('input[id="slug"]', slug);
        await page.selectOption('select[id="language"]', 'en');
        await page.fill('textarea[id="content"]', 'Direct URL load content');
        await page.fill('textarea[id="summary"]', 'Direct URL load summary');
        await page.click('button:has-text("[ Publish ]")');
        await page.waitForURL(/\/posts/);

        await page.click('.logout-btn');
        // Wait for logout to settle (admin origin → /login) before the cross-origin
        // navigation to the public site, so the goto below isn't interrupted mid-flight.
        await page.waitForURL(/\/login/, { timeout: 15000 });

        // Regression test for #25: a *fresh* direct load of `/blog/:slug` (not an
        // in-app navigation) used to render the post via SSR and then, once the
        // client hydrated, flash/redirect back to `/` — because the client
        // re-fetched the post (the SSR HTTP transfer cache key didn't match the
        // client's request) and any transient failure of that re-fetch bounced
        // the visitor home. Track every top-level navigation of the page so we
        // can assert none of them ever went to `/`.
        const navigatedPathnames: string[] = [];
        page.on('framenavigated', (frame) => {
            if (frame === page.mainFrame()) {
                try {
                    navigatedPathnames.push(new URL(frame.url()).pathname);
                } catch {
                    // ignore about:blank / non-URL frame states
                }
            }
        });

        // Navigate directly to the slug URL to verify SSR/Routing fix
        const response = await page.goto(`/blog/${slug}`);
        await page.waitForLoadState('networkidle');

        // Check it's a 2xx response, not a 404
        expect(response?.ok()).toBeTruthy();

        // The blog post content should be visible on the loaded page
        const postTitleOnPage = page.locator('h1', { hasText: title });
        await expect(postTitleOnPage).toBeVisible({ timeout: 10000 });

        const postContentOnPage = page.getByText('Direct URL load content');
        await expect(postContentOnPage).toBeVisible({ timeout: 10000 });

        // Give the client a settle window past hydration (event replay, any
        // deferred re-fetch, etc.) and re-assert the URL and post are still
        // in place — this is exactly the "flash to home after hydration"
        // window in which the bug used to fire.
        await page.waitForTimeout(2000);

        await expect(page).toHaveURL(new RegExp(`/blog/${slug}$`));
        await expect(postTitleOnPage).toBeVisible();
        expect(navigatedPathnames).not.toContain('/');
    });
});
