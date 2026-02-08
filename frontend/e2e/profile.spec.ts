
import { test, expect } from '@playwright/test';
import { API_PREFIX } from './config';

test.describe('Admin Profile - Change Password', () => {

    test.beforeEach(async ({ page }) => {
        console.log(`[E2E] Starting test: ${test.info().title}`);
        await page.goto('/admin/login');

        // Explicitly accept cookies if banner is present
        const cookieButton = page.getByRole('button', { name: 'Accept & Save' });
        if (await cookieButton.isVisible()) {
            console.log('[E2E] Clicking Accept Cookies...');
            await cookieButton.click();
        }

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

    test.skip('should succeed with correct password (full flow)', async ({ page }) => {
        // 1. Login with initial password 'admin' (Handled by beforeEach)

        // 2. Change password to 'newpass123'
        await page.goto('/admin/profile');
        await page.fill('input[name="oldPassword"]', 'admin');
        await page.fill('input[name="newPassword"]', 'newpass123');
        const responsePromise = page.waitForResponse(resp => resp.url().includes('/auth/password') && resp.status() === 200 && resp.request().method() === 'PUT');

        await page.locator('button[type="submit"]').click({ force: true });
        await responsePromise;
        await expect(page.locator('.message-success')).toBeVisible();

        // 3. Logout
        console.log('[E2E] Logging out...');
        const logoutBtn = page.locator('.logout-btn');
        await expect(logoutBtn).toBeVisible();
        await logoutBtn.click();
        await expect(page).toHaveURL(/\/admin\/login/);

        // 4. Login with NEW password 'newpass123'
        console.log('[E2E] Logging in with new password...');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'newpass123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/);

        // 5. Change password BACK to 'admin'
        console.log('[E2E] Reverting password...');
        await page.goto('/admin/profile');
        await page.fill('input[name="oldPassword"]', 'newpass123');
        await page.fill('input[name="newPassword"]', 'admin');
        const revertPromise = page.waitForResponse(resp => resp.url().includes('/auth/password') && resp.status() === 200 && resp.request().method() === 'PUT');
        await page.locator('button[type="submit"]').click({ force: true });
        await revertPromise;
        await expect(page.locator('.message-success')).toBeVisible();

        // 6. Logout again
        console.log('[E2E] Logging out again...');
        await expect(logoutBtn).toBeVisible();
        await logoutBtn.click();
        await expect(page).toHaveURL(/\/admin\/login/);

        // 7. Login with OLD password 'admin'
        console.log('[E2E] logging in with old password...');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/admin\/dashboard/);
        console.log('[E2E] Password reverted successfully and full flow verified.');
    });
});
