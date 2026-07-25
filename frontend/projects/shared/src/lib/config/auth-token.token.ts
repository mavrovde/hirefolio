import { InjectionToken, Provider } from '@angular/core';

/**
 * Supplies the current bearer token (or null) to shared services that make
 * authenticated calls (e.g. LlmService.chatGemini). This decouples the shared
 * library from the admin app's AuthService: the public app provides a
 * `() => null` factory, the admin app wires it to its AuthService.
 */
export type AuthTokenProvider = () => string | null;

export const AUTH_TOKEN_PROVIDER = new InjectionToken<AuthTokenProvider>('AUTH_TOKEN_PROVIDER');

/** Register an auth-token provider for the shared library. */
export function provideAuthTokenProvider(factory: AuthTokenProvider): Provider {
  return { provide: AUTH_TOKEN_PROVIDER, useValue: factory };
}
