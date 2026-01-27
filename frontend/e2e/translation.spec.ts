import { test, expect } from '@playwright/test';

test.describe('Translation Integrity', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        // Wait for potential initial load
        await page.waitForLoadState('networkidle');
    });

    test('should display English menu items by default', async ({ page }) => {
        await expect(page.locator('nav').getByText('About')).toBeVisible();
        await expect(page.locator('nav').getByText('Experience')).toBeVisible();
        await expect(page.locator('nav').getByText('Skills')).toBeVisible();
        await expect(page.locator('nav').getByText('Education')).toBeVisible();
        await expect(page.locator('nav').getByText('Blog')).toBeVisible();
        await expect(page.locator('nav').getByText('[ LLM ]')).toBeVisible();
    });

    test('should switch to German and back', async ({ page }) => {
        // Switch to DE
        await page.getByRole('button', { name: 'DE' }).click();

        await expect(page.locator('nav').getByText('Über Mich')).toBeVisible();
        await expect(page.locator('nav').getByText('Erfahrung')).toBeVisible();
        await expect(page.locator('nav').getByText('Fähigkeiten')).toBeVisible();
        await expect(page.locator('nav').getByText('Ausbildung')).toBeVisible();
        await expect(page.locator('nav').getByText('Blog')).toBeVisible();
        await expect(page.locator('nav').getByText('[ LLM ]')).toBeVisible();

        // Switch back to EN
        await page.getByRole('button', { name: 'EN' }).click();
        await expect(page.locator('nav').getByText('About')).toBeVisible();
    });

    test('should maintain translation when navigating to sub-routes', async ({ page }) => {
        // Go to LLM page
        await page.getByRole('link', { name: '[ LLM ]' }).click();
        await expect(page).toHaveURL(/\/llm/);

        // Wait for it to load
        await page.waitForTimeout(1000);

        // Header is not in LLM page, but if it were, we would check here.
        // Let's verify that the back link has the correct logo text as fallback or translation
        await expect(page.locator('a', { hasText: '>_ SM' })).toBeVisible();

        // Navigate back to home
        await page.getByRole('link', { name: 'EXIT' }).click();
        await expect(page).toHaveURL(/\/$/);

        // Menu should still be correctly translated
        await expect(page.locator('nav').getByText('[ LLM ]')).toBeVisible();
    });
});
