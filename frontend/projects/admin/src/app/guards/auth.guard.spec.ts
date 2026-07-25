import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { authGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { of } from 'rxjs';

describe('AuthGuard', () => {
  let authServiceSpy: { isAuthenticated: Mock; isInitializing$: any; getCurrentUser: Mock };
  let routerSpy: { navigate: Mock };

  beforeEach(() => {
    authServiceSpy = {
      isAuthenticated: vi.fn(),
      isInitializing$: of(false),
      getCurrentUser: vi.fn(),
    };
    routerSpy = { navigate: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authServiceSpy },
        { provide: Router, useValue: routerSpy },
      ],
    });
  });

  it('should redirect if not authenticated', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(false);

    const result = TestBed.runInInjectionContext(() =>
      authGuard({} as any, { url: '/test' } as any),
    );

    expect(result).toBe(false);
    expect(routerSpy.navigate).toHaveBeenCalledWith(['/login'], expect.anything());
  });

  it('should allow if authenticated and no admin requirement', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);

    const result = TestBed.runInInjectionContext(() =>
      authGuard({} as any, { url: '/test' } as any),
    );

    expect(result).toBe(true);
  });

  it('should allow if authenticated and admin user accessing admin route', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    authServiceSpy.getCurrentUser.mockReturnValue({ is_admin: true });

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        { data: { requireAdmin: true } } as any,
        { url: '/dashboard' } as any,
      ),
    );

    // It returns an observable
    if (typeof result === 'object' && 'subscribe' in result) {
      result.subscribe((r) => expect(r).toBe(true));
    } else {
      expect(result).toBe(true); // Should not happen given implementation returns observable
    }
  });

  it('should redirect if authenticated but non-admin user accessing admin route', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    authServiceSpy.getCurrentUser.mockReturnValue({ is_admin: false });

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        { data: { requireAdmin: true } } as any,
        { url: '/dashboard' } as any,
      ),
    );

    if (typeof result === 'object' && 'subscribe' in result) {
      result.subscribe((r) => {
        expect(r).toBe(false);
        expect(routerSpy.navigate).toHaveBeenCalledWith(
          ['/login'],
          expect.anything(),
        );
      });
    }
  });

  it('should redirect if authenticated but user details are missing accessing admin route', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    authServiceSpy.getCurrentUser.mockReturnValue(null);

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        { data: { requireAdmin: true } } as any,
        { url: '/dashboard' } as any,
      ),
    );

    if (typeof result === 'object' && 'subscribe' in result) {
      result.subscribe((r) => {
        expect(r).toBe(false);
        expect(routerSpy.navigate).toHaveBeenCalledWith(
          ['/login'],
          expect.anything(),
        );
      });
    }
  });
});

