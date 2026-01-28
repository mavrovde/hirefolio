import { test, expect } from '@playwright/test';

test.describe('Design Regression Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('cookie_consent', 'true');
    });
  });

  test('should use correct terminal green colors', async ({ page }) => {
    await page.goto('/');

    // Check primary color variable if exposed, or computed style of key elements
    // Since we hardcoded primary to #00ff00

    const body = page.locator('body');
    // text-primary results in color #00ff00 (rgb(0, 255, 0))
    await expect(body).toHaveCSS('color', 'rgb(0, 255, 0)');

    // Check background is black
    await expect(body).toHaveCSS('background-color', 'rgb(0, 0, 0)');

    // Check a border terminal element if exists (e.g. header)
    const headerBorder = page.locator('.border-terminal').first();
    // Border color should be rgba(0, 255, 0, 0.3)
    // Note: computed style might return the matrix or specific rgba
    if ((await headerBorder.count()) > 0) {
      await expect(headerBorder).toHaveCSS('border-bottom-color', 'rgba(0, 255, 0, 0.3)');
    }
  });

  test('should use mono font', async ({ page }) => {
    await page.goto('/');
    const body = page.locator('body');
    await expect(body).toHaveCSS('font-family', /Courier Prime|Courier|monospace/);
  });
});
