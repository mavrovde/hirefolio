import { HttpInterceptorFn } from '@angular/common/http';
import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformServer } from '@angular/common';

export const ssrInterceptor: HttpInterceptorFn = (req, next) => {
  const platformId = inject(PLATFORM_ID);

  if (isPlatformServer(platformId)) {
    // In SSR, we might need to convert relative URLs to absolute.
    // However, if it's already an absolute HTTP URL, leave it alone.
    if (!req.url.startsWith('http')) {
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
  }

  return next(req);
};
