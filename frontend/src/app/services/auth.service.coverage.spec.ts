import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { PLATFORM_ID } from '@angular/core';
import { AuthService } from './auth.service';

describe('AuthService (server platform)', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: PLATFORM_ID, useValue: 'server' },
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
    service = TestBed.inject(AuthService);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('getToken returns null on server without touching localStorage', () => {
    expect(service.getToken()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('setToken is a no-op on server (login stores nothing)', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    // Trigger login flow to exercise the private setToken branch on server
    service.login('u', 'p').subscribe({ error: () => {} });

    const loginReq = httpMock.expectOne((r) => r.url.endsWith('/auth/login'));
    loginReq.flush({ access_token: 'x', token_type: 'bearer', expires_in: 1 });

    // switchMap now fetches /auth/me
    const meReq = httpMock.expectOne((r) => r.url.endsWith('/auth/me'));
    meReq.flush({ id: 1, username: 'u', email: 'u@t.com', is_admin: false });

    expect(setItemSpy).not.toHaveBeenCalledWith('auth_token', expect.anything());
    setItemSpy.mockRestore();
  });

  it('removeToken is a no-op on server (logout does not throw)', () => {
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');
    service.logout();
    expect(removeItemSpy).not.toHaveBeenCalledWith('auth_token');
    removeItemSpy.mockRestore();
    expect(service.getCurrentUser()).toBeNull();
  });
});
