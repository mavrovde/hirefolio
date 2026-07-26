import { TestBed } from '@angular/core/testing';
import { FetchBackend, HttpRequest } from '@angular/common/http';
import { PLATFORM_ID } from '@angular/core';
import { of } from 'rxjs';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SsrHttpBackend } from './ssr-http-backend';

describe('SsrHttpBackend', () => {
  let fetchBackendSpy: { handle: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    fetchBackendSpy = { handle: vi.fn().mockReturnValue(of({} as any)) };
  });

  const createBackend = (isServer: boolean) => {
    TestBed.configureTestingModule({
      providers: [
        SsrHttpBackend,
        { provide: FetchBackend, useValue: fetchBackendSpy },
        { provide: PLATFORM_ID, useValue: isServer ? 'server' : 'browser' },
      ],
    });
    return TestBed.inject(SsrHttpBackend);
  };

  it('dispatches the request unmodified when running in the browser', () => {
    const backend = createBackend(false);
    const req = new HttpRequest('GET', '/api/test');

    backend.handle(req);

    expect(fetchBackendSpy.handle).toHaveBeenCalledWith(req);
  });

  it('dispatches the request unmodified if the url is already absolute HTTP on the server', () => {
    const backend = createBackend(true);
    const req = new HttpRequest('GET', 'http://external.com/api/test');

    backend.handle(req);

    expect(fetchBackendSpy.handle).toHaveBeenCalledWith(req);
  });

  it('dispatches the request unmodified if the url is already absolute HTTPS on the server', () => {
    const backend = createBackend(true);
    const req = new HttpRequest('GET', 'https://external.com/api/test');

    backend.handle(req);

    expect(fetchBackendSpy.handle).toHaveBeenCalledWith(req);
  });

  it('prefixes relative /api urls with the backend container DNS on the server', () => {
    const backend = createBackend(true);
    const req = new HttpRequest('GET', '/api/test');

    backend.handle(req);

    const calledReq = fetchBackendSpy.handle.mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://backend:8000/api/test');
  });

  it('prefixes relative api/ urls with the backend container DNS on the server', () => {
    const backend = createBackend(true);
    const req = new HttpRequest('GET', 'api/test');

    backend.handle(req);

    const calledReq = fetchBackendSpy.handle.mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://backend:8000/api/test');
  });

  it('prefixes other relative urls with the local SSR container DNS on the server', () => {
    const backend = createBackend(true);
    const req = new HttpRequest('GET', 'assets/data.json');

    backend.handle(req);

    const calledReq = fetchBackendSpy.handle.mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://127.0.0.1:4000/assets/data.json');
  });

  it('prefixes absolute-path non-API urls with the local SSR container DNS on the server', () => {
    const backend = createBackend(true);
    const req = new HttpRequest('GET', '/assets/data.json');

    backend.handle(req);

    const calledReq = fetchBackendSpy.handle.mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://127.0.0.1:4000/assets/data.json');
  });

  it('does not mutate the request url used by the (root-level) HTTP transfer cache — regression #25', () => {
    // The whole point of moving the rewrite from an interceptor into the
    // HttpBackend is that Angular's transfer-cache interceptor computes its
    // cache key from `req.url` *before* handing off to the backend. As long
    // as this backend only rewrites the URL it forwards to `FetchBackend`
    // (and never mutates the object passed in), the transfer cache sees the
    // same relative URL on the server and the client, so the client can
    // reuse the SSR-cached response instead of re-fetching on hydration.
    const backend = createBackend(true);
    const req = new HttpRequest('GET', '/api/app/posts/my-post');

    backend.handle(req);

    expect(req.url).toBe('/api/app/posts/my-post');
    const calledReq = fetchBackendSpy.handle.mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://backend:8000/api/app/posts/my-post');
    expect(calledReq).not.toBe(req);
  });
});
