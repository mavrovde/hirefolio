import { test, expect } from '@playwright/test';

test.describe('CV Request Flow', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });
    });

    test('should submit CV request successfully', async ({ page }) => {
        // Intercept the request to verify payload and response
        let requestPayload: any;
        await page.route('**/api/cv/request', async route => {
            requestPayload = route.request().postDataJSON();
            await route.continue();
        });

        await page.goto('/cv');

        // Fill form
        await page.fill('input[formControlName="name"]', 'E2E Tester');
        await page.fill('input[formControlName="email"]', 'e2e@test.com');
        await page.fill('input[formControlName="company"]', 'Test Co');
        await page.fill('textarea[formControlName="message"]', 'Hello from E2E');


        // Handle the download event
        const downloadPromise = page.waitForEvent('download').catch(() => null);
        // We catch because depending on how the component handles it (window.open vs link click), 
        // it might be a popup or a download event. 
        // If logic is window.open(url, '_blank'), Playwright might see a popup.

        // Click submit
        await page.click('button[type="submit"]');

        // Verify request payload was correct
        expect(requestPayload).toBeTruthy();
        expect(requestPayload.name).toBe('E2E Tester');

        // Verify success state - e.g. success message or form reset
        // Assuming the component shows a success message or clears the form
        // Let's wait for a visual confirmation if possible, or just the network request success
        const response = await page.waitForResponse(response =>
            response.url().includes('/api/cv/request') && response.status() === 200
        );
        expect(response.ok()).toBeTruthy();
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
