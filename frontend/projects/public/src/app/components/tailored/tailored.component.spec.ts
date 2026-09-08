import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { PLATFORM_ID, RESPONSE_INIT } from '@angular/core';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { BehaviorSubject, of, throwError } from 'rxjs';
// `describe`/`it`/`beforeEach` come from the GLOBALS on purpose: zone.js/testing
// patches those, and `fakeAsync` needs the ProxyZone they install. Importing
// them from 'vitest' bypasses the patch and every fakeAsync test fails with
// "Expected to be running in 'ProxyZone'".
import { vi } from 'vitest';
import { LanguageService, provideSharedEnvironment } from '@mavrov/shared';
import { MockLanguageService } from '@mavrov/shared/testing';

import { TailoredComponent } from './tailored.component';
import { Profile, ProfileService } from '../../services/profile.service';
import { SeoService } from '../../services/seo.service';
import { SiteConfig, SiteConfigService } from '../../services/site-config.service';
import { TailoredLinkService, TailoredView } from '../../services/tailored-link.service';

const PROFILE: Profile = {
    name: 'Owner',
    headline: 'Engineer',
    location: 'Somewhere',
    about: 'About',
    contact: { email: 'e@example.com', linkedin: 'l' },
    experience: [
        { title: 'Backend Engineer', company: 'Globex', startDate: '2019', endDate: '2021' },
        { title: 'Staff Engineer', company: 'Acme GmbH', startDate: '2021', endDate: 'now' },
    ],
    education: [],
    skills: ['Python', 'Angular'],
    certifications: [],
    languages: [],
    recommendations: [],
};

const SITE: SiteConfig = {
    siteName: 'Portfolio',
    siteUrl: 'https://example.com',
    ownerName: 'Mock Owner',
    ownerHeadline: 'Principal Software Engineer',
    ownerDescription: 'Desc.',
    socialLinks: [],
    analyticsId: '',
    availability: 'listening',
};

const VIEW: TailoredView = {
    slug: 'acme-staff-eng',
    company: 'Acme GmbH',
    role_title: 'Staff Engineer',
    headline_note: 'Hi Acme team — here is why I fit this role.',
    highlighted_skills: ['Angular'],
    highlighted_projects: ['Acme'],
    cv_version: 'acme-v1',
    cv_download_path: '/api/app/for/acme-staff-eng/cv',
};

