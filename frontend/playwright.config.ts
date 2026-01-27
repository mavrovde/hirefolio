/// <reference types="node" />
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // Avoid race conditions on shared DB
  forbidOnly: !!process.env.CI,
  retries: 2, // Always retry to handle flakiness
  workers: 1, // Run sequentially for stability
  reporter: 'html',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:4201', // Default to local dev, override for Docker
    ignoreHTTPSErrors: true,
    trace: 'on-first-retry',
    screenshot: 'on',
    video: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
