import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

test.describe('Post Management', () => {
  test.setTimeout(60000); // Reduced from 300s since AI is now mocked

  test.beforeEach(async ({ page }) => {
    console.log(`[E2E] Starting test: ${test.info().title}`);

    // Mock AI tag suggestion
    await page.route(`**${API_PREFIX}/posts/suggest-tags`, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tags: ['AI', 'Tech', 'Playwright'] })
      });
    });

    // Mock AI detail suggestion (bulk and individual)
    await page.route(`**${API_PREFIX}/posts/suggest-details`, async route => {
      const data = {
        title: 'AI Suggested Title',
        slug: 'ai-suggested-slug',
        summary: 'AI suggested summary'
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(data)
      });
    });

    await page.addInitScript(() => {
      window.localStorage.setItem('cookie_consent', 'true');
    });

    console.log('[E2E] Logging in as admin...');
    await page.goto('/login');

    // Retry login once if it fails due to concurrency
    try {
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="password"]', 'admin123');
      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 30000 });
    } catch (e) {
      console.log('[E2E] Login failed, retrying once...');
      await page.goto('/login');
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="password"]', 'admin123');
      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 30000 });
    }
    console.log('[E2E] Login successful.');

    console.log('[E2E] Navigating to /posts...');
    await page.goto('/posts');
  });

  test('should create a new post', async ({ page }) => {
    await page.click('.btn-new');
    const timestamp = Date.now();
    const title = `E2E Test Post ${timestamp}`;
    const slug = `e2e-test-${timestamp}`;

    await page.fill('input[id="title"]', title);
    await page.fill('input[id="slug"]', slug);
    await page.selectOption('select[id="language"]', 'en');
    await page.fill('textarea[id="content"]', 'Test content.');
    await page.fill('textarea[id="summary"]', 'Test summary');

    await page.click('button[type="submit"]');
    await page.waitForURL('/posts');
    await expect(page.locator('table')).toContainText(title);
  });

  test('should suggest tags', async ({ page }) => {
    await page.click('.btn-new');
    await page.fill('input[id="title"]', 'AI Post');
    await page.fill('textarea[id="content"]', 'AI is the future.');

    const suggestBtn = page.getByTitle('Generate tags with AI');
    await expect(suggestBtn).toBeEnabled();

    await suggestBtn.click();
    await expect(page.locator('.tag-chip').first()).toBeVisible({ timeout: 5000 });
    expect(await page.locator('.tag-chip').count()).toBeGreaterThan(0);
  });

  test('should edit an existing post', async ({ page }) => {
    const firstEditButton = page.locator('.btn-edit').first();
    await expect(firstEditButton).toBeVisible();
    await firstEditButton.click();

    const newTitle = `Edited ${Date.now()}`;
    await page.fill('input[id="title"]', newTitle);
    await page.click('button[type="submit"]');
    await page.waitForURL('/posts');
    await expect(page.locator('table')).toContainText(newTitle);
  });

  test('should delete a post', async ({ page }) => {
    await page.click('.btn-new');
    const timestamp = Date.now();
    await page.fill('input[id="title"]', `Delete Me ${timestamp}`);
    await page.fill('input[id="slug"]', `delete-${timestamp}`);
    await page.fill('textarea[id="content"]', 'Content');
    await page.click('button[type="submit"]');
    await page.waitForURL('/posts');

    const row = page.locator('tr', { hasText: `Delete Me ${timestamp}` });
    page.on('dialog', dialog => dialog.accept());
    await row.locator('.btn-delete').click();
    await expect(row).not.toBeVisible();
  });

  test('should suggest post details (bulk and individual)', async ({ page }) => {
    await page.click('.btn-new');
    await page.fill('textarea[id="content"]', 'AI is transforming the world.');

    // Suggest All
    const suggestAllBtn = page.getByTitle('Suggest Title, Slug, and Summary from content');
    await suggestAllBtn.click();

    await expect(page.locator('input[id="title"]')).not.toHaveValue('', { timeout: 5000 });
    await expect(page.locator('input[id="slug"]')).not.toHaveValue('', { timeout: 5000 });
    await expect(page.locator('textarea[id="summary"]')).not.toHaveValue('', { timeout: 5000 });

    // Suggest Individual
    await page.fill('input[id="title"]', '');
    await page.getByTitle('Suggest title from content').click();
    await expect(page.locator('input[id="title"]')).toHaveValue('AI Suggested Title');
  });

  test('should upload image on post', async ({ page }) => {
    // Create a post first
    await page.click('.btn-new');
    const timestamp = Date.now();
    const title = `Image Test ${timestamp}`;
    const slug = `image-test-${timestamp}`;

    await page.fill('input[id="title"]', title);
    await page.fill('input[id="slug"]', slug);
    await page.fill('textarea[id="content"]', 'Image upload test content.');
    await page.click('button[type="submit"]');
    await page.waitForURL('/posts');

    // Edit the created post
    const row = page.locator('tr', { hasText: title });
    await row.locator('.btn-edit').click();

    // Upload a 1x1 red PNG
    const pngBuffer = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==',
      'base64'
    );
    const fileInput = page.locator('input#image_file');
    await fileInput.setInputFiles({
      name: 'test-image.png',
      mimeType: 'image/png',
      buffer: pngBuffer,
    });

    // Verify preview appears
    await expect(page.locator('img[alt="Preview"]')).toBeVisible({ timeout: 10000 });
    // Verify "New image selected" indicator
    await expect(page.locator('text=New image selected')).toBeVisible({ timeout: 5000 });
  });

  test('should logout', async ({ page }) => {
    await page.click('.logout-btn');
    await expect(page).toHaveURL('/login');
  });
});
