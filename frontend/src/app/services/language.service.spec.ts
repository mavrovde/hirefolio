import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { LanguageService } from './language.service';

describe('LanguageService', () => {
  let service: LanguageService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [LanguageService],
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

    service.translations$.subscribe((translations) => {
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

  it('should handle missing translation files', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const req1 = httpMock.expectOne('assets/i18n/en.json');
    req1.flush({});

    service.setLanguage('de');

    const req2 = httpMock.expectOne('assets/i18n/de.json');
    req2.error(new ProgressEvent('error'));

    // Should still work despite error
    expect(service.getCurrentLanguage()).toBe('de');
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it('should provide translation observable', () => {
    const req = httpMock.expectOne('assets/i18n/en.json');
    req.flush({ TEST_KEY: 'Test Value' });

    service.translations$.subscribe((translations) => {
      expect(translations['TEST_KEY']).toBe('Test Value');
    });
  });

  it('should emit current language', () => {
    const req = httpMock.expectOne('assets/i18n/en.json');
    req.flush({});

    service.currentLang$.subscribe((lang) => {
      expect(lang).toBe('en');
    });
  });

  it('should handle rapid language switches', () => {
    const req1 = httpMock.expectOne('assets/i18n/en.json');
    req1.flush({});

    service.setLanguage('de');
    service.setLanguage('en');
    service.setLanguage('de');

    // Should handle multiple requests
    const deRequests = httpMock.match('assets/i18n/de.json');
    const enRequests = httpMock.match('assets/i18n/en.json');

    deRequests.forEach((req) => req.flush({}));
    enRequests.forEach((req) => req.flush({}));

    expect(service.getCurrentLanguage()).toBe('de');
  });
});
