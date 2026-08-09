
import { test, expect } from '@playwright/test';

test.describe('Gemini Configuration', () => {
    test.beforeEach(async ({ page }) => {
        // Mock the backend responses. SECURITY (#143): the backend never returns
        // the raw key — only has_gemini_key (whether one is configured).
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
                        has_gemini_key: !!data.api_key
                    })
                });
            } else {
                await route.continue();
            }
        });

        // Mock initial user load — a key is already configured, but its value
        // is NOT sent to the browser.
        await page.route('**/api/app/auth/me', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    id: 1,
                    username: 'admin',
                    email: 'admin@mavrov.de',
                    is_admin: true,
                    has_gemini_key: true
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

        await page.goto('/profile');
    });

    test('should show configured status and set a new key without reading it back', async ({ page }) => {
        // 1. Verify initial state: status shows "Key configured", but the raw key
        //    is NOT prefilled into the input (write-only field).
        const input = page.locator('#geminiKey');
        await input.waitFor({ state: 'visible', timeout: 10000 });
        await expect(page.getByTestId('gemini-key-status')).toContainText('Key configured');
        await expect(input).toHaveValue('');
        await expect(input).toHaveAttribute('type', 'password');

        // 2. Toggle visibility of what the user is typing
        await page.click('text=SHOW');
        await expect(input).toHaveAttribute('type', 'text');
        await page.click('text=HIDE');
        await expect(input).toHaveAttribute('type', 'password');

        // 3. Set a new key
        const newKey = 'new-gemini-key-updated';
        await input.fill(newKey);
        await page.click('text=[ SAVE KEY ]');

        // 4. Verify success message
        await expect(page.locator('div.success-message')).toContainText('API Key saved successfully');

        // 5. The secret is cleared from the field after saving; status stays configured.
        await expect(input).toHaveValue('');
        await expect(page.getByTestId('gemini-key-status')).toContainText('Key configured');
    });
});
