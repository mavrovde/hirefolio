import { test, expect } from '@playwright/test';

test.describe('Admin New Features Verification', () => {

    test.beforeEach(async ({ page }) => {
        // Pre-accept cookies to prevent banner from blocking UI
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });

        // Capture browser console logs
        page.on('console', msg => console.log(`[BROWSER] ${msg.type()}: ${msg.text()}`));

        // Login sequence
        await page.goto('/admin/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        // Setup network listener
        // DEBUG: Capture login response body
        page.on('response', async response => {
            if (response.url().includes('/auth/login')) {
                console.log(`[E2E-DEBUG] Login Response Status: ${response.status()}`);
                try {
                    const body = await response.text();
                    console.log(`[E2E-DEBUG] Login Response Body: ${body}`);
                } catch (e) {
                    console.log(`[E2E-DEBUG] Failed to read body: ${e}`);
                }
            }
        });

        const loginResponsePromise = page.waitForResponse(
            resp => resp.url().includes('/auth/login'), // Wait for ANY login response, not just 200
            { timeout: 10000 }
        ).catch(() => null);

        await page.click('button[type="submit"]');

        const loginResponse = await loginResponsePromise;
        if (!loginResponse) {
            console.log('Login request failed or timed out!');
            const errorText = await page.locator('.error-message').textContent().catch(() => 'No error message');
            console.log('UI Error Message:', errorText);
        } else {
            console.log('Login request successful (200 OK)');
        }

        // Wait for ANY admin page element to ensure login success
        // 'app-admin-layout' is usually the wrapper for dashboard
        // Or check URL
        try {
            await expect(page).toHaveURL(/\/admin\/(dashboard|chat|profile|sql)/, { timeout: 15000 });
        } catch (e) {
            console.log('Navigation failed. Current URL:', page.url());
            throw e;
        }
    });

    test('Admin Chat should load and send message', async ({ page }) => {
        // Capture console logs for debugging
        page.on('console', msg => console.log(`[BROWSER] ${msg.text()}`));

        // Mock the chat API with a more robust pattern
        await page.route('**/gemini-chat', async route => {
            console.log('[E2E] Intercepted gemini-chat request');
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ response: "Hello Test Response" })
            });
        });

        await page.goto('/admin/chat');

        // Verify container visibility first
        await expect(page.locator('.bg-terminal-dark')).toBeVisible();

        // Correct input selector
        const input = page.locator('input[placeholder="Type a message..."]');
        await expect(input).toBeVisible();

        // Type and send message
        await input.fill('Hello Test');
        // Click Send button (text "Send")
        await page.locator('button', { hasText: 'Send' }).click();

        // Verify user message appears in chat
        await expect(page.locator('.whitespace-pre-wrap', { hasText: 'Hello Test' }).first()).toBeVisible();

        // Verify assistant response appears
        await expect(page.locator('.whitespace-pre-wrap', { hasText: 'Hello Test Response' }).first()).toBeVisible({ timeout: 15000 });

        // Verify input cleared
        await expect(input).toHaveValue('');
    });

    test('Profile should have show password toggle', async ({ page }) => {
        await page.goto('/admin/profile');

        // Check old password field exists
        await expect(page.locator('input[name="oldPassword"]')).toBeVisible();

        // Check new password field exists and is initially hidden (type password)
        const newPassInput = page.locator('input[name="newPassword"]');
        await expect(newPassInput).toHaveAttribute('type', 'password');

        // Find the toggle button associated with new password using ID adjacency
        const toggleBtn = page.locator('#newPassword + button');

        await expect(toggleBtn).toBeVisible();

        // Click toggle
        await toggleBtn.click();

        // Verify input type changed to text and button text to HIDE
        await expect(newPassInput).toHaveAttribute('type', 'text');
        await expect(toggleBtn).toHaveText('HIDE');

        // Toggle back
        await toggleBtn.click();
        await expect(newPassInput).toHaveAttribute('type', 'password');
    });

    test('SQL Panel should have Backup and Restore buttons', async ({ page }) => {
        await page.goto('/admin/sql');

        // Check Backup button
        const backupBtn = page.locator('button', { hasText: 'BACKUP DATABASE' });
        await expect(backupBtn).toBeVisible();

        // Check Restore button
        const restoreBtn = page.locator('button', { hasText: 'RESTORE DATABASE' });
        await expect(restoreBtn).toBeVisible();

        // Check Restore File Input exists
        const fileInput = page.locator('input#restoreFile');
        await expect(fileInput).toHaveAttribute('type', 'file');
        await expect(fileInput).toHaveAttribute('accept', '.sql');
    });
});
