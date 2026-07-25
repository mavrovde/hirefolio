import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';
import { Buffer } from 'node:buffer';

test.describe('Admin Profile Data Management', () => {
  test.beforeEach(async ({ page }) => {
    console.log(`[E2E] Starting test: ${test.info().title}`);
    page.on('console', (msg) => console.log(`[BROWSER] ${msg.type()}: ${msg.text()}`));

    await page.addInitScript(() => {
      window.localStorage.setItem('cookie_consent', 'true');
    });

    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });

  test('uploads a per-language profile version and shows it active', async ({ page }) => {
    const testVersion = `v-${Date.now()}`;

    await page.route(`**${API_PREFIX}/admin/profile/upload*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, version: testVersion, language: 'de' }),
      });
    });

    // First load: empty; after upload: contains the new active DE version.
    let uploaded = false;
    await page.route(`**${API_PREFIX}/admin/profile/versions*`, async (route) => {
      const items = uploaded
        ? [
            {
              id: 'id-1',
              version: testVersion,
              language: 'de',
              is_active: true,
              created_at: new Date().toISOString(),
            },
          ]
        : [];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items,
          total: items.length,
          page: 1,
          page_size: 10,
          total_pages: 1,
        }),
      });
    });

    await page.goto('/profile-data');

    await page.fill('input[formControlName="version"]', testVersion);
    await page.selectOption('select', 'de');

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.click('input[type="file"]');
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'profile_data.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify({ name: 'Sergii', experience: [] })),
    });

    uploaded = true;
    await page.click('button[type="submit"]');

    await expect(page.locator('.status-success')).toBeVisible({ timeout: 15000 });
    const tbody = page.locator('table tbody');
    await expect(tbody).toContainText(testVersion);
    await expect(tbody).toContainText('DE');
    await expect(tbody.locator('.status-active')).toBeVisible();
  });

  test('activates an inactive version', async ({ page }) => {
    let activated = false;

    await page.route(`**${API_PREFIX}/admin/profile/versions/id-old/activate`, async (route) => {
      activated = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, id: 'id-old', version: 'v1', language: 'en' }),
      });
    });

    await page.route(`**${API_PREFIX}/admin/profile/versions*`, async (route) => {
      const items = [
        {
          id: 'id-old',
          version: 'v1',
          language: 'en',
          is_active: activated,
          created_at: new Date().toISOString(),
        },
        {
          id: 'id-new',
          version: 'v2',
          language: 'en',
          is_active: !activated,
          created_at: new Date().toISOString(),
        },
      ];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items, total: 2, page: 1, page_size: 10, total_pages: 1 }),
      });
    });

    await page.goto('/profile-data');

    const activateBtn = page.locator('table tbody tr', { hasText: 'v1' }).locator('button');
    await expect(activateBtn).toBeVisible({ timeout: 15000 });
    await activateBtn.click();

    // After activation v1's row becomes active (—, no button).
    await expect
      .poll(() => activated, { timeout: 15000 })
      .toBe(true);
  });
});
