import { TestBed } from '@angular/core/testing';
import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpEvent, HttpHeaders } from '@angular/common/http';
import { ssrInterceptor } from './ssr.interceptor';
import { PLATFORM_ID } from '@angular/core';
import { Observable, of } from 'rxjs';
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('SSRInterceptor', () => {
  let platformId: string;
  let nextMock: HttpHandlerFn;

  beforeEach(() => {
    nextMock = vi.fn().mockReturnValue(of({} as HttpEvent<any>));
  });

  const setupInterceptor = (isServer: boolean) => {
    TestBed.configureTestingModule({
      providers: [
        { provide: PLATFORM_ID, useValue: isServer ? 'server' : 'browser' }
      ]
    });
    
    return (req: HttpRequest<any>) => {
      let result: any;
      TestBed.runInInjectionContext(() => {
        result = ssrInterceptor(req, nextMock);
      });
      return result;
    };
  };

  it('should pass request unmodified if running in browser', () => {
    const runInterceptor = setupInterceptor(false);
    const req = new HttpRequest('GET', '/api/test');
    
    runInterceptor(req);
    
    expect(nextMock).toHaveBeenCalledWith(req);
  });

  it('should pass request unmodified if url is already absolute HTTP in server', () => {
    const runInterceptor = setupInterceptor(true);
    const req = new HttpRequest('GET', 'http://external.com/api/test');
    
    runInterceptor(req);
    
    expect(nextMock).toHaveBeenCalledWith(req);
  });
  
  it('should pass request unmodified if url is already absolute HTTPS in server', () => {
    const runInterceptor = setupInterceptor(true);
    const req = new HttpRequest('GET', 'https://external.com/api/test');
    
    runInterceptor(req);
    
    expect(nextMock).toHaveBeenCalledWith(req);
  });

  it('should prefix relative /api URLs with backend container DNS in server', () => {
    const runInterceptor = setupInterceptor(true);
    const req = new HttpRequest('GET', '/api/test');
    
    runInterceptor(req);
    
    const calledReq = vi.mocked(nextMock).mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://backend:8000/api/test');
  });

  it('should prefix relative api/ URLs with backend container DNS in server', () => {
    const runInterceptor = setupInterceptor(true);
    const req = new HttpRequest('GET', 'api/test');
    
    runInterceptor(req);
    
    const calledReq = vi.mocked(nextMock).mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://backend:8000/api/test');
  });

  it('should prefix other relative URLs with local SSR container DNS in server', () => {
    const runInterceptor = setupInterceptor(true);
    const req = new HttpRequest('GET', 'assets/data.json');
    
    runInterceptor(req);
    
    const calledReq = vi.mocked(nextMock).mock.calls[0][0] as HttpRequest<any>;
    expect(calledReq.url).toBe('http://127.0.0.1:4000/assets/data.json');
  });

});
