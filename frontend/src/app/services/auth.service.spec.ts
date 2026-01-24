import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

describe('AuthService', () => {
    let service: AuthService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.resetTestingModule(); // Ensure clean slate

        // Clear localStorage before each test
        const store: { [key: string]: string } = {};
        const mockLocalStorage = {
            getItem: (key: string): string | null => {
                return key in store ? store[key] : null;
            },
            setItem: (key: string, value: string) => {
                store[key] = `${value}`;
            },
            removeItem: (key: string) => {
                delete store[key];
            }
        };

        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(mockLocalStorage.getItem);
        vi.spyOn(Storage.prototype, 'setItem').mockImplementation(mockLocalStorage.setItem);
        vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(mockLocalStorage.removeItem);

        TestBed.configureTestingModule({
            providers: [
                AuthService,
                provideHttpClient(),
                provideHttpClientTesting()
            ]
        });
        service = TestBed.inject(AuthService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        vi.restoreAllMocks();
        if (httpMock) {
            httpMock.verify();
        }
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    describe('login', () => {
        it('should call api/auth/login and store token on success', () => {
            const mockResponse = {
                access_token: 'fake-token',
                token_type: 'bearer',
                expires_in: 3600
            };

            // Mock setUser logic which happens after login
            const mockUser = { id: 1, username: 'user', email: 'u@test.com', is_admin: true };

            service.login('test', 'pass').subscribe(res => {
                expect(res).toEqual(mockResponse);
            });

            const req = httpMock.expectOne(`${environment.apiUrl}/api/auth/login`);
            expect(req.request.method).toBe('POST');
            expect(req.request.body.toString()).toContain('username=test');
            expect(req.request.body.toString()).toContain('password=pass');
            req.flush(mockResponse);

            // It subsequently calls /me
            const meReq = httpMock.expectOne(`${environment.apiUrl}/api/auth/me`);
            meReq.flush(mockUser);

            expect(window.localStorage.setItem).toHaveBeenCalledWith('auth_token', 'fake-token');
        });
    });

    describe('logout', () => {
        it('should remove token and clear current user', () => {
            service.logout();
            expect(window.localStorage.removeItem).toHaveBeenCalledWith('auth_token');
            expect(service.getCurrentUser()).toBeNull();
        });
    });

    describe('initialization', () => {
        it('should load user if token exists', () => {
            // Mock token existing - verify spy is working
            const store: { [key: string]: string } = { 'auth_token': 'existing-token' };
            vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key: string) => store[key] || null);

            // Re-inject to trigger constructor
            TestBed.resetTestingModule();
            TestBed.configureTestingModule({
                providers: [
                    AuthService,
                    provideHttpClient(),
                    provideHttpClientTesting()
                ]
            });
            const newService = TestBed.inject(AuthService);
            const newHttpMock = TestBed.inject(HttpTestingController);

            const req = newHttpMock.expectOne(`${environment.apiUrl}/api/auth/me`);
            req.flush({ id: 1, username: 'loaded', email: 'l@test.com', is_admin: false });

            expect(newService.getCurrentUser()?.username).toBe('loaded');
            newHttpMock.verify();
        });

        it('should logout if loading user fails', () => {
            // Mock token existing
            const store: { [key: string]: string } = { 'auth_token': 'bad-token' };
            vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key: string) => store[key] || null);

            TestBed.resetTestingModule();
            TestBed.configureTestingModule({
                providers: [
                    AuthService,
                    provideHttpClient(),
                    provideHttpClientTesting()
                ]
            });
            const newService = TestBed.inject(AuthService);
            const newHttpMock = TestBed.inject(HttpTestingController);

            const spyLogout = vi.spyOn(newService, 'logout');

            const req = newHttpMock.expectOne(`${environment.apiUrl}/api/auth/me`);
            req.flush('Error', { status: 401, statusText: 'Unauthorized' });

            expect(spyLogout).toHaveBeenCalled();
            newHttpMock.verify();
        });
    });

    describe('helpers', () => {
        it('isAuthenticated should return true if token exists', () => {
            vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('token');
            expect(service.isAuthenticated()).toBe(true);
        });

        it('isAuthenticated should return false if token missing', () => {
            vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
            expect(service.isAuthenticated()).toBe(false);
        });

        it('isAdmin should return true if user is admin', () => {
            // Manually set internal state since it's private but accessible via next() in our test theory if exposed, 
            // or effectively by loading user.
            // Easier way: mock the subject or trigger a load.
            // Let's rely on the public observable behavior or "any" cast if needed, but cleaner to trigger load.

            // Simulating logged in state
            const mockUser = { id: 1, username: 'admin', email: 'admin@test.com', is_admin: true };

            // We can simulate a successful login to set the state
            service['currentUserSubject'].next(mockUser);

            expect(service.isAdmin()).toBe(true);
        });

        it('isAdmin should return false if user is not admin or null', () => {
            service['currentUserSubject'].next(null);
            expect(service.isAdmin()).toBe(false);

            service['currentUserSubject'].next({ id: 2, username: 'user', email: 'u@test.com', is_admin: false });
            expect(service.isAdmin()).toBe(false);
        });
    });
});
