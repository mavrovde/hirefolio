import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import { HttpBackend, provideHttpClient } from '@angular/common/http';
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
    // already computed its cache key from the original (server/client-identical)
    // request URL — so the browser reuses the SSR-cached response on hydration
    // instead of re-fetching (fixes the blog "flash to home", #25). The backend
    // delegates to `HttpXhrBackend`, keeping the browser on its long-working XHR
    // path (so the `/stats/public` browser fetch keeps working, #94). See
    // ssr-http-backend.ts for the full rationale.
    provideHttpClient(),
    { provide: HttpBackend, useClass: SsrHttpBackend },
    provideClientHydration(withEventReplay()),
    provideSharedEnvironment(environment),
    provideAuthTokenProvider(() => null),
  ],
};
