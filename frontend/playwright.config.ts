/// <reference types="node" />
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // Run tests sequentially to avoid shared state conflicts
  forbidOnly: !!process.env.CI,
  retries: 2, // Always retry to handle flakiness
  workers: 1, // Sequential execution needed for profile/sql tests sharing admin user
  reporter: 'html',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:4200', // Default to local dev, override for Docker
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
