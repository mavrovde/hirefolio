
import { test, expect } from '@playwright/test';

const navItems = [
    { label: 'About', hash: '#about' },
    { label: 'Experience', hash: '#experience' },
    { label: 'Skills', hash: '#skills' },
    { label: 'Education', hash: '#education' },
];

test.describe('Cross-Route Navigation', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });
    });

    // 1. Check navigation from CV page
    for (const item of navItems) {
        test(`should navigate from CV to ${item.label}`, async ({ page }) => {
            await page.goto('/cv');
            // Wait for hydration
            await expect(page.locator('app-cv')).toBeVisible();

            // Click navigation item
            await page.click(`nav >> text=${item.label}`);

            // Verify URL
            await expect(page).toHaveURL(new RegExp(`.*\\/${item.hash}`));

            // Verify section visibility
            const section = page.locator(`section${item.hash}`);
            await expect(section).toBeVisible();

            // Verify scroll happened (unless it's 'About' and resolution is huge, but usually it should be > 0)
            if (item.label !== 'About') {
                await expect.poll(async () => page.evaluate(() => window.scrollY), { timeout: 5000 }).toBeGreaterThan(50);
            }

            if (item.label !== 'Blog') {
                await expect.poll(async () => {
                    const box = await section.boundingBox();
                    return Math.abs((box?.y || 0) - 80);
                }, { timeout: 10000 }).toBeLessThan(50);
            } else {
                await expect.poll(async () => {
                    const box = await section.boundingBox();
                    return box?.y;
                }, { timeout: 10000 }).toBeGreaterThan(50);
            }
        });
    }

    // 2. Check navigation from LLM page
    for (const item of navItems) {
        test(`should navigate from LLM to ${item.label}`, async ({ page }) => {
            await page.goto('/llm');
            await expect(page.locator('app-llm')).toBeVisible();

            await page.click(`nav >> text=${item.label}`);
            await expect(page).toHaveURL(new RegExp(`.*\\/${item.hash}`));

            const section = page.locator(`section${item.hash}`);
            await expect(section).toBeVisible();

            if (item.label !== 'About') {
                await expect.poll(async () => page.evaluate(() => window.scrollY), { timeout: 5000 }).toBeGreaterThan(50);
            }

            if (item.label !== 'Blog') {
                await expect.poll(async () => {
                    const box = await section.boundingBox();
                    return Math.abs((box?.y || 0) - 80);
                }, { timeout: 10000 }).toBeLessThan(50);
            } else {
                await expect.poll(async () => {
                    const box = await section.boundingBox();
                    return box?.y;
                }, { timeout: 10000 }).toBeGreaterThan(50);
            }
        });
    }

    test('should navigate from CV to Blog route', async ({ page }) => {
        await page.goto('/cv');
        await expect(page.locator('app-cv')).toBeVisible();
        await page.click('nav >> text=Blog');
        await expect(page).toHaveURL(/\/blog$/);
    });

    test('should navigate from LLM to Blog route', async ({ page }) => {
        await page.goto('/llm');
        await expect(page.locator('app-llm')).toBeVisible();
        await page.click('nav >> text=Blog');
        await expect(page).toHaveURL(/\/blog$/);
    });
});
