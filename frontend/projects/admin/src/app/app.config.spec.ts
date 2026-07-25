import { describe, it, expect } from 'vitest';
import { AUTH_TOKEN_PROVIDER } from '@mavrov/shared';
import { appConfig } from './app.config';
import { AuthService } from './services/auth.service';

describe('AppConfig', () => {
  it('should have required providers', () => {
    expect(appConfig.providers).toBeDefined();
    expect(Array.isArray(appConfig.providers)).toBe(true);
    expect(appConfig.providers.length).toBeGreaterThan(0);
  });

  it('should wire the auth token provider to AuthService.getToken', () => {
    const provider = appConfig.providers.find(
      (p): p is { provide: unknown; useFactory: (auth: AuthService) => () => string | null; deps: unknown[] } =>
        typeof p === 'object' && p !== null && 'provide' in p && p.provide === AUTH_TOKEN_PROVIDER,
    );
    expect(provider).toBeDefined();
    expect(provider?.deps).toContain(AuthService);

    const auth = { getToken: () => 'the-token' } as unknown as AuthService;
    const tokenGetter = provider!.useFactory(auth);
    expect(tokenGetter()).toBe('the-token');
  });
});
