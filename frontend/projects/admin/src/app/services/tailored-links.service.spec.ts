import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
    TailoredLink,
    TailoredLinksService,
    parseHighlights,
} from './tailored-links.service';

const LINK: TailoredLink = {
    id: 'l1',
    opportunity_id: 'o1',
    slug: 'acme-staff-eng',
    path: '/for/acme-staff-eng',
    url: 'https://example.com/for/acme-staff-eng',
    cv_document_id: null,
    cv_version: null,
    cv_filename: null,
    headline_note: null,
    highlighted_skills: [],
    highlighted_projects: [],
    enabled: true,
    expires_at: null,
    visit_count: 0,
    cv_download_count: 0,
    last_visited_at: null,
    created_at: '2026-09-08T10:00:00Z',
    updated_at: '2026-09-08T10:00:00Z',
};

describe('TailoredLinksService', () => {
    let service: TailoredLinksService;
    let http: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
        service = TestBed.inject(TailoredLinksService);
        http = TestBed.inject(HttpTestingController);
    });

    afterEach(() => http.verify());

    it('lists the links of one opportunity', () => {
        let received: TailoredLink[] | undefined;
        service.listFor('o1').subscribe((rows) => (received = rows));

        const req = http.expectOne(
            '/api/app/admin/tailored-links?opportunity_id=o1'
        );
        expect(req.request.method).toBe('GET');
        req.flush([LINK]);
        expect(received).toEqual([LINK]);
    });

    it('mints a link', () => {
        service.create({ opportunity_id: 'o1', slug: 'acme-staff-eng' }).subscribe();
        const req = http.expectOne('/api/app/admin/tailored-links');
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ opportunity_id: 'o1', slug: 'acme-staff-eng' });
        req.flush(LINK);
    });

    it('patches and deletes a link', () => {
        service.update('l1', { enabled: false }).subscribe();
        const patch = http.expectOne('/api/app/admin/tailored-links/l1');
        expect(patch.request.method).toBe('PATCH');
        patch.flush({ ...LINK, enabled: false });

        service.remove('l1').subscribe();
        const del = http.expectOne('/api/app/admin/tailored-links/l1');
        expect(del.request.method).toBe('DELETE');
        del.flush(null);
    });
});

describe('parseHighlights', () => {
    it('splits, trims and drops the blanks', () => {
        expect(parseHighlights(' Angular , Python ,, ')).toEqual(['Angular', 'Python']);
    });

    it('yields an empty array for an empty control', () => {
        expect(parseHighlights('')).toEqual([]);
        expect(parseHighlights('   ')).toEqual([]);
    });
});
