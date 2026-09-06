import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
    HttpTestingController,
    provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { OpportunitiesService } from './opportunities.service';
import { environment } from '../../environments/environment';

describe('OpportunitiesService', () => {
    let service: OpportunitiesService;
    let httpMock: HttpTestingController;
    const base = `${environment.apiUrl}${environment.apiPrefix}/admin/opportunities`;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [provideHttpClient(), provideHttpClientTesting(), OpportunitiesService],
        });
        service = TestBed.inject(OpportunitiesService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => httpMock.verify());

    it('lists with defaults and optional stage filter', () => {
        service.list().subscribe();
        const req = httpMock.expectOne((r) => r.url === base);
        expect(req.request.params.get('page')).toBe('1');
        expect(req.request.params.has('stage')).toBe(false);
        req.flush({ items: [], total: 0, page: 1, pages: 1 });

        service.list({ stage: 'offer', page: 2, pageSize: 10 }).subscribe();
        const req2 = httpMock.expectOne((r) => r.url === base);
        expect(req2.request.params.get('stage')).toBe('offer');
        expect(req2.request.params.get('page_size')).toBe('10');
        req2.flush({ items: [], total: 0, page: 2, pages: 1 });
    });

    it('records which CV variant was sent', () => {
        service.recordCvSent('o1', 'cv9').subscribe();
        const req = httpMock.expectOne(`${base}/o1/cv-sent`);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ cv_document_id: 'cv9' });
        req.flush({ id: 'o1', sent_cv_id: 'cv9' });
    });

    it('gets, creates, moves stage, adds notes', () => {
        service.get('o1').subscribe();
        httpMock.expectOne(`${base}/o1`).flush({ id: 'o1' });

        service.create({ company: 'Acme', role_title: 'SE' }).subscribe();
        const post = httpMock.expectOne(base);
        expect(post.request.method).toBe('POST');
        post.flush({ id: 'o2' });

        service.moveStage('o1', 'offer').subscribe();
        const patch = httpMock.expectOne(`${base}/o1/stage`);
        expect(patch.request.body).toEqual({ stage: 'offer' });
        patch.flush({ id: 'o1', stage: 'offer' });

        service.addNote('o1', 'hi').subscribe();
        const note = httpMock.expectOne(`${base}/o1/notes`);
        expect(note.request.body).toEqual({ body: 'hi' });
        note.flush({ id: 'o1' });
    });

    it('promotes an interaction (with and without a role title)', () => {
        service.promote('i1', 'Staff').subscribe();
        const req = httpMock.expectOne(`${base}/promote`);
        expect(req.request.body).toEqual({ interaction_id: 'i1', role_title: 'Staff' });
        req.flush({ id: 'o3' });

        service.promote('i2').subscribe();
        const req2 = httpMock.expectOne(`${base}/promote`);
        expect(req2.request.body).toEqual({ interaction_id: 'i2', role_title: null });
        req2.flush({ id: 'o4' });
    });
});
