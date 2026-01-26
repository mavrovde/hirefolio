import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { authGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

describe('AuthGuard', () => {
  let authServiceSpy: { isAuthenticated: Mock; currentUser$: any };
  let routerSpy: { navigate: Mock };

  beforeEach(() => {
    authServiceSpy = {
      isAuthenticated: vi.fn(),
      currentUser$: { pipe: vi.fn() },
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
    expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/login'], expect.anything());
  });

  it('should allow if authenticated', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);

    const result = TestBed.runInInjectionContext(() =>
      authGuard({} as any, { url: '/test' } as any),
    );

    expect(result).toBe(true);
  });
});
