import { test, expect } from '@playwright/test';

test.describe('CV Request Flow', () => {
    test.beforeEach(async ({ page }) => {
        console.log(`[E2E] Starting test: ${test.info().title}`);
        page.on('console', msg => console.log(`[BROWSER] ${msg.type()}: ${msg.text()}`));

        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });
    });

    test('should submit CV request successfully', async ({ page }) => {
        // Intercept the request to verify payload and response
        let requestPayload: any;
        console.log('[E2E] Mocking CV request API...');
        await page.route('**/api/cv/request*', async route => {
            requestPayload = route.request().postDataJSON();
            console.log('[E2E] Intercepted /api/cv/request with payload:', requestPayload);
            await route.continue();
        });

        console.log('[E2E] Navigating to /cv...');
        await page.goto('/cv');

        // Fill form
        console.log('[E2E] Filling CV request form...');
        await page.fill('input[formControlName="name"]', 'E2E Tester');
        await page.fill('input[formControlName="email"]', 'e2e@test.com');
        await page.fill('input[formControlName="company"]', 'Test Co');
        await page.fill('textarea[formControlName="message"]', 'Hello from E2E');

        // Handle the download event
        console.log('[E2E] Setting up download listener...');
        const downloadPromise = page.waitForEvent('download').catch(() => {
            console.log('[E2E] No download event triggered (within timeout)');
            return null;
        });

        // Click submit
        console.log('[E2E] Submitting request...');
        await page.click('button[type="submit"]');

        // Verify request payload was correct
        expect(requestPayload).toBeTruthy();
        expect(requestPayload.name).toBe('E2E Tester');
        console.log('[E2E] Request payload verified.');

        // Verify success state
        console.log('[E2E] Waiting for API response...');
        const response = await page.waitForResponse(response =>
            response.url().includes('/api/cv/request') && response.status() === 200
        );
        expect(response.ok()).toBeTruthy();
        console.log('[E2E] API response received and verified.');
    });

    test('should show validation errors', async ({ page }) => {
        await page.goto('/cv');

        // Touch fields and leave them to trigger validation
        await page.focus('input[formControlName="email"]');
        await page.locator('input[formControlName="email"]').blur();

        // Look for error message (adjust selector based on your visual implementation)
        // If specific error classes/elements aren't known, checking that submit is disabled is a good proxy if valid
        // Or check if classes keys are visible like "VALIDATION.REQUIRED"

        // Attempt submit
        // Check submit button is disabled
        await expect(page.locator('button[type="submit"]')).toBeDisabled();

        // Check error message visibility
        await expect(page.locator('.error-msg').first()).toBeVisible();
    });
});
