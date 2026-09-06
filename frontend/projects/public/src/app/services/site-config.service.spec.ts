import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
    HttpTestingController,
    provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { SiteConfigService, DEFAULT_SITE_CONFIG, SiteConfig } from './site-config.service';
import { environment } from '../../environments/environment';

const DTO = {
    site_name: 'mavrov.de',
    site_url: 'https://mavrov.de',
    owner_name: 'Mock Owner',
    owner_headline: 'Principal Software Engineer',
    owner_description: 'Desc.',
    social_links: ['https://linkedin.example/x'],
    analytics_id: 'G-TEST0001',
};

describe('SiteConfigService', () => {
    let service: SiteConfigService;
    let httpMock: HttpTestingController;
    const url = `${environment.apiUrl}${environment.apiPrefix}/config/site`;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [provideHttpClient(), provideHttpClientTesting(), SiteConfigService],
        });
        service = TestBed.inject(SiteConfigService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('maps the snake_case wire shape to camelCase', () => {
        let received: SiteConfig | undefined;
        service.config$.subscribe((c) => (received = c));
        httpMock.expectOne(url).flush(DTO);

        expect(received).toEqual({
            siteName: 'mavrov.de',
            siteUrl: 'https://mavrov.de',
            ownerName: 'Mock Owner',
            ownerHeadline: 'Principal Software Engineer',
            ownerDescription: 'Desc.',
            
            socialLinks: ['https://linkedin.example/x'],
            analyticsId: 'G-TEST0001',
        });
    });

    it('falls back to the neutral default when the backend is unreachable', () => {
        let received: SiteConfig | undefined;
        service.config$.subscribe((c) => (received = c));
        httpMock.expectOne(url).flush('boom', { status: 500, statusText: 'Server Error' });

        expect(received).toEqual(DEFAULT_SITE_CONFIG);
        expect(received!.analyticsId).toBe('');
    });

    it('fetches once and replays to late subscribers (shareReplay)', () => {
        let first: SiteConfig | undefined;
        service.config$.subscribe((c) => (first = c));
        httpMock.expectOne(url).flush(DTO);

        let second: SiteConfig | undefined;
        service.config$.subscribe((c) => (second = c));
        // No second request may be issued:
        httpMock.expectNone(url);
        expect(second).toEqual(first);
    });
});
