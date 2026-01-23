import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { LanguageService } from './language.service';

describe('LanguageService', () => {
    let service: LanguageService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [LanguageService]
        });
        service = TestBed.inject(LanguageService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        const req = httpMock.expectOne('assets/i18n/en.json');
        expect(req.request.method).toBe('GET');
        req.flush({});
        expect(service).toBeTruthy();
    });

    it('should load translations on init', () => {
        const req = httpMock.expectOne('assets/i18n/en.json');
        expect(req.request.method).toBe('GET');
        req.flush({ HELLO: 'Hello' });

        service.translations$.subscribe(translations => {
            expect(translations['HELLO']).toBe('Hello');
        });
    });

    it('should switch language', () => {
        const req1 = httpMock.expectOne('assets/i18n/en.json');
        req1.flush({});

        service.setLanguage('de');

        const req2 = httpMock.expectOne('assets/i18n/de.json');
        expect(req2.request.method).toBe('GET');
        req2.flush({ HELLO: 'Hallo' });

        expect(service.getCurrentLanguage()).toBe('de');
    });
});
