import { appConfig } from './app.config';
import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { AUTH_TOKEN_PROVIDER } from '@mavrov/shared';

describe('AppConfig', () => {
    it('should have required providers', () => {
        expect(appConfig.providers).toBeDefined();
        expect(Array.isArray(appConfig.providers)).toBe(true);
        expect(appConfig.providers.length).toBeGreaterThan(0);
    });

    it('registers an auth token provider that yields null (public app is unauthenticated)', () => {
        TestBed.configureTestingModule({ providers: [...(appConfig.providers as unknown[])] as never });
        const authTokenProvider = TestBed.inject(AUTH_TOKEN_PROVIDER);
        expect(authTokenProvider()).toBeNull();
    });
});
