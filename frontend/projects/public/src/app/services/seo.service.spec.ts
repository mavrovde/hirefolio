import { TestBed } from '@angular/core/testing';
import { PLATFORM_ID } from '@angular/core';
import { Title, Meta } from '@angular/platform-browser';
import { of, Subject } from 'rxjs';
import { SeoService } from './seo.service';
import { SiteConfigService } from './site-config.service';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Test identity mirrors the historical branding so the assertions stay
// meaningful; production values now come from the runtime config (#65).
const MOCK_SITE_CONFIG_PROVIDER = {
    provide: SiteConfigService,
    useValue: {
        config$: of({
            siteName: 'mavrov.de',
            siteUrl: 'https://mavrov.de',
            ownerName: 'Mock Owner',
            ownerHeadline: 'Principal Software Engineer',
            ownerDescription:
                'Professional portfolio of Mock Owner, a Principal Software Engineer specialized in Cloud, AI, and Full-Stack Development.',
           
            socialLinks: [],
            analyticsId: '',
        }),
    },
};

describe('SeoService', () => {
    let service: SeoService;
    let titleService: Title;
    let metaService: Meta;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [SeoService, Title, Meta, MOCK_SITE_CONFIG_PROVIDER]
        });
        service = TestBed.inject(SeoService);
        titleService = TestBed.inject(Title);
        metaService = TestBed.inject(Meta);
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should update SEO with full config', () => {
        const spy = vi.spyOn(metaService, 'updateTag');
        const titleSpy = vi.spyOn(titleService, 'setTitle');

        service.updateSeo({
            title: 'Page Title',
            description: 'Page Desc',
            keywords: 'k1, k2',
            image: '/img.jpg',
            url: '/page',
            type: 'article'
        });

        expect(titleSpy).toHaveBeenCalledWith('Page Title | Mock Owner');
        expect(spy).toHaveBeenCalledWith({ name: 'description', content: 'Page Desc' });
        expect(spy).toHaveBeenCalledWith({ name: 'keywords', content: 'k1, k2' });
        expect(spy).toHaveBeenCalledWith({ property: 'og:type', content: 'article' });
        expect(spy).toHaveBeenCalledWith({ name: 'twitter:card', content: 'summary_large_image' });
    });

    it('should use defaults when config is empty', () => {
        const titleSpy = vi.spyOn(titleService, 'setTitle');
        service.updateSeo({});

        expect(titleSpy).toHaveBeenCalledWith('Mock Owner | Principal Software Engineer');
    });

    it('should set JSON-LD schema', () => {
        const schema = { '@type': 'Person', name: 'Test' };
        service.setJsonLd(schema);

        service.jsonLdSchema$.subscribe(val => {
            expect(val).toEqual(schema);
        });
    });

    it('should not update canonical url in server environment', () => {
        document.head.innerHTML = ''; // reset DOM
        TestBed.resetTestingModule();
        TestBed.configureTestingModule({
            providers: [
                SeoService, Title, Meta, MOCK_SITE_CONFIG_PROVIDER,
                { provide: PLATFORM_ID, useValue: 'server' }
            ]
        });
        const serverService = TestBed.inject(SeoService);
        serverService.updateSeo({ url: '/server-test' });
        
        expect(document.querySelector("link[rel='canonical']")).toBeNull();
    });
});

describe('SeoService config re-apply (#255 review pins)', () => {
    let subject: Subject<any>;
    let titleService: Title;
    let service: SeoService;

    const CFG = {
        siteName: 'mavrov.de', siteUrl: 'https://real.example',
        ownerName: 'Real Owner', ownerHeadline: 'Real Headline',
        ownerDescription: 'Real description.', socialLinks: [], analyticsId: '',
    };

    beforeEach(() => {
        subject = new Subject<any>();
        TestBed.resetTestingModule();
        TestBed.configureTestingModule({
            providers: [
                SeoService, Title, Meta,
                { provide: SiteConfigService, useValue: { config$: subject.asObservable() } },
            ],
        });
        service = TestBed.inject(SeoService);
        titleService = TestBed.inject(Title);
    });

    it('re-applies the last SEO data when the config arrives (placeholder never sticks)', () => {
        service.updateSeo({ title: 'Blog' });
        expect(titleService.getTitle()).toBe('Blog | Portfolio Owner'); // neutral default first

        subject.next(CFG);
        // Mutation pin: deleting the constructor re-apply leaves the
        // placeholder in the SSR head — this asserts the re-brand happened.
        expect(titleService.getTitle()).toBe('Blog | Real Owner');
    });

    it('a not-found page re-applies its NOT-FOUND title, never the page branding (#109)', () => {
        service.updateSeo({ title: 'Some Post' });
        service.setNotFound();
        expect(titleService.getTitle()).toBe('Post not found | Portfolio Owner');

        subject.next(CFG);
        expect(titleService.getTitle()).toBe('Post not found | Real Owner');
    });

    it('updateSeo after a not-found clears the flag (normal navigation resumes)', () => {
        service.setNotFound();
        service.updateSeo({ title: 'Home' });
        subject.next(CFG);
        expect(titleService.getTitle()).toBe('Home | Real Owner');
    });
});
