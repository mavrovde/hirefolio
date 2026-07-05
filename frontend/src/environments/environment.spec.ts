import { environment } from './environment';
import { environment as prodEnvironment } from './environment.prod';

describe('Environment', () => {
    it('should have production flag set correctly', () => {
        expect(environment.production).toBe(false);
        expect(prodEnvironment.production).toBe(true);
    });

    it('should expose a googleAnalyticsId string (injected at build time)', () => {
        // The ID is no longer hardcoded — it is injected from build-time env
        // (NG_APP_GA_ID / GA_MEASUREMENT_ID), so it defaults to an empty string.
        expect(typeof environment.googleAnalyticsId).toBe('string');
        expect(typeof prodEnvironment.googleAnalyticsId).toBe('string');
    });

    it('should share the same api configuration across environments', () => {
        expect(environment.apiPrefix).toBe('/api/app');
        expect(prodEnvironment.apiPrefix).toBe('/api/app');
    });
});
