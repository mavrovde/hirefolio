import { routes } from './app.routes';
import { authGuard } from './guards/auth.guard';
import { describe, it, expect, beforeEach } from 'vitest';
import { provideRouter, Router } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { Location } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Component } from '@angular/core';

@Component({ template: '' }) class MockComponent { }

describe('AppRoutes', () => {
    it('should have routes defined', () => {
        expect(routes).toBeDefined();
        expect(Array.isArray(routes)).toBe(true);
        expect(routes.length).toBeGreaterThan(0);
    });

    it('should have all expected top-level routes', () => {
        const expectedPaths = ['', 'llm', 'blog', 'blog/:slug', 'cv', 'admin/login', 'admin'];
        for (const path of expectedPaths) {
            const route = routes.find(r => r.path === path);
            expect(route).toBeDefined();
        }
    });

    it('should have an admin route with guards and children', () => {
        const adminRoute = routes.find(r => r.path === 'admin');
        expect(adminRoute).toBeDefined();
        expect(adminRoute?.canActivate).toContain(authGuard);
        expect(adminRoute?.children).toBeDefined();

        const dashboardRedirect = adminRoute?.children?.find(c => c.path === '');
        expect(dashboardRedirect?.redirectTo).toBe('dashboard');

        const expectedChildPaths = ['dashboard', 'posts', 'posts/new', 'posts/edit/:id', 'cv-manager', 'profile'];
        for (const path of expectedChildPaths) {
            const childRoute = adminRoute?.children?.find(c => c.path === path);
            expect(childRoute).toBeDefined();
        }
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
                { provide: authGuard, useValue: () => true } // simple bypass for testing navigation
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

    it('should navigate to "cv"', async () => {
        await router.navigate(['/cv']);
        expect(location.path()).toBe('/cv');
    });

    it('should navigate to "admin/login"', async () => {
        await router.navigate(['/admin/login']);
        expect(location.path()).toBe('/admin/login');
    });

    it('should navigate to "admin/dashboard"', async () => {
        await router.navigate(['/admin/dashboard']);
        expect(location.path()).toBe('/admin/dashboard');
    });

    it('should navigate to "admin/posts"', async () => {
        await router.navigate(['/admin/posts']);
        expect(location.path()).toBe('/admin/posts');
    });

    it('should navigate to "admin/posts/new"', async () => {
        await router.navigate(['/admin/posts/new']);
        expect(location.path()).toBe('/admin/posts/new');
    });

    it('should navigate to "blog/:slug"', async () => {
        await router.navigate(['/blog/test-post']);
        expect(location.path()).toBe('/blog/test-post');
    });

    it('should navigate to "admin/posts/edit/:id"', async () => {
        await router.navigate(['/admin/posts/edit/1']);
        expect(location.path()).toBe('/admin/posts/edit/1');
    });

    it('should navigate to "admin/cv-manager"', async () => {
        await router.navigate(['/admin/cv-manager']);
        expect(location.path()).toBe('/admin/cv-manager');
    });

    it('should navigate to "admin/profile"', async () => {
        await router.navigate(['/admin/profile']);
        expect(location.path()).toBe('/admin/profile');
    });
});
