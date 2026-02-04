/// <reference types="node" />
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true, // Run tests within files in parallel
  forbidOnly: !!process.env.CI,
  retries: 2, // Always retry to handle flakiness
  workers: 2, // Use "few workers" as requested for better speed/stability balance
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
