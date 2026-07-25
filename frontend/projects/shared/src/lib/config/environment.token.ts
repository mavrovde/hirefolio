import { InjectionToken, Provider } from '@angular/core';

/**
 * Deployment configuration consumed by the shared library's HTTP services.
 * Each host application implements this shape in its own `environment.ts`
 * and supplies it via {@link provideSharedEnvironment}, so the library never
 * imports an app's `environment` file directly (which would break the
 * isolated ng-packagr build and hard-couple the lib to one app).
 */
export interface SharedEnvironment {
  production: boolean;
  apiUrl: string;
  apiPrefix: string;
  googleAnalyticsId: string;
}

export const SHARED_ENVIRONMENT = new InjectionToken<SharedEnvironment>('SHARED_ENVIRONMENT');

/** Register the host application's environment for the shared library. */
export function provideSharedEnvironment(env: SharedEnvironment): Provider {
  return { provide: SHARED_ENVIRONMENT, useValue: env };
}
