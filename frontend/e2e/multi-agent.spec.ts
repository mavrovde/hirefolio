import { test, expect } from '@playwright/test';
import { API_PREFIX } from './config';

test.describe('Multi-Agent Conversation', () => {
    test.beforeEach(async ({ page }) => {
        console.log(`[E2E] Starting test: ${test.info().title}`);

        // Detailed console logging from browser
        page.on('console', msg => {
            console.log(`[BROWSER] ${msg.type()}: ${msg.text()}`);
        });

        // Mock name generation
        await page.route(`**${API_PREFIX}/ai/generate-name`, async route => {
            console.log(`[E2E] Mocking ${API_PREFIX}/ai/generate-name`);
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ name: 'Mock Agent' })
            });
        });

        // Mock SSE/Streaming for multi-chat
        await page.route(`**${API_PREFIX}/ai/multi-chat`, async route => {
            console.log(`[E2E] Mocking ${API_PREFIX}/ai/multi-chat (SSE)`);
            const body =
                JSON.stringify({ agent: 1, content: 'Quantum ' }) + '\n' +
                JSON.stringify({ agent: 1, content: 'physics is ' }) + '\n' +
                JSON.stringify({ agent: 1, content: 'fascinating.' }) + '\n' +
                JSON.stringify({ agent: 1, turn_complete: true }) + '\n' +
                JSON.stringify({ agent: 2, content: ' But what ' }) + '\n' +
                JSON.stringify({ agent: 2, content: 'is meaning?' }) + '\n' +
                JSON.stringify({ agent: 2, turn_complete: true }) + '\n' +
                JSON.stringify({ done: true }) + '\n';

            // Small delay to ensure buttons/state are visible during "thinking" phase
            await new Promise(resolve => setTimeout(resolve, 1000));

            await route.fulfill({
                status: 200,
                contentType: 'application/x-ndjson',
                body: body
            });
        });

        console.log('[E2E] Navigating to /llm');
        await page.goto('/llm');
        await page.waitForLoadState('networkidle');

        // Accept cookies
        const acceptBtn = page.locator('button:has-text("Accept & Save")');
        if (await acceptBtn.isVisible()) {
            await acceptBtn.click();
            console.log('[E2E] Cookies accepted');
        }
    });

    async function fillAgent(page: any, index: number, name: string, desc: string) {
        console.log(`[E2E] Filling agent ${index}: ${name}`);
        const card = page.locator('.agent-card').nth(index);
        // Important: Fill description first because it triggers onAgentDescriptionChange which might overwrite name
        await card.locator('textarea[placeholder*="personality"]').fill(desc);
        await card.locator('input[placeholder="e.g. Skeptic"]').fill(name);
    }

    async function fillTopic(page: any, topic: string) {
        console.log(`[E2E] Filling topic: ${topic}`);
        await page.locator('input[placeholder*="core subject"]').fill(topic);
    }

    test('should display mode toggle buttons', async ({ page }) => {
        await expect(page.locator('button:has-text("Single Agent")')).toBeVisible();
        await expect(page.locator('button:has-text("Multi-Agent Debate")')).toBeVisible();
    });

    test('should switch to multi-agent mode', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();
        await expect(page.locator('.multi-agent-container')).toBeVisible();
        await expect(page.locator('h1:has-text("Multi-Agent Debate")')).toBeVisible();
    });

    test('should disable start button without required fields', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();
        const startBtn = page.locator('button:has-text("START DEBATE")');

        await expect(startBtn).toBeDisabled();

        await fillAgent(page, 0, 'Agent 1', 'Expert physicist');
        await fillAgent(page, 1, 'Agent 2', 'Expert philosopher');
        await expect(startBtn).toBeDisabled();

        await fillTopic(page, 'The nature of time');
        await expect(startBtn).toBeEnabled();
    });

    test('should start and display messages', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        await fillAgent(page, 0, 'Skeptic', 'A doubting scientist');
        await fillAgent(page, 1, 'Believer', 'An optimistic dreamer');
        await fillTopic(page, 'Is AI alive?');

        const startBtn = page.locator('button:has-text("START DEBATE")');
        await startBtn.click();

        console.log('[E2E] Clicked START, waiting for messages...');
        const messages = page.locator('.agent-message');
        await expect(messages.first()).toBeVisible({ timeout: 15000 });

        const firstMessageText = await messages.first().innerText();
        console.log('[E2E] First message text:', firstMessageText);

        expect(await messages.count()).toBeGreaterThan(0);
        await expect(page.locator('.agent-label').first()).toBeVisible();
    });

    test('should stop conversation manually', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();
        await fillAgent(page, 0, 'A', 'B');
        await fillAgent(page, 1, 'C', 'D');
        await fillTopic(page, 'T');

        await page.locator('button:has-text("START DEBATE")').click();
        const stopBtn = page.locator('button:has-text("STOP")').first();

        // Wait for it to become enabled (when stream starts)
        await expect(stopBtn).toBeEnabled({ timeout: 10000 });
        await stopBtn.click();

        console.log('[E2E] Clicked STOP, checking status...');
        await expect(page.locator('.timer')).toContainText('Debate Stopped', { timeout: 10000 });
        await expect(page.locator('button:has-text("START DEBATE")')).toBeEnabled();
    });

    test('should disable inputs during active conversation', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();
        await fillAgent(page, 0, 'A', 'B');
        await fillAgent(page, 1, 'C', 'D');
        await fillTopic(page, 'Topic');

        await page.locator('button:has-text("START DEBATE")').click();

        // Config hides automatically on start, must show it to check inputs
        const showConfigBtn = page.locator('button:has-text("Show Config")');
        if (await showConfigBtn.isVisible()) {
            await showConfigBtn.click();
        }

        // Topic input should be disabled
        await expect(page.locator('input[placeholder*="core subject"]')).toBeDisabled();


        // Agent inputs should be disabled (cards contain them)
        const agentInputs = page.locator('.agent-card input');
        const count = await agentInputs.count();
        expect(count).toBeGreaterThan(0);
        for (let i = 0; i < count; i++) {
            await expect(agentInputs.nth(i)).toBeDisabled();
        }
    });

    test('should reset configuration', async ({ page }) => {
        await page.locator('button:has-text("Multi-Agent Debate")').click();

        await fillAgent(page, 0, 'Custom Name', 'Custom Description');
        await fillTopic(page, 'Custom Topic');

        await page.locator('button:has-text("RESET CONFIGURATION")').click();

        // Should return to defaults
        await expect(page.locator('input[placeholder="e.g. Skeptic"]').first()).toHaveValue('Agent 1');
        await expect(page.locator('input[placeholder*="core subject"]')).toHaveValue('');
    });
});
