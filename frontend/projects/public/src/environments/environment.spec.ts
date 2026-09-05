import { environment } from './environment';
import { environment as prodEnvironment } from './environment.prod';

describe('Environment', () => {
    it('should have production flag set correctly', () => {
        expect(environment.production).toBe(false);
        expect(prodEnvironment.production).toBe(true);
    });

    it('should have an EMPTY googleAnalyticsId (deprecated by the runtime site config, #65)', () => {
        expect(environment.googleAnalyticsId).toBe('');
        expect(prodEnvironment.googleAnalyticsId).toBe('');
    });
});
