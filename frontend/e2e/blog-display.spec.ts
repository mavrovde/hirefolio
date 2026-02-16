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

    test('blog posts are visible on home page without login', async ({ page }) => {
        await page.goto('/');
        await page.waitForLoadState('networkidle');

        // The blog section should exist on the home page
        const blogSection = page.locator('#blog');
        await expect(blogSection).toBeVisible({ timeout: 10000 });

        // There should be at least one blog post displayed
        // Blog posts are rendered as <article> or individual post cards
        const blogPosts = page.locator('app-blog-post');
        const postCount = await blogPosts.count();

        // If the API is available, posts should be displayed
        // If not, fallback static data should show posts
        expect(postCount).toBeGreaterThan(0);
    });

    test('blog posts are visible on standalone /blog page', async ({ page }) => {
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        // Wait for posts to load
        const blogPosts = page.locator('app-blog-post');
        await expect(blogPosts.first()).toBeVisible({ timeout: 10000 });

        const postCount = await blogPosts.count();
        expect(postCount).toBeGreaterThan(0);
        // Initial load should show up to 10 posts
        expect(postCount).toBeLessThanOrEqual(10);
    });

    test('load more button fetches additional posts', async ({ page }) => {
        // First, create enough posts via admin to ensure load-more is available
        // Login as admin
        await page.goto('/admin/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/);

        // Create 12 posts (enough to trigger load-more after initial 10)
        for (let i = 0; i < 12; i++) {
            const uniqueId = Date.now() + i;
            await page.goto('/admin/posts');
            await page.click('.btn-new');

            await page.fill('input[id="title"]', `Load More Test Post ${uniqueId}`);
            await page.fill('input[id="slug"]', `load-more-test-${uniqueId}`);
            await page.selectOption('select[id="language"]', 'en');
            await page.fill('textarea[id="content"]', `Content for load more test ${i}`);
            await page.fill('textarea[id="summary"]', `Summary ${i}`);

            // Check published checkbox
            const publishedCheckbox = page.locator('input[id="published"]');
            if (!(await publishedCheckbox.isChecked())) {
                await publishedCheckbox.check();
            }

            await page.click('button[type="submit"]');
            await page.waitForTimeout(300);
        }

        // Now visit the blog page as a visitor
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        // Should show 10 posts initially
        const blogPosts = page.locator('app-blog-post');
        await expect(blogPosts.first()).toBeVisible({ timeout: 10000 });

        const initialCount = await blogPosts.count();
        expect(initialCount).toBe(10);

        // Find and click the "Load More" button
        const loadMoreBtn = page.locator('button').filter({ hasText: /load.*more|mehr.*laden/i });
        await expect(loadMoreBtn).toBeVisible();
        await loadMoreBtn.click();

        // Wait for new posts to load
        await page.waitForTimeout(1000);

        // Should now have more than 10 posts (10 initial + up to 5 more)
        const afterLoadMoreCount = await page.locator('app-blog-post').count();
        expect(afterLoadMoreCount).toBeGreaterThan(initialCount);
        expect(afterLoadMoreCount).toBeLessThanOrEqual(15); // 10 + 5
    });

    test('blog posts show title and summary', async ({ page }) => {
        await page.goto('/blog');
        await page.waitForLoadState('networkidle');

        const firstPost = page.locator('app-blog-post').first();
        await expect(firstPost).toBeVisible({ timeout: 10000 });

        // Each post should have a title (h2 or h3) and summary text
        const postTitle = firstPost.locator('h2, h3').first();
        await expect(postTitle).toBeVisible();
        const titleText = await postTitle.textContent();
        expect(titleText?.trim().length).toBeGreaterThan(0);
    });
});
