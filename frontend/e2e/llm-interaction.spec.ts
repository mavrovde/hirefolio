import { test, expect } from '@playwright/test';

test.describe('LLM Terminal', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/llm');
    });

    test('should display terminal with initial system message', async ({ page }) => {
        await expect(page.locator('.terminal-container')).toBeVisible();
        await expect(page.getByText('user@mavrov:~/llm$', { exact: true })).toBeVisible();
        await expect(page.locator('text=# Connected to local AI agent.')).toBeVisible();
    });

    test('should handle multi-chunk streaming response', async ({ page }) => {
        const chunks = ['Hello ', 'this ', 'is ', 'a ', 'streamed ', 'response.'];

        await page.route('**/api/ai/chat', async (route) => {
            await new Promise(resolve => setTimeout(resolve, 100)); // Simulate delay
            await route.fulfill({
                status: 200,
                contentType: 'text/event-stream',
                body: chunks.join('')
            });
        });

        const input = page.locator('input[type="text"]');
        await input.fill('test message');
        await input.press('Enter');

        // Check user message
        await expect(page.locator('.message', { hasText: 'test message' })).toBeVisible();

        // Check cumulative response
        await expect(page.locator('.message .text-secondary')).toContainText('Hello this is a streamed response.');
    });

    test('should clear history when "clear" command is sent', async ({ page }) => {
        const input = page.locator('input[type="text"]');

        // Send a message first
        await input.fill('temporary message');
        await input.press('Enter');
        await expect(page.locator('text=temporary message')).toBeVisible();

        // Send clear
        await input.fill('clear');
        await input.press('Enter');

        // Verify history is cleared and shows "Console cleared"
        await expect(page.locator('text=temporary message')).not.toBeVisible();
        await expect(page.locator('text=# Console cleared.')).toBeVisible();
    });

    test('should handle API errors gracefully', async ({ page }) => {
        await page.route('**/api/ai/chat', async (route) => {
            await new Promise(resolve => setTimeout(resolve, 100));
            await route.abort('failed');
        });

        const input = page.locator('input[type="text"]');
        await input.fill('trigger error');
        await input.press('Enter');

        // Error message should appear
        await expect(page.locator('text=Error: Failed to communicate with AI agent.')).toBeVisible();
    });

    test('should have terminal-inspired aesthetics', async ({ page }) => {
        const terminal = page.locator('.terminal-container');
        await expect(terminal).toHaveCSS('background-color', 'rgb(0, 0, 0)');
        await expect(terminal).toHaveCSS('font-family', /monospace|mono/);

        const input = page.locator('input[type="text"]');
        await expect(input).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
        await expect(input).toHaveCSS('border-style', 'none');
    });

    test('should maintain focus on input after interaction', async ({ page }) => {
        // Mock API with delay
        await page.route('**/api/ai/chat', async (route) => {
            await new Promise(resolve => setTimeout(resolve, 200));
            await route.fulfill({
                status: 200,
                contentType: 'text/event-stream',
                body: 'Ok'
            });
        });

        const input = page.locator('input[type="text"]');

        // Initial focus
        await expect(input).toBeFocused();

        // Focus after sending message
        await input.fill('hello');
        await input.press('Enter');

        // Input should disappear during thinking (pulse indicator)
        await expect(page.locator('text=_ generating response...')).toBeVisible();

        // Wait for it to reappear and be focused
        await expect(input).toBeVisible();
        await page.waitForFunction(() => document.activeElement instanceof HTMLInputElement);
        await expect(input).toBeFocused();

        // Focus after clicking terminal container
        await page.locator('.terminal-container').click();
        await page.waitForFunction(() => document.activeElement instanceof HTMLInputElement);
        await expect(input).toBeFocused();
    });
});
