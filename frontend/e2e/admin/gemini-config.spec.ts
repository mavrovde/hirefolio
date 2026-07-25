
import { test, expect } from '@playwright/test';

test.describe('Gemini Configuration', () => {
    test.beforeEach(async ({ page }) => {
        // Mock the backend responses
        await page.route('**/api/app/auth/gemini-key', async route => {
            if (route.request().method() === 'PUT') {
                const data = route.request().postDataJSON();
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        id: 1,
                        username: 'admin',
                        email: 'admin@mavrov.de',
                        is_admin: true,
                        gemini_api_key: data.api_key
                    })
                });
            } else {
                await route.continue();
            }
        });

        // Mock initial user load with existing key
        await page.route('**/api/app/auth/me', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    id: 1,
                    username: 'admin',
                    email: 'admin@mavrov.de',
                    is_admin: true,
                    gemini_api_key: 'initial-e2e-key'
                })
            });
        });

        // Inject fake token to trigger AuthService.loadCurrentUser()
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-e2e-token');
        });

        // Since we mock auth/me returning a user, we are effectively "logged in"
        // and can navigate directly to protected routes.
        // await page.goto('/login'); // specific login steps removed

        await page.goto('/admin/profile');
    });

    test('should load and update Gemini API Key', async ({ page }) => {
        // 1. Verify initial state
        const input = page.locator('#geminiKey');
        await input.waitFor({ state: 'visible', timeout: 10000 });
        await expect(input).toHaveValue('initial-e2e-key');
        await expect(input).toHaveAttribute('type', 'password');

        // 2. Toggle visibility
        await page.click('text=SHOW');
        await expect(input).toHaveAttribute('type', 'text');
        await page.click('text=HIDE');
        await expect(input).toHaveAttribute('type', 'password');

        // 3. Update key
        const newKey = 'new-gemini-key-updated';
        await input.fill(newKey);
        await page.click('text=[ SAVE KEY ]');

        // 4. Verify success message
        await expect(page.locator('div.success-message')).toContainText('API Key saved successfully'); // Using class selector based on template

        // 5. Verify persisted value (though mocked backend returns it, UI should update)
        await expect(input).toHaveValue(newKey);
    });
});
