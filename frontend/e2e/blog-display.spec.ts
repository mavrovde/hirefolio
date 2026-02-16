import { test, expect } from '@playwright/test';

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
        await page.goto('/admin/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/);

        // Create 15 published posts (enough to trigger load-more after initial 10)
        for (let i = 0; i < 15; i++) {
            const uniqueId = Date.now() + i;
            await page.goto('/admin/posts');
            await page.click('.btn-new');

            await page.fill('input[id="title"]', `Blog Display E2E ${uniqueId}`);
            await page.fill('input[id="slug"]', `blog-display-e2e-${uniqueId}`);
            await page.selectOption('select[id="language"]', 'en');
            await page.fill('textarea[id="content"]', `Content for blog display test ${i}`);
            await page.fill('textarea[id="summary"]', `Summary for post ${i}`);

            // Publish the post (uses the Publish button, not a checkbox)
            await page.click('button:has-text("[ Publish ]")');
            await page.waitForURL('/admin/posts');
        }

        // Logout and visit the blog page as a visitor
        await page.click('.logout-btn');

        // Navigate to blog and intercept all posts API calls
        const apiResponses: any[] = [];
        await page.route('**/api/app/posts?**', async (route) => {
            const response = await route.fetch();
            const json = await response.json();
            apiResponses.push({ url: route.request().url(), total: json.total, itemCount: json.items?.length });
            await route.fulfill({ response });
        });

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

        // Find and click the "LOAD MORE RECORDS" button
        const loadMoreBtn = page.locator('button:has-text("LOAD MORE RECORDS")');
        await expect(loadMoreBtn).toBeVisible();

        // Set up a promise to wait for the load-more API response (page > 1)
        const loadMoreResponse = page.waitForResponse(
            resp => {
                const url = resp.url();
                if (!url.includes('/api/app/posts')) return false;
                const pageMatch = url.match(/[?&]page=(\d+)/);
                return pageMatch !== null && parseInt(pageMatch[1]) > 1 && resp.status() === 200;
            },
            { timeout: 15000 }
        );

        await loadMoreBtn.click();

        // Wait for the API response to arrive
        await loadMoreResponse;

        // Wait a bit for Angular to render the new posts
        await page.waitForTimeout(1000);

        // Should now have more than 10 posts (10 initial + up to 5 more)
        const afterLoadMoreCount = await blogSection.locator('.space-y-6 > .group').count();
        expect(afterLoadMoreCount).toBeGreaterThan(initialCount);
        expect(afterLoadMoreCount).toBeLessThanOrEqual(20); // generous upper bound
    });

    test('newly created blog post shows title on public page', async ({ page }) => {
        const uniqueId = Date.now();
        const title = `E2E Title Check ${uniqueId}`;

        // Create a post via admin
        await page.goto('/admin/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/);

        await page.goto('/admin/posts');
        await page.click('.btn-new');
        await page.fill('input[id="title"]', title);
        await page.fill('input[id="slug"]', `e2e-title-check-${uniqueId}`);
        await page.selectOption('select[id="language"]', 'en');
        await page.fill('textarea[id="content"]', 'Title check content');
        await page.fill('textarea[id="summary"]', 'Title check summary');
        await page.click('button:has-text("[ Publish ]")');
        await page.waitForURL('/admin/posts');

        // Logout and visit blog
        await page.click('.logout-btn');
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        // The newly created post title should be visible
        const postWithTitle = page.locator('.group', { hasText: title });
        await expect(postWithTitle).toBeVisible({ timeout: 10000 });
    });
});
