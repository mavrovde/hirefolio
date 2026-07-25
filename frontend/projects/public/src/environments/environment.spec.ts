import { environment } from './environment';
import { environment as prodEnvironment } from './environment.prod';

describe('Environment', () => {
    it('should have production flag set correctly', () => {
        expect(environment.production).toBe(false);
        expect(prodEnvironment.production).toBe(true);
    });

    it('should have googleAnalyticsId', () => {
        expect(environment.googleAnalyticsId).toBe('G-1QSMT6N045');
        expect(prodEnvironment.googleAnalyticsId).toBe('G-1QSMT6N045');
    });
});
