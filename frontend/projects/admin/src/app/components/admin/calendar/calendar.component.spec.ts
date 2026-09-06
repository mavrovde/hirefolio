import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PLATFORM_ID } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import {
    HttpTestingController,
    provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { CalendarComponent } from './calendar.component';
import { InterviewsService, UpcomingInterview } from '../../../services/interviews.service';
import { environment } from '../../../../environments/environment';

const UPCOMING = `${environment.apiUrl}${environment.apiPrefix}/admin/interviews/upcoming`;

function row(overrides: Partial<UpcomingInterview> = {}): UpcomingInterview {
    return {
        id: 'i1',
        opportunity_id: 'o1',
        scheduled_at: '2026-09-10T09:00:00Z',
        duration_minutes: 60,
        kind: 'video',
        location_or_link: null,
        interviewer: null,
        notes: null,
        outcome: 'pending',
        company: 'Acme GmbH',
        role_title: 'Staff Engineer',
        stage: 'interviewing',
        ...overrides,
    };
}

describe('CalendarComponent', () => {
    let fixture: ComponentFixture<CalendarComponent>;
    let component: CalendarComponent;
    let httpMock: HttpTestingController;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [CalendarComponent],
            providers: [provideHttpClient(), provideHttpClientTesting(), InterviewsService],
        }).compileComponents();

        fixture = TestBed.createComponent(CalendarComponent);
        component = fixture.componentInstance;
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => httpMock.verify());

    function flushUpcoming(rows: UpcomingInterview[]) {
        fixture.detectChanges();
        httpMock.expectOne((r) => r.url === UPCOMING).flush(rows);
        fixture.detectChanges();
    }

    it('loads the default window and groups rounds by local day', () => {
        // Pin the zone so the expected day-split is the same on every runner
        // (under UTC+14 these three rows straddle local midnight differently).
        component.timeZone = 'UTC';
        fixture.detectChanges();
        const req = httpMock.expectOne((r) => r.url === UPCOMING);
        expect(req.request.params.get('days')).toBe('14');
        req.flush([
            row({ id: 'a', scheduled_at: '2026-09-10T09:00:00Z' }),
            row({ id: 'b', scheduled_at: '2026-09-10T14:00:00Z' }),
            row({ id: 'c', scheduled_at: '2026-09-11T09:00:00Z' }),
        ]);
        fixture.detectChanges();

        expect(component.days.length).toBe(2);
        expect(component.days[0].interviews.map((i) => i.id)).toEqual(['a', 'b']);
        expect(component.total).toBe(3);
    });

    it('groups by LOCAL date, not by the UTC prefix of the ISO string', () => {
        // Explicit IANA zones, NOT the runner's TZ: the first version of this
        // test recomputed its expectation with the implementation's own
        // algorithm, so a UTC-slice implementation passed it on UTC runners —
        // a tautology (#292 review round 1). With pinned zones the two
        // implementations give DIFFERENT answers on every runner:
        // 23:30 UTC is already Sep 11 in Kiritimati (UTC+14) and still
        // Sep 10 in Anchorage (UTC-8). A slice(0, 10) returns 2026-09-10
        // for both, so it fails the first assertion everywhere.
        component.timeZone = 'Pacific/Kiritimati';
        expect(component.localDateKey('2026-09-10T23:30:00Z')).toBe('2026-09-11');
        component.timeZone = 'America/Anchorage';
        expect(component.localDateKey('2026-09-10T23:30:00Z')).toBe('2026-09-10');
        component.timeZone = 'UTC';
        expect(component.localDateKey('2026-09-10T23:30:00Z')).toBe('2026-09-10');
    });

    it('reloads with a different window when one is picked', () => {
        flushUpcoming([]);
        component.changeWindow(30);
        const req = httpMock.expectOne((r) => r.url === UPCOMING);
        expect(req.request.params.get('days')).toBe('30');
        req.flush([]);
        expect(component.windowDays).toBe(30);
    });

    it('shows an error and clears the rows when the window fails to load', () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        fixture.detectChanges();
        httpMock
            .expectOne((r) => r.url === UPCOMING)
            .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
        fixture.detectChanges();

        expect(component.error).toBe('Failed to load the calendar');
        expect(component.days).toEqual([]);
        expect(component.loading).toBe(false);
    });

    it('computes the end time and flags a round that is in progress', () => {
        const r = row({ scheduled_at: '2026-09-10T09:00:00Z', duration_minutes: 45 });
        expect(component.endsAt(r).toISOString()).toBe('2026-09-10T09:45:00.000Z');

        expect(component.isInProgress(r, new Date('2026-09-10T09:30:00Z'))).toBe(true);
        // Boundaries: the start instant counts, the end instant does not.
        expect(component.isInProgress(r, new Date('2026-09-10T09:00:00Z'))).toBe(true);
        expect(component.isInProgress(r, new Date('2026-09-10T09:45:00Z'))).toBe(false);
        expect(component.isInProgress(r, new Date('2026-09-10T08:59:59Z'))).toBe(false);
    });

    it('records an outcome in place without reloading the window', () => {
        const r = row();
        flushUpcoming([r]);

        component.setOutcome(component.days[0].interviews[0], 'passed');
        const patch = httpMock.expectOne(
            `${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1`,
        );
        expect(patch.request.body.outcome).toBe('passed');
        patch.flush({ ...r, outcome: 'passed' });

        expect(component.days[0].interviews[0].outcome).toBe('passed');
        // NO second /upcoming request: a reload here would drop the operator's
        // scroll position on every recorded outcome. httpMock.verify() in
        // afterEach turns any stray reload into a failure.
    });

    it('downloads the .ics with auth and hands the browser a blob', () => {
        const r = row();
        flushUpcoming([r]);

        const created: string[] = [];
        vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
            created.push('blob:mock');
            return 'blob:mock';
        });
        vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
        const clicks: string[] = [];
        vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
            this: HTMLAnchorElement,
        ) {
            clicks.push(this.download);
        });

        component.downloadIcs(component.days[0].interviews[0]);
        const req = httpMock.expectOne(
            `${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1.ics`,
        );
        expect(req.request.responseType).toBe('blob');
        req.flush(new Blob(['BEGIN:VCALENDAR'], { type: 'text/calendar' }));

        expect(created).toEqual(['blob:mock']);
        expect(clicks).toEqual(['interview-i1.ics']);
        expect(component.downloadingId).toBeNull();
    });

    it('surfaces a failed .ics download and clears the busy state', () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        const r = row();
        flushUpcoming([r]);

        component.downloadIcs(component.days[0].interviews[0]);
        httpMock
            .expectOne(`${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1.ics`)
            .flush(new Blob(['no']), { status: 401, statusText: 'Unauthorized' });

        expect(component.error).toBe('Failed to download the calendar file');
        expect(component.downloadingId).toBeNull();
    });

    it('reloads after a cancellation, because the backend drops it from the window', () => {
        const r = row();
        flushUpcoming([r]);

        component.setOutcome(component.days[0].interviews[0], 'cancelled');
        httpMock
            .expectOne(`${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1`)
            .flush({ ...r, outcome: 'cancelled' });

        // Leaving the row would show a cancelled round until the next refresh.
        httpMock.expectOne((req) => req.url === UPCOMING).flush([]);
        expect(component.total).toBe(0);
    });

    it('surfaces an outcome failure and snaps the select back to the model', () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        const r = row();
        flushUpcoming([r]);

        component.setOutcome(component.days[0].interviews[0], 'passed');
        httpMock
            .expectOne(`${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1`)
            .flush({ detail: 'no' }, { status: 500, statusText: 'Server Error' });

        expect(component.error).toBe('Failed to update the outcome');
        expect(component.days[0].interviews[0].outcome).toBe('pending');
        // Fresh row identities force the ngFor to rebuild, so the <select>
        // re-reads the (unchanged) model value instead of keeping the user's
        // rejected choice on screen.
        expect(component.days[0].interviews[0]).not.toBe(r);
    });

    it('is inert on a non-browser platform (rule 5 DOM guard)', async () => {
        // Admin is a CSR SPA today, but the DOM guard is the house rule
        // (lessons §1 territory) — pin the guarded branch so it stays.
        TestBed.resetTestingModule();
        await TestBed.configureTestingModule({
            imports: [CalendarComponent],
            providers: [
                provideHttpClient(),
                provideHttpClientTesting(),
                InterviewsService,
                { provide: PLATFORM_ID, useValue: 'server' },
            ],
        }).compileComponents();
        const f = TestBed.createComponent(CalendarComponent);
        const mock = TestBed.inject(HttpTestingController);
        f.componentInstance.downloadIcs(row());
        // No request, no busy state: the guard returned before the fetch.
        mock.expectNone((r) => r.url.includes('.ics'));
        expect(f.componentInstance.downloadingId).toBeNull();
        mock.verify();
    });

    it('renders the .ics control as a BUTTON, never a bare link', () => {
        // A plain <a href> to the admin-gated endpoint 401s (no Bearer token),
        // which is precisely the round-1 blocker. Pin the control type.
        flushUpcoming([row()]);
        const host = fixture.nativeElement as HTMLElement;
        expect(host.querySelector('button.ics')).not.toBeNull();
        expect(host.querySelector('a.ics')).toBeNull();
    });
});
