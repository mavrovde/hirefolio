import { test, expect } from '@playwright/test';

test.describe('Admin LinkedIn Integration Verification', () => {

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

        const loginResponsePromise = page.waitForResponse(
            resp => resp.url().includes('/auth/login'),
            { timeout: 10000 }
        ).catch(() => null);

        await page.click('button[type="submit"]');
        await loginResponsePromise;

        // Wait for ANY admin page element to ensure login success
        try {
            await expect(page).toHaveURL(/\/admin\/(dashboard|chat|profile|sql|linkedin)/, { timeout: 15000 });
        } catch (e) {
            console.log('Navigation failed. Current URL:', page.url());
            throw e;
        }
    });

    test('LinkedIn Panel should fetch posts and allow transferring', async ({ page }) => {
        // Mock the fetch posts API correctly now that Angular Proxy configuration is fixed
        await page.route('**/api/app/linkedin/posts', async route => {
            if (route.request().method() === 'OPTIONS') {
                return route.continue();
            }
            console.log('[E2E] Intercepted linkedin/posts request');
            await route.fulfill({
                status: 200,
                headers: {
                    'Access-Control-Allow-Origin': 'http://localhost:4200',
                    'Access-Control-Allow-Credentials': 'true',
                    'Access-Control-Expose-Headers': '*'
                },
                json: [
                    {
                        id: 'urn:li:activity:123456789',
                        content: 'This is a test LinkedIn post from Playwright E2E.',
                        time: '2 hours ago',
                        url: 'https://linkedin.com/test'
                    }
                ]
            });
        });

        // Mock the transfer post API
        await page.route('**/api/app/linkedin/transfer-post', async route => {
            if (route.request().method() === 'OPTIONS') {
                return route.continue();
            }
            console.log('[E2E] Intercepted linkedin/transfer-post request');
            await route.fulfill({
                status: 200,
                headers: {
                    'Access-Control-Allow-Origin': 'http://localhost:4200',
                    'Access-Control-Allow-Credentials': 'true'
                },
                json: { id: 999, message: 'Post transferred successfully' }
            });
        });
        // Navigate to the LinkedIn admin page
        await page.goto('/admin/linkedin');

        // Wait for container to be visible
        await expect(page.locator('h1', { hasText: '> LinkedIn Sync' })).toBeVisible({ timeout: 15000 });

        // Click Fetch Recent Posts button
        await page.locator('button', { hasText: 'Fetch Recent Posts' }).click();

        // Workaround for Playwright route.fulfill bypassing Angular ZoneJS XHR hooks
        await page.waitForTimeout(500);
        await page.mouse.click(0, 0);

        // Verify the post content is visible by checking for the stable post card element
        await expect(page.locator('.post-card').first()).toBeVisible({ timeout: 5000 });

        // Click Transfer as Draft button
        await page.locator('button', { hasText: 'Transfer to DB' }).first().click();

        await page.waitForTimeout(500);
        await page.mouse.click(0, 0);

        // Verify the status message changes to the transfer success
        await expect(page.locator('.status-bar')).toContainText('Transferred', { timeout: 5000 });
    });

    test('LinkedIn Panel should sync profile', async ({ page }) => {
        // Mock the profile API correctly
        await page.route('**/api/app/linkedin/profile-sync', async route => {
            if (route.request().method() === 'OPTIONS') {
                return route.continue();
            }
            console.log('[E2E] Intercepted linkedin/profile-sync request');
            await route.fulfill({
                status: 200,
                headers: {
                    'Access-Control-Allow-Origin': 'http://localhost:4200',
                    'Access-Control-Allow-Credentials': 'true'
                },
                json: {
                    name: 'E2E Test User',
                    headline: 'E2E Test Engineer',
                    about: 'Writing robust reliable Playwright tests.'
                }
            });
        });
        // Navigate to the LinkedIn admin page
        await page.goto('/admin/linkedin');

        // Wait for container to be visible
        await expect(page.locator('h1', { hasText: '> LinkedIn Sync' })).toBeVisible();

        // Switch to Profile tab
        await page.locator('button', { hasText: 'Profile' }).click();

        // Click Scan Profile button
        await page.locator('button', { hasText: 'Scan Profile' }).click();

        // Workaround for ZoneJS
        await page.waitForTimeout(500);
        await page.mouse.click(0, 0);

        // Verify profile data JSON renders (stable view)
        await expect(page.locator('.data-view')).toBeVisible({ timeout: 5000 });
        await expect(page.locator('pre', { hasText: '"name": "E2E Test User"' })).toBeVisible();
    });

    test('LinkedIn Panel should handle dynamic login flow', async ({ page }) => {
        // Mock the initial status API to return false to show login form
        await page.route('**/api/app/linkedin/status', async route => {
            if (route.request().method() === 'OPTIONS') {
                return route.continue();
            }
            await route.fulfill({
                status: 200,
                headers: {
                    'Access-Control-Allow-Origin': 'http://localhost:4200',
                    'Access-Control-Allow-Credentials': 'true'
                },
                json: { logged_in: false }
            });
        });

        // Navigate to the LinkedIn admin page
        await page.goto('/admin/linkedin');
        
        // Wait for container to be visible and login form to render
        await expect(page.locator('h1', { hasText: '> LinkedIn Sync' })).toBeVisible({ timeout: 15000 });
        await expect(page.locator('input[placeholder="LinkedIn Email"]')).toBeVisible();

        // Fill credentials
        await page.fill('input[placeholder="LinkedIn Email"]', 'testuser@example.com');
        await page.fill('input[placeholder="LinkedIn Password"]', 'securepass');

        // Mock the login API to return success
        await page.route('**/api/app/linkedin/login', async route => {
            if (route.request().method() === 'OPTIONS') {
                return route.continue();
            }
            // Add slight delay for realistic timing
            await new Promise(r => setTimeout(r, 200));
            await route.fulfill({
                status: 200,
                headers: {
                    'Access-Control-Allow-Origin': 'http://localhost:4200',
                    'Access-Control-Allow-Credentials': 'true'
                },
                json: { message: 'Successfully logged in' }
            });
        });

        // Click login button
        await page.locator('button', { hasText: 'Login & Save Session' }).click();

        // Workaround for ZoneJS
        await page.waitForTimeout(500);
        await page.mouse.click(0, 0);

        // Verify success status
        await expect(page.locator('.status-bar')).toContainText('Successfully logged in', { timeout: 5000 });
        
        // Ensure form inputs are removed and connected state shows
        await expect(page.locator('input[placeholder="LinkedIn Email"]')).toBeHidden();
        await expect(page.locator('.success', { hasText: 'Connected' })).toBeVisible();
    });
});
