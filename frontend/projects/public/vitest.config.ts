import { defineConfig } from 'vitest/config';
import angular from '@analogjs/vite-plugin-angular';
import { resolve } from 'path';

export default defineConfig({
  plugins: [angular()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.spec.ts'],
    reporters: ['default'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      include: ['src/**/*.ts'],
      // Exclude framework-generated bootstrap entry points (client + SSR server)
      exclude: ['src/**/*.spec.ts', 'src/test-setup.ts', 'src/main.ts', 'src/main.server.ts', 'src/server.ts'],
    },
  },
  resolve: {
    alias: {
      '@mavrov/shared/testing': resolve(__dirname, '../shared/testing/public-api.ts'),
      '@mavrov/shared': resolve(__dirname, '../shared/src/public-api.ts'),
    },
  },
});
