import { defineConfig } from 'vitest/config';
import angular from '@analogjs/vite-plugin-angular';
import { resolve } from 'path';

export default defineConfig({
  plugins: [angular()],
  root: __dirname,
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.spec.ts'],
    reporters: ['default'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: '../../coverage/public',
      include: ['src/**/*.ts'],
      // Exclude framework-generated bootstrap entry points (client + SSR server)
      exclude: ['src/**/*.spec.ts', 'src/test-setup.ts', 'src/main.ts', 'src/main.server.ts', 'src/server.ts'],
      // The project standard (CLAUDE.md rule 2) as an ENFORCED floor, not a convention: any drop
      // below 100% fails the run instead of merely printing a smaller number.
      thresholds: { statements: 100, branches: 100, functions: 100, lines: 100 },
    },
  },
  resolve: {
    alias: {
      '@beaconfolio/shared/testing': resolve(__dirname, '../shared/testing/public-api.ts'),
      '@beaconfolio/shared': resolve(__dirname, '../shared/src/public-api.ts'),
    },
  },
});
