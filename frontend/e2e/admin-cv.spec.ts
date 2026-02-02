import { test, expect } from '@playwright/test';

test.describe('Admin CV Management', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });

        // Login as admin
        await page.goto('/admin/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 15000 });
    });

    test('should display CV requests', async ({ page }) => {
        await page.goto('/admin/cv-manager');

        // Check if we are on the CV management page
        await expect(page.locator('h1.page-title')).toContainText('CV Management');

        // Wait for the requests table to load
        // If there are no requests, it should show "No records in database"
        const emptyRow = page.locator('.empty-row');
        const tableRows = page.locator('tbody tr');

        await expect(emptyRow.or(tableRows.first())).toBeVisible();
    });

    test('should upload a new CV version', async ({ page }) => {
        await page.goto('/admin/cv-manager');
        await page.click('button:has-text("VERSION_CONTROL.sys")');

        const testVersion = `v2.0-${Date.now()}`;

        // Intercept upload request
        await page.route('**/api/admin/cv/upload', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true, version: testVersion, filename: 'test-cv.pdf' })
            });
        });

        // Fill form
        await page.fill('input[formControlName="version"]', testVersion);

        // Mock file selection (Playwright approach)
        const fileChooserPromise = page.waitForEvent('filechooser');
        await page.click('input[type="file"]');
        const fileChooser = await fileChooserPromise;
        await fileChooser.setFiles({
            name: 'test-cv.pdf',
            mimeType: 'application/pdf',
            buffer: new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a]).buffer as any
        });

        // Click upload
        await page.click('button[type="submit"]');

        // Check for success message
        await expect(page.locator('.success-text')).toContainText('SUCCESS: CV_UPLOAD_COMPLETE');

        // Verify version appears in list
        await expect(page.locator('tbody')).toContainText(testVersion);
    });
});
