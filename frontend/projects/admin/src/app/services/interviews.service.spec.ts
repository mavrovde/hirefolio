import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
    HttpTestingController,
    provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { InterviewsService } from './interviews.service';
import { environment } from '../../environments/environment';

describe('InterviewsService', () => {
    let service: InterviewsService;
    let httpMock: HttpTestingController;
    const base = `${environment.apiUrl}${environment.apiPrefix}/admin`;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [provideHttpClient(), provideHttpClientTesting(), InterviewsService],
        });
        service = TestBed.inject(InterviewsService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => httpMock.verify());

    it('requests the upcoming window with a default and an explicit day count', () => {
        service.upcoming().subscribe();
        const req = httpMock.expectOne((r) => r.url === `${base}/interviews/upcoming`);
        expect(req.request.params.get('days')).toBe('14');
        req.flush([]);

        service.upcoming(30).subscribe();
        const req2 = httpMock.expectOne((r) => r.url === `${base}/interviews/upcoming`);
        expect(req2.request.params.get('days')).toBe('30');
        req2.flush([]);
    });

    it('lists, schedules, patches and removes a round', () => {
        service.listFor('o1').subscribe();
        httpMock.expectOne(`${base}/opportunities/o1/interviews`).flush([]);

        service.schedule('o1', { scheduled_at: '2026-09-10T10:00:00Z' }).subscribe();
        const post = httpMock.expectOne(`${base}/opportunities/o1/interviews`);
        expect(post.request.method).toBe('POST');
        expect(post.request.body.scheduled_at).toBe('2026-09-10T10:00:00Z');
        post.flush({ id: 'i1' });

        service.update('i1', { outcome: 'passed' }).subscribe();
        const patch = httpMock.expectOne(`${base}/interviews/i1`);
        expect(patch.request.method).toBe('PATCH');
        expect(patch.request.body.outcome).toBe('passed');
        patch.flush({ id: 'i1' });

        service.remove('i1').subscribe();
        const del = httpMock.expectOne(`${base}/interviews/i1`);
        expect(del.request.method).toBe('DELETE');
        del.flush(null);
    });

    it('builds the .ics URL without fetching it', () => {
        // The browser downloads this directly; the service must NOT issue a
        // request for it, which httpMock.verify() in afterEach enforces.
        expect(service.icsUrl('i1')).toBe(`${base}/interviews/i1.ics`);
    });

    it('surfaces a server error to the caller instead of swallowing it', () => {
        let status = 0;
        service.upcoming().subscribe({ error: (e) => (status = e.status) });
        httpMock
            .expectOne((r) => r.url === `${base}/interviews/upcoming`)
            .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
        expect(status).toBe(500);
    });
});
