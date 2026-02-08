import { test, expect } from '@playwright/test';
import { API_PREFIX } from './config';
import { Buffer } from 'node:buffer';

test.describe('Admin CV Management', () => {
    test.beforeEach(async ({ page }) => {
        console.log(`[E2E] Starting test: ${test.info().title}`);
        page.on('console', msg => console.log(`[BROWSER] ${msg.type()}: ${msg.text()}`));

        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });

        // Login as admin
        console.log('[E2E] Logging in as admin...');
        await page.goto('/admin/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 15000 });
        console.log('[E2E] Login successful.');
    });

    test('should display CV requests with download status', async ({ page }) => {
        console.log('[E2E] Mocking CV requests API...');
        // Intercept requests list before navigation - added wildcard for query params
        await page.route(`**${API_PREFIX}/admin/cv/requests*`, async route => {
            console.log('[E2E] Intercepted /api/admin/cv/requests');
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    items: [{
                        id: '123',
                        name: 'Test Recruiter',
                        email: 'test@example.com',
                        company: 'Test Co',
                        message: 'Hello',
                        created_at: new Date().toISOString(),
                        consent_given: true,
                        cv_version: 'v1.0',
                        download_count: 5,
                        downloaded_at: new Date().toISOString()
                    }],
                    total: 1,
                    page: 1,
                    page_size: 10,
                    total_pages: 1
                })
            });
        });

        console.log('[E2E] Navigating to CV Manager...');
        const responsePromise = page.waitForResponse(response =>
            response.url().includes(`${API_PREFIX}/admin/cv/requests`) && response.status() === 200
        );
        await page.goto('/admin/cv-manager');
        await responsePromise;
        console.log('[E2E] Navigation and API response received.');

        // Check if we are on the CV management page
        await expect(page.locator('h1.page-title')).toContainText('CV Management');

        // Explicitly click the Requests tab to ensure it's active
        console.log('[E2E] Ensuring Requests tab is active...');
        await page.locator('button').filter({ hasText: /Requests/i }).click();

        // Verify row content including download status
        console.log('[E2E] Verifying table content...');
        const table = page.locator('table').first();
        await expect(table).toBeVisible({ timeout: 15000 });
        const tbody = table.locator('tbody');
        const row = tbody.locator('tr').first();
        await expect(row).toBeVisible({ timeout: 15000 });
        await expect(row).toContainText('Test Recruiter');
        await expect(row).toContainText('Test Co');

        // Verify Download column
        const downloadCell = row.locator('.status-cell');
        await expect(downloadCell).toContainText('YES');
        await expect(downloadCell).toContainText('Count: 5');
        console.log('[E2E] Verification complete.');
    });

    test('should upload a new CV version', async ({ page }) => {
        const testVersion = `v2.0-${Date.now()}`;
        console.log(`[E2E] Starting upload test with version: ${testVersion}`);

        // Intercept upload request
        await page.route(`**${API_PREFIX}/admin/cv/upload*`, async route => {
            console.log('[E2E] Intercepted /api/admin/cv/upload');
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true, version: testVersion, filename: 'test-cv.pdf' })
            });
        });

        // Intercept versions list to include the new version
        await page.route(`**${API_PREFIX}/admin/cv/versions*`, async route => {
            console.log('[E2E] Intercepted /api/admin/cv/versions');
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    items: [{
                        version: testVersion,
                        filename: 'test-cv.pdf',
                        created_at: new Date().toISOString(),
                        is_active: true
                    }],
                    total: 1,
                    page: 1,
                    page_size: 10,
                    total_pages: 1
                })
            });
        });

        console.log('[E2E] Navigating to CV Manager...');
        await page.goto('/admin/cv-manager');

        console.log('[E2E] Switching to Versions tab...');
        await page.locator('button').filter({ hasText: /Versions/i }).click();

        // Fill form
        console.log('[E2E] Filling upload form...');
        await page.fill('input[formControlName="version"]', testVersion);

        // Mock file selection (Playwright approach)
        const fileChooserPromise = page.waitForEvent('filechooser');
        await page.click('input[type="file"]');
        const fileChooser = await fileChooserPromise;
        await fileChooser.setFiles({
            name: 'test-cv.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a])
        });

        // Click upload
        console.log('[E2E] Clicking upload button...');
        await page.click('button[type="submit"]');

        // Check for success message
        console.log('[E2E] Verifying success message...');
        await expect(page.locator('.success-text')).toBeVisible({ timeout: 15000 });
        await expect(page.locator('.success-text')).toContainText(/success/i);

        // Verify version appears in list
        console.log('[E2E] Verifying version in table...');
        await expect(page.locator('tbody')).toContainText(testVersion);
        console.log('[E2E] Test complete.');
    });
});
