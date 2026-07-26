import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformServer } from '@angular/common';
import { FetchBackend, HttpBackend, HttpEvent, HttpRequest } from '@angular/common/http';
import { Observable } from 'rxjs';

/**
 * Rewrites relative API/asset URLs to absolute, container-internal addresses
 * during SSR — but only at the point the request is actually dispatched to
 * the network, i.e. inside the `HttpBackend`, not in an `HttpInterceptorFn`.
 *
 * This used to live in an `HttpInterceptorFn` (see the removed
 * `ssr.interceptor.ts`). Interceptors registered via `withInterceptors()` run
 * *before* Angular's HTTP transfer-cache interceptor (which is a root-level
 * interceptor appended after all feature interceptors in the chain). That
 * meant:
 *  - during the SSR render, the transfer cache computed its cache key from
 *    the *rewritten* absolute URL (e.g. `http://backend:8000/api/app/posts/x`)
 *  - during hydration in the browser, the transfer cache computed its key
 *    from the *original* relative URL (`/api/app/posts/x`)
 *
 * The two keys never matched, so the browser never found the SSR-cached
 * response and always re-fetched every request on hydration — including the
 * blog post fetch. Any transient failure of that unnecessary re-fetch then
 * bounced the visitor back to `/` (see `BlogPostComponent`), producing the
 * "flash to home" behaviour described in issue #25.
 *
 * Doing the rewrite here, in the `HttpBackend`, happens *after* the transfer
 * cache interceptor has already read/written its entry (keyed on the
 * original URL, which is identical on the server and the client). The client
 * therefore reuses the SSR response instead of re-fetching.
 */
@Injectable()
export class SsrHttpBackend implements HttpBackend {
  constructor(
    private readonly fetchBackend: FetchBackend,
    @Inject(PLATFORM_ID) private readonly platformId: Object,
  ) {}

  handle(req: HttpRequest<any>): Observable<HttpEvent<any>> {
    if (isPlatformServer(this.platformId) && !req.url.startsWith('http')) {
      let absoluteUrl = req.url;
      if (req.url.startsWith('/api')) {
        absoluteUrl = `http://backend:8000${req.url}`;
      } else if (req.url.startsWith('api/')) {
        absoluteUrl = `http://backend:8000/${req.url}`;
      } else {
        // Assets or other non-API routes should be fetched from the Angular SSR server itself
        const prefix = req.url.startsWith('/') ? '' : '/';
        absoluteUrl = `http://127.0.0.1:4000${prefix}${req.url}`;
      }

      req = req.clone({ url: absoluteUrl });
    }

    return this.fetchBackend.handle(req);
  }
}
