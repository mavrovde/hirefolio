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
    include: ['src/**/*.spec.ts', 'testing/**/*.spec.ts'],
    reporters: ['default'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: '../../coverage/shared',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.spec.ts', 'src/test-setup.ts', 'src/public-api.ts', 'testing/**'],
    },
  },
  resolve: {
    alias: {
      '@mavrov/shared/testing': resolve(__dirname, './testing/public-api.ts'),
      '@mavrov/shared': resolve(__dirname, './src/public-api.ts'),
    },
  },
});