describe('TailoredComponent', () => {
    let fixture: ComponentFixture<TailoredComponent>;
    let component: TailoredComponent;
    let tailoredSpy: {
        getView: ReturnType<typeof vi.fn>;
        recordVisit: ReturnType<typeof vi.fn>;
        cvDownloadUrl: ReturnType<typeof vi.fn>;
    };
    let seoSpy: Record<string, ReturnType<typeof vi.fn>>;
    let paramMap: BehaviorSubject<{ get: (key: string) => string | null }>;

    async function setup(
        options: {
            platformId?: string;
            responseInit?: ResponseInit | null;
            snapshotSlug?: string | null;
        } = {},
    ) {
        const snapshotSlug = options.snapshotSlug === undefined ? 'acme-staff-eng' : options.snapshotSlug;
        paramMap = new BehaviorSubject({
            get: (key: string) => (key === 'slug' ? 'acme-staff-eng' : null),
        });
        tailoredSpy = {
            getView: vi.fn().mockReturnValue(of(VIEW)),
            recordVisit: vi.fn().mockReturnValue(of(void 0)),
            cvDownloadUrl: vi.fn().mockReturnValue('/api/app/for/acme-staff-eng/cv'),
        };
        seoSpy = {
            updateSeo: vi.fn(),
            setNoIndex: vi.fn(),
            setNotFound: vi.fn(),
            setJsonLd: vi.fn(),
        };

        await TestBed.configureTestingModule({
            imports: [TailoredComponent, HttpClientTestingModule],
            providers: [
                provideRouter([]),
                provideSharedEnvironment({
                    production: false,
                    apiUrl: '',
                    apiPrefix: '/api/app',
                    googleAnalyticsId: '',
                }),
                { provide: LanguageService, useClass: MockLanguageService },
                { provide: ProfileService, useValue: { getProfile: () => of(PROFILE) } },
                { provide: SiteConfigService, useValue: { config$: of(SITE) } },
                { provide: TailoredLinkService, useValue: tailoredSpy },
                { provide: SeoService, useValue: seoSpy },
                { provide: PLATFORM_ID, useValue: options.platformId ?? 'browser' },
                { provide: RESPONSE_INIT, useValue: options.responseInit ?? null },
                {
                    provide: ActivatedRoute,
                    useValue: {
                        paramMap: paramMap.asObservable(),
                        snapshot: { paramMap: { get: () => snapshotSlug } },
                    },
                },
            ],
        }).compileComponents();

        fixture = TestBed.createComponent(TailoredComponent);
        component = fixture.componentInstance;
    }

    beforeEach(async () => {
        await setup();
    });

    it('renders the note, the highlights and the variant CV CTA', fakeAsync(() => {
        fixture.detectChanges();
        tick();
        fixture.detectChanges();

        const html: HTMLElement = fixture.nativeElement;
        expect(html.querySelector('[data-testid="tailored-company"]')?.textContent).toContain(
            'Acme GmbH',
        );
        expect(html.querySelector('[data-testid="tailored-role"]')?.textContent).toContain(
            'Staff Engineer',
        );
        expect(html.querySelector('[data-testid="tailored-note"]')?.textContent).toContain(
            'Hi Acme team',
        );
        expect(html.querySelector('[data-testid="tailored-skill"]')?.textContent).toContain(
            'Angular',
        );
        expect(html.querySelector('[data-testid="tailored-project"]')?.textContent).toContain(
            'Acme',
        );
        const cta = html.querySelector('[data-testid="tailored-cv-cta"]') as HTMLAnchorElement;
        expect(cta.getAttribute('href')).toBe('/api/app/for/acme-staff-eng/cv');
        expect(cta.textContent).toContain('acme-v1');
        expect(html.querySelector('[data-testid="tailored-not-found"]')).toBeNull();
    }));

    it('falls back to the standard CV flow when no variant is pinned', fakeAsync(() => {
        tailoredSpy.getView.mockReturnValue(
            of({ ...VIEW, cv_version: null, cv_download_path: null }),
        );
        tailoredSpy.cvDownloadUrl.mockReturnValue(null);

        fixture.detectChanges();
        tick();
        fixture.detectChanges();

        const cta = fixture.nativeElement.querySelector('[data-testid="tailored-cv-cta"]');
        expect(cta.getAttribute('href')).toBe('/cv');
        expect(cta.textContent).toContain('request the CV');
    }));

    it('re-orders the profile for this application without hiding anything', fakeAsync(() => {
        let vm: any;
        fixture.detectChanges();
        component.vm$!.subscribe((v) => (vm = v));
        tick();

        expect(vm.profile.skills).toEqual(['Angular', 'Python']);
        expect(vm.profile.experience.map((e: any) => e.company)).toEqual(['Acme GmbH', 'Globex']);
    }));

    it('marks the page noindex and canonical on the tailored URL', fakeAsync(() => {
        fixture.detectChanges();
        tick();

        expect(seoSpy['updateSeo']).toHaveBeenCalledWith({
            title: 'For Acme GmbH · Staff Engineer',
            description: 'Hi Acme team — here is why I fit this role.',
            url: '/for/acme-staff-eng',
        });
        expect(seoSpy['setNoIndex']).toHaveBeenCalled();
    }));

    it('describes the page generically when the owner wrote no note', fakeAsync(() => {
        tailoredSpy.getView.mockReturnValue(of({ ...VIEW, headline_note: null }));
        fixture.detectChanges();
        tick();

        expect(seoSpy['updateSeo']).toHaveBeenCalledWith(
            expect.objectContaining({ description: 'A portfolio view prepared for Acme GmbH.' }),
        );
    }));

    it('renders the not-found panel for an unknown / disabled / expired slug', fakeAsync(() => {
        tailoredSpy.getView.mockReturnValue(
            throwError(() => ({ status: 404, message: 'Not Found' })),
        );

        fixture.detectChanges();
        tick();
        fixture.detectChanges();

        expect(fixture.nativeElement.querySelector('[data-testid="tailored-not-found"]')).toBeTruthy();
        expect(fixture.nativeElement.querySelector('[data-testid="tailored-banner"]')).toBeNull();
        expect(seoSpy['setNotFound']).toHaveBeenCalled();
    }));

    it('counts the visit in the browser, once', fakeAsync(() => {
        fixture.detectChanges();
        tick();
        expect(tailoredSpy.recordVisit).toHaveBeenCalledTimes(1);
        expect(tailoredSpy.recordVisit).toHaveBeenCalledWith('acme-staff-eng');
    }));

    it('never lets a failed visit-count break the page', fakeAsync(() => {
        tailoredSpy.recordVisit.mockReturnValue(throwError(() => new Error('offline')));

        fixture.detectChanges();
        tick();
        fixture.detectChanges();

        expect(fixture.nativeElement.querySelector('[data-testid="tailored-banner"]')).toBeTruthy();
    }));

    // These re-configure the TestBed, so they are plain async tests: a
    // `fakeAsync(async () => …)` body never enters the fake-async zone.
    describe('on the server', () => {
        it('does NOT count the visit — SSR would double every real one', async () => {
            TestBed.resetTestingModule();
            await setup({ platformId: 'server' });

            fixture.detectChanges();
            await fixture.whenStable();

            expect(tailoredSpy.recordVisit).not.toHaveBeenCalled();
        });

        it('turns a soft 404 into a real HTTP 404', async () => {
            TestBed.resetTestingModule();
            const responseInit: ResponseInit = { status: 200 };
            await setup({ platformId: 'server', responseInit });
            tailoredSpy.getView.mockReturnValue(throwError(() => ({ status: 404 })));

            fixture.detectChanges();
            await fixture.whenStable();

            expect(responseInit.status).toBe(404);
        });

        it('does not blow up when the engine supplies no ResponseInit', async () => {
            TestBed.resetTestingModule();
            await setup({ platformId: 'server', responseInit: null });
            tailoredSpy.getView.mockReturnValue(throwError(() => ({ status: 404 })));

            fixture.detectChanges();
            await fixture.whenStable();

            expect(seoSpy['setNotFound']).toHaveBeenCalled();
        });
    });

    it('treats a route without a slug as not found and never calls the API', async () => {
        TestBed.resetTestingModule();
        await setup({ snapshotSlug: null });
        paramMap.next({ get: () => null });

        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();

        expect(component.slug).toBe('');
        expect(tailoredSpy.getView).not.toHaveBeenCalled();
        expect(tailoredSpy.recordVisit).not.toHaveBeenCalled();
        expect(fixture.nativeElement.querySelector('[data-testid="tailored-not-found"]')).toBeTruthy();
    });
});
