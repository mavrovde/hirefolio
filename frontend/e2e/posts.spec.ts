import { test, expect } from '@playwright/test';

test.describe('Post Management', () => {
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    console.log(`[E2E] Starting test: ${test.info().title}`);
    page.on('console', msg => console.log(`[BROWSER] ${msg.type()}: ${msg.text()}`));

    await page.addInitScript(() => {
      window.localStorage.setItem('cookie_consent', 'true');
    });
    // Login before each test
    console.log('[E2E] Logging in as admin...');
    await page.goto('/admin/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');

    // Auth redirect is to dashboard by default
    await expect(page).toHaveURL(/\/admin\/dashboard/);
    console.log('[E2E] Login successful.');

    // Navigate to posts list
    console.log('[E2E] Navigating to /admin/posts...');
    await page.goto('/admin/posts');
  });

  test('should create a new post', async ({ page }) => {
    console.log('[E2E] Clicking button to create new post...');
    await page.click('.btn-new');

    // Fill form
    const timestamp = Date.now();
    const title = `E2E Test Post ${timestamp}`;
    const slug = `e2e-test-${timestamp}`;
    console.log(`[E2E] Creating post with title: ${title}`);

    await page.fill('input[id="title"]', title);
    await page.fill('input[id="slug"]', slug);
    await page.selectOption('select[id="language"]', 'en');
    await page.fill('textarea[id="content"]', 'This is a test content created by Playwright.');
    await page.fill('textarea[id="summary"]', 'Test summary');

    console.log('[E2E] Submitting post form...');
    await page.click('button[type="submit"]');

    // Verify redirect to list
    await page.waitForURL('/admin/posts');
    await expect(page).toHaveURL('/admin/posts');

    // Verify post is in the list
    await expect(page.locator('table')).toContainText(title);
    console.log('[E2E] Post created successfully.');
  });

  test('should suggest tags', async ({ page }) => {
    await page.click('.btn-new');

    // Fill minimum required for suggestion
    await page.fill('input[id="title"]', 'Artificial Intelligence');
    await page.fill(
      'textarea[id="content"]',
      'Artificial intelligence (AI) is intelligence demonstrated by machines.',
    );

    // Check suggest button state
    const suggestBtn = page.getByTitle('Generate tags with AI');
    await expect(suggestBtn).toBeEnabled();

    // Setup network interception to verify data flow
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/posts/suggest-tags') && response.status() === 200,
    );

    // Click and wait for response
    await suggestBtn.click();
    await expect(page.getByText('Thinking...')).toBeVisible();

    // Verify Backend Response Payload
    const response = await responsePromise;
    const data = await response.json();
    console.log('AI Response:', data);

    expect(data).toHaveProperty('tags');
    expect(Array.isArray(data.tags)).toBe(true);
    expect(data.tags.length).toBeGreaterThan(0);

    // Wait for at least one tag chip in UI
    await expect(page.locator('.tag-chip').first()).toBeVisible({ timeout: 180000 }); // increased timeout for AI on CPU runner
    expect(await page.locator('.tag-chip').count()).toBeGreaterThan(0);
  });

  test('should edit an existing post', async ({ page }) => {
    // Ensure we have a post to edit.
    const firstEditButton = page.locator('.btn-edit').first();
    await expect(firstEditButton).toBeVisible();
    await firstEditButton.click();

    const newTitle = `Edited Title ${Date.now()}`;
    await page.fill('input[id="title"]', newTitle);
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin/posts');
    await expect(page).toHaveURL('/admin/posts');
    await expect(page.locator('table')).toContainText(newTitle);
  });

  test('should delete a post', async ({ page }) => {
    // Create a dummy post to delete
    await page.click('.btn-new');
    const timestamp = Date.now();
    await page.fill('input[id="title"]', `Delete Me ${timestamp}`);
    await page.fill('input[id="slug"]', `delete-me-${timestamp}`);
    await page.selectOption('select[id="language"]', 'en');
    await page.fill('textarea[id="content"]', 'Content to delete');
    await page.fill('textarea[id="summary"]', 'Summary');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/admin/posts');

    // Find the row with our post
    const row = page.locator('tr', { hasText: `Delete Me ${timestamp}` });
    await expect(row).toBeVisible();

    // Click delete button inside that row
    // Handling potentially window.confirm?
    // post-list uses (click)="deletePost(post)". Check if it confirms.
    // If not, it just works. If it does, we need event listener.
    // Assuming simple delete for now, if fails we add dialog handler.
    // Usually delete actions have confirmation.
    page.on('dialog', (dialog) => dialog.accept());

    await row.locator('.btn-delete').click();

    // Wait for network idle or table update
    await page.waitForTimeout(1000); // Small wait for transition

    await expect(page).toHaveURL('/admin/posts');
    await expect(page.locator('table')).not.toContainText(`Delete Me ${timestamp}`);
  });

  test('should suggest post details (bulk and individual)', async ({ page }) => {
    await page.click('.btn-new');

    // Fill content first
    const postContent =
      'The ethics of artificial intelligence is the branch of the ethics of technology specific to artificially intelligent systems.';
    await page.fill('textarea[id="content"]', postContent);

    // 1. Test "Suggest All"
    const suggestAllBtn = page.getByTitle('Suggest Title, Slug, and Summary from content');
    await expect(suggestAllBtn).toBeVisible();

    const bulkResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes('/api/posts/suggest-details') && response.status() === 200,
    );

    await suggestAllBtn.click();
    await expect(page.getByText('Thinking...')).toBeVisible();

    const bulkResponse = await bulkResponsePromise;
    const bulkData = await bulkResponse.json();
    expect(bulkData).toHaveProperty('title');
    expect(bulkData).toHaveProperty('slug');
    expect(bulkData).toHaveProperty('summary');

    // Wait for UI to update
    await expect(page.locator('input[id="title"]')).not.toHaveValue('', { timeout: 180000 });
    await expect(page.locator('input[id="slug"]')).not.toHaveValue('', { timeout: 180000 });
    await expect(page.locator('textarea[id="summary"]')).not.toHaveValue('', { timeout: 180000 });

    // 2. Test individual "Suggest" for Title
    await page.fill('input[id="title"]', ''); // Clear title
    const suggestTitleBtn = page.getByTitle('Suggest title from content');

    const titleResponsePromise = page.waitForResponse((response) => {
      const url = response.url();
      const postData = response.request().postData();
      return (
        url.includes('/api/posts/suggest-details') &&
        !!postData &&
        postData.includes('"field":"title"')
      );
    });

    await suggestTitleBtn.click();
    await expect(page.locator('input[id="title"]')).not.toHaveValue('', { timeout: 180000 });

    const titleResponse = await titleResponsePromise;
    const titleData = await titleResponse.json();
    expect(titleData).toHaveProperty('title');
  });

  test('should logout', async ({ page }) => {
    await page.click('.logout-btn');
    await expect(page).toHaveURL('/admin/login');
  });
});
