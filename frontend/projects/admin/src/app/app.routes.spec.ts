import { describe, it, expect } from 'vitest';
import { Route } from '@angular/router';
import { routes } from './app.routes';
import { authGuard } from './guards/auth.guard';

describe('AppRoutes', () => {
  it('should have routes defined', () => {
    expect(routes).toBeDefined();
    expect(Array.isArray(routes)).toBe(true);
    expect(routes.length).toBeGreaterThan(0);
  });

  it('should have a rebased login route (no admin prefix)', () => {
    const login = routes.find((r) => r.path === 'login');
    expect(login).toBeDefined();
    expect(login?.component).toBeDefined();
  });

  it('should have a root layout route with the auth guard and children', () => {
    const layout = routes.find((r) => r.path === '');
    expect(layout).toBeDefined();
    expect(layout?.canActivate).toContain(authGuard);
    expect(layout?.data?.['requireAdmin']).toBe(true);

    const dashboardRedirect = layout?.children?.find((c) => c.path === '');
    expect(dashboardRedirect?.redirectTo).toBe('dashboard');

    const expectedChildPaths = [
      'dashboard',
      'posts',
      'posts/new',
      'posts/edit/:id',
      'cv-manager',
      'tag-manager',
      'profile',
      'sql',
      'chat',
      'linkedin',
    ];
    for (const path of expectedChildPaths) {
      expect(layout?.children?.find((c) => c.path === path)).toBeDefined();
    }
  });

  it('should redirect unknown routes to the root', () => {
    const wildcard = routes.find((r) => r.path === '**');
    expect(wildcard?.redirectTo).toBe('');
  });

  it('should resolve all lazy-loaded components', async () => {
    const checkLazy = async (routeList: Route[]) => {
      for (const route of routeList) {
        if (route.loadComponent) {
          const component = await route.loadComponent();
          expect(component).toBeDefined();
        }
        if (route.children) {
          await checkLazy(route.children);
        }
      }
    };
    await checkLazy(routes);
  });
});
