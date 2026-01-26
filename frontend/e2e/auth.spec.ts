import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should login successfully with admin credentials', async ({ page }) => {
    // Enable request logging
    page.on('request', (request) => console.log('>>', request.method(), request.url()));
    page.on('response', (response) => console.log('<<', response.status(), response.url()));

    await page.goto('/admin/login');

    // Check if we are on the login page
    await expect(page.locator('input[name="username"]')).toBeVisible();

    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');

    // Expect to be redirected to dashboard
    await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 15000 });
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/admin/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'wrongpass');
    await page.click('button[type="submit"]');

    // Expect error message with correct selector
    await expect(page.locator('.error-message')).toContainText('Incorrect username or password');
  });

  test('should persist authentication on page reload', async ({ page }) => {
    page.on('console', (msg) => console.log('PAGE LOG:', msg.text()));

    await page.goto('/admin/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 15000 });

    // Reload the page
    await page.reload();

    // Should still be on dashboard, not redirected to login
    await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 15000 });
  });
});
