import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { ActivatedRoute } from '@angular/router';
import { PLATFORM_ID } from '@angular/core';
import { HomeComponent } from './home.component';
import { ProfileService } from '../../services/profile.service';
import { LanguageService } from '../../services/language.service';
import { SeoService } from '../../services/seo.service';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { of } from 'rxjs';
import { MockLanguageService } from '../../testing/mock-language.service';

function makeProfile(overrides: any) {
  return {
    name: 'Test',
    headline: 'Headline',
    location: 'Loc',
    about: 'About',
    contact: { email: 'e', linkedin: 'l' },
    experience: [],
    education: [],
    skills: ['Angular'],
    certifications: [],
    languages: [],
    recommendations: [],
    ...overrides,
  };
}

describe('HomeComponent description fallback branches', () => {
  function setup(profile: any, platform: 'browser' | 'server' = 'server') {
    TestBed.configureTestingModule({
      imports: [HomeComponent, HttpClientTestingModule],
      providers: [
        { provide: ProfileService, useValue: { getProfile: () => of(profile) } },
        { provide: LanguageService, useClass: MockLanguageService },
        { provide: ActivatedRoute, useValue: { snapshot: { fragment: null } } },
        { provide: PLATFORM_ID, useValue: platform },
      ],
    });
    const fixture: ComponentFixture<HomeComponent> = TestBed.createComponent(HomeComponent);
    return fixture;
  }

  it('uses headline when about is empty', () => {
    const fixture = setup(makeProfile({ about: '' }));
    const seo = TestBed.inject(SeoService);
    const spy = vi.spyOn(seo, 'updateSeo');
    fixture.detectChanges();
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ description: 'Headline' }));
  });

  it('uses default string when about and headline are empty', () => {
    const fixture = setup(makeProfile({ about: '', headline: '' }));
    const seo = TestBed.inject(SeoService);
    const spy = vi.spyOn(seo, 'updateSeo');
    fixture.detectChanges();
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        description: 'Professional portfolio of Sergii Mavrov, a Principal Software Engineer.',
      }),
    );
  });

  it('does not update SEO when the profile is null (line 71 false branch)', () => {
    const fixture = setup(null);
    const seo = TestBed.inject(SeoService);
    const spy = vi.spyOn(seo, 'updateSeo');
    fixture.detectChanges();
    expect(spy).not.toHaveBeenCalled();
  });

  it('runs scroll logic on browser platform', () => {
    vi.useFakeTimers();
    const fixture = setup(makeProfile({}), 'browser');
    fixture.detectChanges();
    // initScrollLogic starts an interval; with a null fragment it clears on the first tick
    vi.advanceTimersByTime(200);
    expect(fixture.componentInstance).toBeTruthy();
    vi.useRealTimers();
  });
});

afterEach(() => {
  vi.useRealTimers();
});
