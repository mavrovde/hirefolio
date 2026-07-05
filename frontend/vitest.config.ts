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
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.ts'],
      exclude: [
        'src/**/*.spec.ts',
        'src/test-setup.ts',
        // Application/SSR bootstrap entry points. These are executed by the
        // Angular/Node runtime (not unit-testable in jsdom): main.ts and
        // main.server.ts are bootstrap shims, and server.ts instantiates
        // AngularNodeAppEngine at import time, which requires the production
        // SSR build manifest produced by @angular/build:application.
        'src/main.ts',
        'src/main.server.ts',
        'src/server.ts',
      ],
    },
  },
  resolve: {
    alias: {
      '@app': resolve(__dirname, './src/app'),
      '@env': resolve(__dirname, './src/environments'),
    },
  },
});
