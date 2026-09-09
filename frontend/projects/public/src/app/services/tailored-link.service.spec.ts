import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { TailoredLinkService, TailoredView } from './tailored-link.service';

const VIEW: TailoredView = {
    slug: 'acme-staff-eng',
    company: 'Acme GmbH',
    role_title: 'Staff Engineer',
    headline_note: 'Hi Acme team',
    highlighted_skills: ['Angular'],
    highlighted_projects: ['Beaconfolio'],
    cv_version: 'acme-v1',
    cv_download_path: '/api/app/for/acme-staff-eng/cv',
};

describe('TailoredLinkService', () => {
    let service: TailoredLinkService;
    let http: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
        service = TestBed.inject(TailoredLinkService);
        http = TestBed.inject(HttpTestingController);
    });

    afterEach(() => http.verify());

    it('fetches the tailored view for a slug', () => {
        let received: TailoredView | undefined;
        service.getView('acme-staff-eng').subscribe((v) => (received = v));

        const req = http.expectOne('/api/app/for/acme-staff-eng');
        expect(req.request.method).toBe('GET');
        req.flush(VIEW);
        expect(received).toEqual(VIEW);
    });

    it('percent-encodes the slug so a crafted path cannot escape the endpoint', () => {
        service.getView('a/../b').subscribe();
        http.expectOne('/api/app/for/a%2F..%2Fb').flush(VIEW);
    });

    it('records a visit with a POST', () => {
        service.recordVisit('acme-staff-eng').subscribe();
        const req = http.expectOne('/api/app/for/acme-staff-eng/visit');
        expect(req.request.method).toBe('POST');
        req.flush(null);
    });

    it('propagates a 404 for an unknown / disabled / expired slug', () => {
        let status = 0;
        service.getView('gone').subscribe({ error: (e) => (status = e.status) });
        http.expectOne('/api/app/for/gone').flush('nope', { status: 404, statusText: 'Not Found' });
        expect(status).toBe(404);
    });

    it('builds the CV URL only when a variant is pinned', () => {
        expect(service.cvDownloadUrl(VIEW)).toBe('/api/app/for/acme-staff-eng/cv');
        expect(service.cvDownloadUrl({ ...VIEW, cv_download_path: null })).toBeNull();
    });
});
