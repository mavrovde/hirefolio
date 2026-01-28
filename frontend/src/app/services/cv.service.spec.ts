import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { CvService } from './cv.service';
import { environment } from '../../environments/environment';

describe('CvService', () => {
    let service: CvService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [CvService]
        });
        service = TestBed.inject(CvService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should send CV request', () => {
        const mockRequest = {
            name: 'John Doe',
            email: 'john@example.com',
            message: 'Hello',
            company: 'Test Corp'
        };

        const mockResponse = {
            success: true,
            message: 'Sent',
            download_url: '/api/static/cv.pdf'
        };

        service.requestCv(mockRequest).subscribe(response => {
            expect(response).toEqual(mockResponse);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/api/cv/request`);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual(mockRequest);
        req.flush(mockResponse);
    });

    it('should format download URL', () => {
        const relative = '/api/download/cv.pdf';
        const expected = `${environment.apiUrl}${relative}`;
        expect(service.getDownloadUrl(relative)).toBe(expected);
    });

    it('should return absolute URL as is', () => {
        const absolute = 'http://example.com/cv.pdf';
        expect(service.getDownloadUrl(absolute)).toBe(absolute);
    });
});
