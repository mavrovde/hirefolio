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
      // `testing/**` means the sibling `@mavrov/shared/testing` entry point ONLY. Vitest 4 matched
      // these globs against absolute paths with picomatch `contains`, so it also swallowed
      // `src/lib/testing/**`; Vitest 5 matches relative to `root`, so those two mock files are now
      // measured (and are at 100%). Do not "restore" the old, wider exclusion — see #309.
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
