import { test, expect } from '@playwright/test';

test.describe('AI Suggestions Flow', () => {
  test.setTimeout(180000); // AI can be slow

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('cookie_consent', 'true');
    });
    // Login first
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/dashboard');
  });

  test('should suggest all fields from content', async ({ page }) => {
    await page.goto('/posts/new');

    const content =
      'This is a test post about Artificial Intelligence and how it is changing the software development world in 2026.';
    await page.fill('textarea[id="content"]', content);

    // Click "Suggest All from Content"
    await page.click('button[title="Suggest Title, Slug, and Summary from content"]');

    // Wait for results
    await expect(page.locator('input[id="title"]')).not.toHaveValue('', { timeout: 300000 });
    await expect(page.locator('input[id="slug"]')).not.toHaveValue('', { timeout: 10000 });
    await expect(page.locator('textarea[id="summary"]')).not.toHaveValue('', { timeout: 10000 });

    expect(await page.inputValue('input[id="title"]')).toBeTruthy();
  });

  test('should suggest title individually', async ({ page }) => {
    await page.goto('/posts/new');
    await page.fill('textarea[id="content"]', 'AI and Future');

    await page.click('button[title="Suggest title from content"]');
    await expect(page.locator('input[id="title"]')).not.toHaveValue('', { timeout: 300000 });
    expect(await page.inputValue('input[id="title"]')).toBeTruthy();
  });

  test('should suggest summary individually', async ({ page }) => {
    await page.goto('/posts/new');
    await page.fill('textarea[id="content"]', 'AI and Future');

    await page.click('button[title="Suggest summary from content"]');
    await expect(page.locator('textarea[id="summary"]')).not.toHaveValue('', { timeout: 300000 });
    expect(await page.inputValue('textarea[id="summary"]')).toBeTruthy();
  });

  test('should suggest tags from title and content', async ({ page }) => {
    await page.goto('/posts/new');

    await page.fill('input[id="title"]', 'Future of AI');
    await page.fill('textarea[id="content"]', 'AI is evolving rapidly.');

    await page.click('button[title="Generate tags with AI"]');

    await page.waitForSelector('.tag-chip', { timeout: 300000 });
    const tagsCount = await page.locator('.tag-chip').count();
    expect(tagsCount).toBeGreaterThan(0);
  });
});
