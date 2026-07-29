
import { test, expect } from '@playwright/test';

test.describe('Footer Stats', () => {
    test.beforeEach(async ({ page }) => {
        // Block Google Analytics and Tag Manager
        await page.route('**/*analytics*', route => route.abort());
        await page.route('**/*googletagmanager*', route => route.abort());
        await page.route('**/*doubleclick*', route => route.abort());

        // Bypass cookie consent
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });

        page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
        page.on('request', request => console.log('>>', request.method(), request.url()));
        page.on('requestfailed', request => console.log('>> FAILED', request.method(), request.url(), request.failure()?.errorText));
    });

    test('should display footer stats on success', async ({ page }) => {
        // Use real backend response
        // await page.route('**/api/app/stats/public', ...);

        // Wait for request
        const requestPromise = page.waitForRequest(req => req.url().includes('stats/public'));
        await page.goto('/');

        // Footer is hidden on small screens, so ensure viewport is large enough (Desktop)
        await page.setViewportSize({ width: 1920, height: 1080 });

        // Force visibility if still hidden (for verification of content)
        // Check for specific text from real backend
        // Check for specific text from real backend
        const footer = page.locator('app-system-stats > div').first();
        await expect(footer).toBeVisible();
        const footerText = await footer.innerText();
        console.log('Footer text:', footerText);



        const clientIp = page.locator('span').filter({ hasText: 'CLIENT:' });
        await expect(clientIp).toBeVisible();
        await expect(clientIp).not.toContainText('Unavailable');
        // Accept localhost IP or typical Docker IPs
        await expect(clientIp).toHaveText(/CLIENT: (127\.0\.0\.1|::1|172\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)/);

        const feVersion = page.getByText('FE: v');
        await expect(feVersion).toBeVisible();

        const beVersion = page.getByText(/BE: v\d+\.\d+\.\d+/);
        await expect(beVersion).toBeVisible();
    });

    // #105 — zoneless change-detection guard. The footer uptime is a PURELY async
    // region: a `setInterval` mutates a plain `uptime` property every second and
    // relies solely on `ChangeDetectorRef.markForCheck()` to repaint (the public
    // app bundles no zone.js). If the app silently reverted to relying on an
    // implicit zone, the counter would freeze in the browser while unit tests
    // (which bundle zone.js) still pass — so assert it actually advances live.
    test('footer uptime advances over time (zoneless CD repaints async mutations)', async ({ page }) => {
        await page.goto('/');
        await page.setViewportSize({ width: 1920, height: 1080 });

        const uptime = page.getByTestId('footer-uptime');
        await expect(uptime).toBeVisible();
        await expect(uptime).toHaveText(/^\d{2}:\d{2}:\d{2}$|^\d+d /);

        const first = await uptime.innerText();
        // The counter ticks once per second; wait long enough to cross ≥2 ticks.
        await expect
            .poll(async () => uptime.innerText(), { timeout: 5000, intervals: [500] })
            .not.toBe(first);
    });

    test('should handle API error gracefully', async ({ page }) => {
        // Mock failed API response
        await page.route('**/api/app/stats/public', async route => {
            await route.abort(); // Network error
        });

        await page.goto('/');
        await page.setViewportSize({ width: 1280, height: 720 });

        // Check for fallback text (from our error handling code)
        // We set 'Unavailable' and 'Error'
        const unavailableIp = page.getByText('CLIENT: Unavailable');
        await expect(unavailableIp).toBeVisible();

        const errorVersion = page.getByText('BE: vError');
        await expect(errorVersion).toBeVisible();
    });
});
