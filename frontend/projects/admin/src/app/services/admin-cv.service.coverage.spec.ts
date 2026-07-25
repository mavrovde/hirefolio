import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AdminCvService } from './admin-cv.service';
import { environment } from '../../environments/environment';

describe('AdminCvService search param branches', () => {
  let service: AdminCvService;
  let httpMock: HttpTestingController;
  const base = `${environment.apiUrl}${environment.apiPrefix}/admin/cv`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AdminCvService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AdminCvService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('getRequests includes search when provided (line 66)', () => {
    service.getRequests(1, 10, 'created_at', 'desc', 'alice').subscribe();
    const req = httpMock.expectOne((r) => r.url === `${base}/requests`);
    expect(req.request.params.get('search')).toBe('alice');
    req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });
  });

  it('getVersions includes search when provided (line 85)', () => {
    service.getVersions(1, 10, 'created_at', 'desc', 'v2').subscribe();
    const req = httpMock.expectOne((r) => r.url === `${base}/versions`);
    expect(req.request.params.get('search')).toBe('v2');
    req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });
  });
});
