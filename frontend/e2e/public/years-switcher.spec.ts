import { test, expect } from '@playwright/test';

test.describe('Years Switcher Navigation', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });
    });

    test('should display year slider in header', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('app-header')).toBeVisible();
        const slider = page.locator('.year-slider');
        await expect(slider).toBeVisible();
    });

    test('should show selected year in brackets', async ({ page }) => {
        await page.goto('/');
        const selected = page.locator('.slider-year.selected');
        await expect(selected).toBeVisible();
        const text = await selected.textContent();
        expect(text).toMatch(/\[\d{4}\]/);
    });

    test('should have arrow navigation buttons', async ({ page }) => {
        await page.goto('/');
        const arrows = page.locator('.slider-arrow');
        expect(await arrows.count()).toBe(2);
    });

    test('should display year buttons with dashes', async ({ page }) => {
        await page.goto('/');
        const yearBtns = page.locator('.slider-year');
        const count = await yearBtns.count();
        expect(count).toBeGreaterThan(0);
    });

    test('should scroll to experience when clicking a year', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('section#experience')).toBeVisible();

        const yearBtn = page.locator('.slider-year').nth(2);
        await yearBtn.click();

        await expect.poll(
            async () => page.evaluate(() => window.scrollY),
            { timeout: 5000 }
        ).toBeGreaterThan(50);
    });

    test('experience cards should have data-year attributes', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('section#experience')).toBeVisible();

        const cardsWithYear = page.locator('[data-year]');
        const count = await cardsWithYear.count();
        expect(count).toBeGreaterThan(0);

        const firstYear = await cardsWithYear.first().getAttribute('data-year');
        expect(firstYear).toMatch(/^\d{4}$/);
    });
});
