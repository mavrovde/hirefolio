import { routes } from './app.routes';
import { describe, it, expect } from 'vitest';

describe('AppRoutes', () => {
    it('should have routes defined', () => {
        expect(routes).toBeDefined();
        expect(Array.isArray(routes)).toBe(true);
        expect(routes.length).toBeGreaterThan(0);
    });

    it('should have a root route', () => {
        const rootRoute = routes.find(r => r.path === '');
        expect(rootRoute).toBeDefined();
    });

    it('should have an admin route', () => {
        const adminRoute = routes.find(r => r.path === 'admin');
        expect(adminRoute).toBeDefined();
        expect(adminRoute?.canActivate).toBeDefined();
    });

    it('should be possible to load all lazy components', async () => {
        const lazyRoutes = routes.flatMap(r => {
            const children = r.children || [];
            return [r, ...children];
        }).filter(r => r.loadComponent);

        for (const route of lazyRoutes) {
            if (route.loadComponent) {
                const component = await (route.loadComponent as any)();
                expect(component).toBeDefined();
            }
        }
    });
});
