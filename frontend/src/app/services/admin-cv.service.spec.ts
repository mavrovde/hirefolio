import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AdminCvService } from './admin-cv.service';
import { environment } from '../../environments/environment';

describe('AdminCvService', () => {
    let service: AdminCvService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [AdminCvService]
        });
        service = TestBed.inject(AdminCvService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should upload CV', () => {
        const file = new File([''], 'test.pdf', { type: 'application/pdf' });
        const version = 'v1.0';

        service.uploadCv(file, version).subscribe(response => {
            expect(response).toBeTruthy();
        });

        const req = httpMock.expectOne(`${environment.apiUrl}${environment.apiPrefix}/admin/cv/upload`);
        expect(req.request.method).toBe('POST');
        expect(req.request.body.get('version')).toBe(version);
        req.flush({ success: true });
    });

    it('should get requests with pagination params', () => {
        const mockResponse = {
            items: [{ id: '1', name: 'Test', email: 'test@test.com', company: '', message: '', created_at: '', consent_given: true, cv_version: '' }],
            total: 1,
            page: 1,
            page_size: 10,
            total_pages: 1
        };

        service.getRequests(1, 10, 'created_at', 'desc', null).subscribe(response => {
            expect(response.items.length).toBe(1);
            expect(response.items[0].name).toBe('Test');
            expect(response.total).toBe(1);
        });

        const req = httpMock.expectOne((request) => request.url === `${environment.apiUrl}${environment.apiPrefix}/admin/cv/requests`);
        expect(req.request.method).toBe('GET');
        expect(req.request.params.get('page')).toBe('1');
        expect(req.request.params.get('page_size')).toBe('10');
        req.flush(mockResponse);
    });

    it('should get versions with pagination params', () => {
        const mockResponse = {
            items: [{ id: '1', version: 'v1.0', is_active: true, filename: 'test.pdf', created_at: '' }],
            total: 1,
            page: 1,
            page_size: 10,
            total_pages: 1
        };

        service.getVersions(1, 10, 'created_at', 'desc', null).subscribe(response => {
            expect(response.items.length).toBe(1);
            expect(response.items[0].version).toBe('v1.0');
            expect(response.total).toBe(1);
        });

        const req = httpMock.expectOne((request) => request.url === `${environment.apiUrl}${environment.apiPrefix}/admin/cv/versions`);
        expect(req.request.method).toBe('GET');
        expect(req.request.params.get('page')).toBe('1');
        expect(req.request.params.get('page_size')).toBe('10');
        req.flush(mockResponse);
    });
});
