import { routes } from './app.routes';
import { describe, it, expect, beforeEach } from 'vitest';
import { provideRouter, Router } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { Location } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

describe('AppRoutes', () => {
    it('should have routes defined', () => {
        expect(routes).toBeDefined();
        expect(Array.isArray(routes)).toBe(true);
        expect(routes.length).toBeGreaterThan(0);
    });

    it('should have all expected top-level routes', () => {
        const expectedPaths = ['', 'llm', 'blog', 'blog/:slug', 'cv'];
        for (const path of expectedPaths) {
            const route = routes.find(r => r.path === path);
            expect(route).toBeDefined();
        }
    });

    it('should render Home eagerly for the root route', () => {
        const home = routes.find(r => r.path === '');
        expect(home?.component).toBeDefined();
        expect(home?.loadComponent).toBeUndefined();
    });

    it('should verify all lazy-loaded components', async () => {
        const checkLazy = async (routeList: any[]) => {
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

describe('AppRoutes Integration', () => {
    let router: Router;
    let location: Location;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [
                provideRouter(routes),
                provideHttpClient(),
                provideHttpClientTesting(),
                provideNoopAnimations(),
            ]
        });

        router = TestBed.inject(Router);
        location = TestBed.inject(Location);
        router.initialNavigation();
    });

    it('should navigate to "" (Home)', async () => {
        await router.navigate(['']);
        expect(location.path()).toBe('');
    });

    it('should navigate to "llm"', async () => {
        await router.navigate(['/llm']);
        expect(location.path()).toBe('/llm');
    });

    it('should navigate to "blog"', async () => {
        await router.navigate(['/blog']);
        expect(location.path()).toBe('/blog');
    });

    it('should navigate to "blog/:slug"', async () => {
        await router.navigate(['/blog/test-post']);
        expect(location.path()).toBe('/blog/test-post');
    });

    it('should navigate to "cv"', async () => {
        await router.navigate(['/cv']);
        expect(location.path()).toBe('/cv');
    });
});
