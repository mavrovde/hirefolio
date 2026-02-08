import { test, expect } from '@playwright/test';
// import { LoginPage } from './pages/login-page';
import { API_PREFIX } from './config';

test.describe('Admin SQL Panel', () => {

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

    test('should execute a valid SQL query and show results', async ({ page }) => {
        await page.goto('/admin/sql');

        // Check if we are on the SQL panel
        await expect(page.locator('h2:has-text("SQL Panel")')).toBeVisible();

        // Type query
        await page.fill('#query', "SELECT 'test_value' as result_col");

        // Mock API response to avoid actual DB modification/dependency during E2E if preferred, 
        // or let it run against test DB. For E2E, usually we might want actual execution or mock.
        // Let's rely on actual execution for "SELECT 1" type queries.

        // intercept for stability verification
        const responsePromise = page.waitForResponse(resp => resp.url().includes('/sql/execute') && resp.status() === 200 && resp.request().method() === 'POST');

        // Click execute
        await page.click('button:has-text("Execute")');

        await responsePromise;

        // Check results
        await expect(page.locator('table')).toBeVisible();
        await expect(page.locator('th')).toHaveText('result_col');
        await expect(page.locator('td')).toHaveText('test_value');
    });

    test('should handle invalid SQL query', async ({ page }) => {
        await page.goto('/admin/sql');

        await page.fill('#query', "SELECT * FROM non_existent_table_123");
        await page.click('button:has-text("Execute")');

        // Expect error message
        await expect(page.locator('.border-terminal.text-primary')).toBeVisible();
        await expect(page.locator('.border-terminal.text-primary')).toContainText('SQL Execution Error');
    });
});
