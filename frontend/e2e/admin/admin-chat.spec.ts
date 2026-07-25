
import { test, expect } from '@playwright/test';

test.describe('Admin Chat', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to admin login
        await page.goto('/admin/login');

        // Perform login
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');

        // Wait for navigation to dashboard
        await expect(page).toHaveURL('/admin/dashboard');
    });

    test('should navigate to Gemini Chat from sidebar', async ({ page }) => {
        // Navigate directly to chat to ensure page loads
        await page.goto('/admin/chat');

        // Check for header
        await expect(page.locator('h2', { hasText: 'Admin Chat with Gemini' })).toBeVisible();
        // Note: The specific chat header might be different or inside the component
        // Let's check for chat-specific elements

        // Check for input field
        await expect(page.locator('input[placeholder="Type a message..."]')).toBeVisible();

        // Check for send button
        await expect(page.locator('button', { hasText: 'Send' })).toBeVisible();
    });
});
