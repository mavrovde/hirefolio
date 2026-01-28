import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { LanguageService } from './language.service';
import { StorageService } from './storage.service';
import { firstValueFrom } from 'rxjs';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

describe('LanguageService', () => {
  let service: LanguageService;
  let httpMock: HttpTestingController;
  let storageServiceMock: any;

  beforeEach(() => {
    storageServiceMock = {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
    };

    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        LanguageService,
        { provide: StorageService, useValue: storageServiceMock },
      ],
    });
    service = TestBed.inject(LanguageService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should load default language on init', () => {
    const req = httpMock.expectOne('/assets/i18n/en.json');
    expect(req.request.method).toBe('GET');
    req.flush({ TEST: 'Test' });
    expect(service.getCurrentLanguage()).toBe('en');
  });

  it('should translate correctly using nested keys', async () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({ NAV: { LLM: 'LLM Support' } });

    const translation = await firstValueFrom(service.translate('NAV.LLM'));
    expect(translation).toBe('LLM Support');
  });

  it('should return the key if translation is missing', async () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({});

    const translation = await firstValueFrom(service.translate('MISSING.KEY'));
    expect(translation).toBe('MISSING.KEY');
  });

  it('should handle malformed keys gracefully', async () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({ A: { B: 'C' } });

    // Path that exists then stops
    const t1 = await firstValueFrom(service.translate('A.B.D'));
    expect(t1).toBe('A.B.D');
  });

  it('should load translations when setting language', () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({});

    service.setLanguage('de');
    const deReq = httpMock.expectOne('/assets/i18n/de.json');
    deReq.flush({ TEST: 'Deutsch' });

    expect(service.getCurrentLanguage()).toBe('de');
  });

  it('should not reload if setting same language', () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({});

    service.setLanguage('en');
    httpMock.expectNone('/assets/i18n/en.json');
    // It should NOT try to set storage if logic prevents redundant setLanguage
    // But implementation says: if (current != lang)
    // So if current is 'en', setLanguage('en') does nothing.
  });

  it('should persist language on setLanguage', () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({});

    service.setLanguage('de');
    const deReq = httpMock.expectOne('/assets/i18n/de.json');
    deReq.flush({});

    expect(storageServiceMock.setItem).toHaveBeenCalledWith('language', 'de');
  });

  it('should handle http error gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.error(new ProgressEvent('Network Error'));

    // Should still emit empty object (fallback)
    const translation = await firstValueFrom(service.translate('ANY'));
    expect(translation).toBe('ANY');
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it('should return multiple results when translations change', async () => {
    const initReq = httpMock.expectOne('/assets/i18n/en.json');
    initReq.flush({ KEY: 'Initial' });

    const results: string[] = [];
    const sub = service.translate('KEY').subscribe(val => results.push(val));

    expect(results[0]).toBe('Initial');

    // Trigger second change
    service.setLanguage('de');
    const deReq = httpMock.expectOne('/assets/i18n/de.json');
    deReq.flush({ KEY: 'Deutsch' });

    expect(results[1]).toBe('Deutsch');
    sub.unsubscribe();
  });
});
