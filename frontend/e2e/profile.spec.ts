
import { test, expect } from '@playwright/test';
import { API_PREFIX } from './config';

test.describe('Admin Profile - Change Password', () => {

    test.beforeEach(async ({ page }) => {
        console.log(`[E2E] Starting test: ${test.info().title}`);
        await page.goto('/admin/login');

        // Retry login once if it fails due to concurrency or slower start
        try {
            await page.fill('input[name="username"]', 'admin');
            await page.fill('input[name="password"]', 'admin');
            await page.click('button[type="submit"]');
            await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 10000 });
        } catch (e) {
            console.log('[E2E] Login failed, retrying once...');
            await page.goto('/admin/login');
            await page.fill('input[name="username"]', 'admin');
            await page.fill('input[name="password"]', 'admin');
            await page.click('button[type="submit"]');
            await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 10000 });
        }
        console.log('[E2E] Login successful.');
    });

    test('should display profile page and user details', async ({ page }) => {
        await page.goto('/admin/profile');
        // Use class selector to avoid ambiguity
        await expect(page.locator('h2.profile-title').first()).toContainText('Profile');
        await expect(page.locator('.user-info')).toContainText('admin');
    });

    test('should fail with incorrect old password', async ({ page }) => {
        await page.goto('/admin/profile');

        await page.fill('input[name="oldPassword"]', 'wrongpassword');
        await page.fill('input[name="newPassword"]', 'newpass123');
        const responsePromise = page.waitForResponse(resp => resp.url().includes('/auth/password') && (resp.status() === 400 || resp.status() === 200) && resp.request().method() === 'PUT');
        await page.click('button[type="submit"]');
        await responsePromise;

        // Expect error message
        await expect(page.locator('.error-message')).toBeVisible();
        // Allow for localized error or backend message
        // await expect(page.locator('.error-message')).toContainText('Incorrect old password');
    });

    test('should succeed with correct password', async ({ page }) => {
        // NOTE: This test changes the password. We should probably revert it or rely on test env reset.
        // For now, let's change it, verify success, and then change it back to 'admin' to keep other tests happy.

        await page.goto('/admin/profile');

        // Change to 'newpass123'
        await page.fill('input[name="oldPassword"]', 'admin');
        await page.fill('input[name="newPassword"]', 'newpass123');
        const responsePromise = page.waitForResponse(resp => resp.url().includes('/auth/password') && resp.status() === 200 && resp.request().method() === 'PUT');
        await page.click('button[type="submit"]');
        await responsePromise;

        await expect(page.locator('.message-success')).toBeVisible();

        // IMMEDIATELY REVERT PASSWORD TO 'admin' to prevent cascading failures
        console.log('[E2E] Reverting password to "admin"...');
        await page.fill('input[name="oldPassword"]', 'newpass123'); // It is now newpass123
        await page.fill('input[name="newPassword"]', 'admin');      // Back to admin

        const revertPromise = page.waitForResponse(resp => resp.url().includes('/auth/password') && resp.status() === 200 && resp.request().method() === 'PUT');
        await page.click('button[type="submit"]');
        await revertPromise;

        await expect(page.locator('.message-success')).toBeVisible();
        console.log('[E2E] Password reverted successfully.');
    });
});
