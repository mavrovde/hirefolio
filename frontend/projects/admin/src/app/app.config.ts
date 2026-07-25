import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { authInterceptor } from './interceptors/auth.interceptor';
import { AuthService } from './services/auth.service';
import { AUTH_TOKEN_PROVIDER, provideSharedEnvironment } from '@mavrov/shared';
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
    // Admin app carries the auth interceptor (attaches Bearer, handles 401/403).
    provideHttpClient(withInterceptors([authInterceptor])),
    provideSharedEnvironment(environment),
    // Feed the shared library's Gemini calls the admin bearer token.
    {
      provide: AUTH_TOKEN_PROVIDER,
      useFactory: (auth: AuthService) => () => auth.getToken(),
      deps: [AuthService],
    },
  ],
};
