import { appConfig } from './app.config';
import { describe, it, expect } from 'vitest';

describe('AppConfig', () => {
    it('should have required providers', () => {
        expect(appConfig.providers).toBeDefined();
        expect(Array.isArray(appConfig.providers)).toBe(true);
        expect(appConfig.providers.length).toBeGreaterThan(0);
    });
});
