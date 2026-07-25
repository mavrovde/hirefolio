import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ProfileService, Profile } from './profile.service';
import { LanguageService } from '@mavrov/shared';
import { MockLanguageService } from '@mavrov/shared/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('ProfileService', () => {
  let service: ProfileService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        ProfileService,
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: LanguageService, useClass: MockLanguageService },
      ],
    });
    service = TestBed.inject(ProfileService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  const dummyProfile: Profile = {
    name: 'John Doe',
    headline: 'Developer',
    location: 'City',
    about: 'Bio',
    contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
    experience: [],
    education: [],
    skills: ['Angular'],
    certifications: [],
    languages: [],
    recommendations: [],
  };

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should fetch the active profile from the backend', () => {
    service.getProfile().subscribe((profile) => {
      expect(profile).toEqual(dummyProfile);
    });

    const req = httpMock.expectOne(
      (r) => r.url.includes('/api/app/profile') && r.method === 'GET',
    );
    expect(req.request.url).toContain('lang=en');
    req.flush(dummyProfile);
  });

  it('should fall back to the static asset when the backend has no profile', () => {
    service.getProfile().subscribe((profile) => {
      expect(profile).toEqual(dummyProfile);
    });

    // Backend returns 404 (no active version) → fall back to the asset.
    const backendReq = httpMock.expectOne((r) => r.url.includes('/api/app/profile'));
    backendReq.flush('Not found', { status: 404, statusText: 'Not Found' });

    const assetReq = httpMock.expectOne((r) => r.url.includes('assets/profile_data_en.json'));
    assetReq.flush(dummyProfile);
  });

  it('should error only when both backend and the asset fail', () => {
    let errorOccurred = false;
    service.getProfile().subscribe({
      next: () => {},
      error: () => {
        errorOccurred = true;
      },
    });

    httpMock
      .expectOne((r) => r.url.includes('/api/app/profile'))
      .flush('err', { status: 500, statusText: 'Server Error' });
    httpMock
      .expectOne((r) => r.url.includes('assets/profile_data_en.json'))
      .flush('err', { status: 500, statusText: 'Server Error' });

    expect(errorOccurred).toBe(true);
  });

  it('should switch language and reload profile from the backend', () => {
    const languageService = TestBed.inject(LanguageService) as unknown as MockLanguageService;

    service.getProfile().subscribe();
    httpMock.match((r) => r.url.includes('lang=en')).forEach((r) => r.flush(dummyProfile));

    languageService.setLanguage('de');

    service.getProfile().subscribe();
    const deReqs = httpMock.match((r) => r.url.includes('lang=de'));
    expect(deReqs.length).toBeGreaterThan(0);
    deReqs[0].flush({ ...dummyProfile, name: 'German Profile' });
  });
});
