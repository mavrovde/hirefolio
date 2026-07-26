import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import { HttpBackend, provideHttpClient, withFetch } from '@angular/common/http';
import { provideClientHydration, withEventReplay } from '@angular/platform-browser';

import { routes } from './app.routes';
import { SsrHttpBackend } from './interceptors/ssr-http-backend';
import { provideSharedEnvironment, provideAuthTokenProvider } from '@mavrov/shared';
import { environment } from '../environments/environment';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withInMemoryScrolling({
        anchorScrolling: 'enabled',
        scrollPositionRestoration: 'enabled',
      })
    ),
    // Public app is unauthenticated: no auth interceptor needed. The SSR
    // URL-rewriting (relative -> absolute container addresses) happens in
    // `SsrHttpBackend`, *after* Angular's HTTP transfer-cache interceptor has
    // already computed its cache key from the original (server/client
    // identical) request URL — see ssr-http-backend.ts for why this must not
    // be done in an `HttpInterceptorFn`.
    // `withFetch()` is REQUIRED: `SsrHttpBackend` (below) delegates to
    // `FetchBackend`, which is only fully wired (its `FetchFactory`) when the
    // fetch backend is explicitly enabled. Without it, browser requests issued
    // through the overridden `HttpBackend` fail at the network layer
    // (`net::ERR_FAILED`) — see issue #94 (the footer `/stats/public` call, the
    // app's only genuine client-side fetch, was the visible casualty).
    provideHttpClient(withFetch()),
    { provide: HttpBackend, useClass: SsrHttpBackend },
    provideClientHydration(withEventReplay()),
    provideSharedEnvironment(environment),
    provideAuthTokenProvider(() => null),
  ],
};
