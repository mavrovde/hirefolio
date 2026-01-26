import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ProfileService, Profile } from './profile.service';
import { LanguageService } from './language.service';
import { MockLanguageService } from '../testing/mock-language.service';
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

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should fetch profile data from assets', () => {
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

    service.getProfile().subscribe((profile) => {
      expect(profile).toEqual(dummyProfile);
    });

    // Expect a request to the assets file
    const req = httpMock.expectOne(
      (req) => req.url.includes('assets/profile_data') && req.method === 'GET',
    );
    req.flush(dummyProfile);
  });

  it('should handle HTTP errors gracefully', () => {
    let errorOccurred = false;

    service.getProfile().subscribe({
      next: () => {},
      error: (error) => {
        expect(error).toBeTruthy();
        errorOccurred = true;
      },
    });

    const req = httpMock.expectOne((req) => req.url.includes('assets/profile_data'));
    req.flush('Error', { status: 500, statusText: 'Server Error' });

    expect(errorOccurred).toBe(true);
  });

  it('should switch language and reload profile', () => {
    const languageService = TestBed.inject(LanguageService) as unknown as MockLanguageService;

    // Initial load (default language en)
    service.getProfile().subscribe();

    const reqs = httpMock.match((req) => req.url.endsWith('en.json'));
    if (reqs.length > 0) {
      reqs[0].flush({ name: 'English Profile' } as any);
    }

    // Switch language
    languageService.setLanguage('de');

    // Should load German profile
    service.getProfile().subscribe();

    const reqs2 = httpMock.match((req) => req.url.endsWith('de.json'));
    expect(reqs2.length).toBeGreaterThan(0);
    reqs2[0].flush({ name: 'German Profile' } as any);
  });
});
