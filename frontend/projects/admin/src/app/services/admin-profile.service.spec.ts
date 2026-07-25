import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AdminProfileService } from './admin-profile.service';
import { environment } from '../../environments/environment';

const base = `${environment.apiUrl}${environment.apiPrefix}/admin/profile`;

describe('AdminProfileService', () => {
  let service: AdminProfileService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [AdminProfileService],
    });
    service = TestBed.inject(AdminProfileService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('is created', () => {
    expect(service).toBeTruthy();
  });

  it('uploads a profile with version and language', () => {
    const file = new File(['{}'], 'profile.json', { type: 'application/json' });
    service.uploadProfile(file, 'v1', 'de').subscribe((r) => expect(r).toBeTruthy());

    const req = httpMock.expectOne(`${base}/upload`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.get('version')).toBe('v1');
    expect(req.request.body.get('language')).toBe('de');
    req.flush({ success: true, version: 'v1', language: 'de' });
  });

  it('gets versions without a language filter', () => {
    service.getVersions().subscribe((r) => expect(r.total).toBe(0));
    const req = httpMock.expectOne(
      (r) => r.url === `${base}/versions` && !r.params.has('language'),
    );
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('page')).toBe('1');
    req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
  });

  it('gets versions filtered by language', () => {
    service.getVersions(2, 5, 'created_at', 'asc', 'en').subscribe();
    const req = httpMock.expectOne(
      (r) => r.url === `${base}/versions` && r.params.get('language') === 'en',
    );
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe('5');
    expect(req.request.params.get('sort_order')).toBe('asc');
    req.flush({ items: [], total: 0, page: 2, page_size: 5, total_pages: 1 });
  });

  it('activates a version', () => {
    service.activateVersion('abc').subscribe((r) => expect(r).toBeTruthy());
    const req = httpMock.expectOne(`${base}/versions/abc/activate`);
    expect(req.request.method).toBe('PATCH');
    req.flush({ success: true });
  });
});
