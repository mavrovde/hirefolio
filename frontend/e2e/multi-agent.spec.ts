import { test, expect } from '@playwright/test';

test.describe('Multi-Agent Conversation', () => {
    test.beforeEach(async ({ page }) => {
        // Mock name generation
        await page.route('**/api/ai/generate-name', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify('Mock Agent')
            });
        });

        await page.goto('/llm');
        await page.waitForLoadState('networkidle');

        // Accept cookies to avoid overlays
        const acceptBtn = page.locator('button:has-text("Accept & Save")');
        if (await acceptBtn.isVisible()) {
            await acceptBtn.click();
        }
    });

    async function fillAgent(page: any, index: number, name: string, role: string, goal: string, backstory: string) {
        console.log(`Filling agent ${index + 1}: ${name}`);
        const nameInput = page.locator('input[placeholder="Agent Name"]').nth(index);
        const roleInput = page.locator('input[placeholder*="Role"]').nth(index);
        const goalInput = page.locator('input[placeholder*="Goal"]').nth(index);
        const backstoryInput = page.locator('textarea[placeholder*="Backstory"]').nth(index);

        await nameInput.fill(name);
        await roleInput.fill(role);
        await goalInput.fill(goal);
        await backstoryInput.fill(backstory);
    }

    async function fillTopic(page: any, topic: string) {
        console.log(`Filling topic: ${topic}`);
        await page.locator('input[placeholder*="subject of the debate"]').fill(topic);
    }

    test('should display mode toggle buttons', async ({ page }) => {
        const singleAgentBtn = page.locator('button:has-text("Single Agent")');
        const multiAgentBtn = page.locator('button:has-text("Multi-Agent Debate")');

        await expect(singleAgentBtn).toBeVisible();
        await expect(multiAgentBtn).toBeVisible();
    });

    test('should switch to multi-agent mode', async ({ page }) => {
        const multiAgentBtn = page.locator('button:has-text("Multi-Agent Debate")');
        await multiAgentBtn.click();

        // Verify multi-agent UI is visible
        await expect(page.locator('input[placeholder="Agent Name"]').first()).toBeVisible();
        await expect(page.locator('input[placeholder="Agent Name"]').nth(1)).toBeVisible();
        await expect(page.locator('input[placeholder*="subject of the debate"]')).toBeVisible();
    });


    test('should disable start button without required fields', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();
        await expect(page.locator('.multi-agent-container')).toBeVisible();

        const startBtn = page.locator('button:has-text("START DEBATE")');
        await expect(startBtn).toBeDisabled();

        // Fill only agent 1
        await fillAgent(page, 0, 'Agent 1', 'Scientist', 'Research', 'Backstory 1');
        await expect(startBtn).toBeDisabled();

        // Fill agent 2
        await fillAgent(page, 1, 'Agent 2', 'Philosopher', 'Think', 'Backstory 2');

        // Fill topic
        await fillTopic(page, 'Test topic');

        // Now button should be enabled
        await expect(startBtn).toBeEnabled({ timeout: 60000 });
    });

    test('should start multi-agent conversation', async ({ page }) => {
        test.setTimeout(90000); // Allow time for local LLM to load
        await page.locator('button:has-text("Multi-Agent Debate")').click();
        await expect(page.locator('.multi-agent-container')).toBeVisible();

        // Fill in all fields
        await fillAgent(page, 0, 'A scientist', 'Quantum Physicist', 'Explain reality', 'Senior researcher');
        await fillAgent(page, 1, 'A philosopher', 'Ethicist', 'Probe morality', 'Modern thinker');
        await fillTopic(page, 'The nature of reality');

        // Start conversation
        const startBtn = page.locator('button:has-text("START DEBATE")');
        await expect(startBtn).toBeEnabled({ timeout: 60000 });
        await startBtn.click();

        // Verify conversation started
        await expect(page.locator('button:has-text("STOP")').first()).toBeEnabled();
        await expect(startBtn).toBeDisabled();

        // Wait for some conversation to appear (longer for cold start)
        await page.waitForTimeout(30000);

        // Check if messages are displayed
        const messages = page.locator('.agent-message');
        const messageCount = await messages.count();
        expect(messageCount).toBeGreaterThan(0);
    });

    test('should display timer countdown', async ({ page }) => {
        test.setTimeout(90000);
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        // Initial timer should show 5:00
        const timer = page.locator('.timer');
        await expect(timer).toHaveText('5:00');

        // Fill fields and start
        await fillAgent(page, 0, 'Agent 1', 'Role 1', 'Goal 1', 'B1');
        await fillAgent(page, 1, 'Agent 2', 'Role 2', 'Goal 2', 'B2');
        await fillTopic(page, 'Topic');
        await page.waitForTimeout(2000);

        const startBtn = page.locator('button:has-text("START DEBATE")');
        await expect(startBtn).toBeEnabled({ timeout: 60000 });
        await startBtn.click();

        // Wait a few seconds and check timer has decreased
        await page.waitForTimeout(3000);
        const timerText = await timer.textContent();
        expect(timerText).not.toBe('5:00');
    });

    test('should stop conversation manually', async ({ page }) => {
        test.setTimeout(90000);
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        // Start conversation
        await fillAgent(page, 0, 'Agent 1', 'Role 1', 'Goal 1', 'B1');
        await fillAgent(page, 1, 'Agent 2', 'Role 2', 'Goal 2', 'B2');
        await fillTopic(page, 'Topic');
        await page.waitForTimeout(2000);

        const startBtn = page.locator('button:has-text("START DEBATE")');
        await expect(startBtn).toBeEnabled({ timeout: 60000 });
        await startBtn.click();
        await page.waitForTimeout(1000);

        // Stop conversation
        const stopBtn = page.locator('button:has-text("STOP")').first();
        await stopBtn.click();

        // Verify stopped
        await expect(stopBtn).toBeDisabled();
        await expect(page.locator('button:has-text("START DEBATE")')).toBeEnabled();
    });

    test('should display agent messages with identity', async ({ page }) => {
        test.setTimeout(90000);
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        // Start conversation
        await fillAgent(page, 0, 'Scientist', 'Expert', 'Facts', 'B1');
        await fillAgent(page, 1, 'Philosopher', 'Critic', 'Questions', 'B2');
        await fillTopic(page, 'AI Ethics');


        await page.locator('button:has-text("START DEBATE")').click();

        // Check message structure
        const firstMessage = page.locator('.agent-message').first();
        await expect(firstMessage.locator('.agent-header .agent-label')).toBeVisible({ timeout: 60000 });
    });

    // NOTE: This test requires a running LLM backend (Ollama) to work properly
    // Skipping in CI/automated environments where LLM may not be available
    test('should disable inputs during active conversation', async ({ page }) => {
        test.setTimeout(90000);

        // Hit the real backend (requires Ollama)
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        const agent1Input = page.locator('input[placeholder="Agent Name"]').first();
        const agent2Input = page.locator('input[placeholder="Agent Name"]').nth(1);
        const topicInput = page.locator('input[placeholder*="subject of the debate"]');

        // Fill and start with proper roles/goals
        await fillAgent(page, 0, 'A skeptical scientist', 'Physicist', 'Debunk myths', 'B1');
        await fillAgent(page, 1, 'An optimistic philosopher', 'Theologian', 'Find meaning', 'B2');
        await fillTopic(page, 'The nature of consciousness');

        // Wait for START button to be enabled
        const startBtn = page.locator('button:has-text("START DEBATE")');
        await expect(startBtn).toBeEnabled({ timeout: 60000 });
        await startBtn.click();

        // Check that STOP button becomes enabled (proves conversation started)
        const stopBtn = page.locator('button:has-text("STOP")').first();
        await expect(stopBtn).toBeEnabled({ timeout: 5000 });

        // Show config again to verify inputs are disabled
        await page.locator('.config-toggle').click();

        // Now verify inputs are disabled
        await expect(agent1Input).toBeDisabled();
        await expect(agent2Input).toBeDisabled();
        await expect(topicInput).toBeDisabled();

        // Stop and verify re-enabled
        await stopBtn.click();
        await expect(agent1Input).toBeEnabled();
        await expect(agent2Input).toBeEnabled();
        await expect(topicInput).toBeEnabled();
    });

    test('should switch back to single agent mode', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        // Verify multi-agent UI
        await expect(page.locator('input[placeholder="Agent Name"]').first()).toBeVisible();

        // Switch back
        await page.locator('button:has-text("Single Agent")').click();

        // Verify single-agent UI
        await expect(page.locator('.terminal-container')).toBeVisible();
        await expect(page.locator('input[placeholder="Agent Name"]')).not.toBeVisible();
    });
});
