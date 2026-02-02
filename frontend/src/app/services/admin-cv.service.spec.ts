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

        const req = httpMock.expectOne(`${environment.apiUrl}/api/admin/cv/upload`);
        expect(req.request.method).toBe('POST');
        expect(req.request.body.get('version')).toBe(version);
        req.flush({ success: true });
    });

    it('should get requests', () => {
        const mockRequests = [{ id: '1', name: 'Test', email: 'test@test.com' }];

        service.getRequests().subscribe(requests => {
            expect(requests.length).toBe(1);
            expect(requests[0].name).toBe('Test');
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/api/admin/cv/requests`);
        expect(req.request.method).toBe('GET');
        req.flush(mockRequests);
    });

    it('should get versions', () => {
        const mockVersions = [{ id: '1', version: 'v1.0', is_active: true }];

        service.getVersions().subscribe(versions => {
            expect(versions.length).toBe(1);
            expect(versions[0].version).toBe('v1.0');
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/api/admin/cv/versions`);
        expect(req.request.method).toBe('GET');
        req.flush(mockVersions);
    });
});
