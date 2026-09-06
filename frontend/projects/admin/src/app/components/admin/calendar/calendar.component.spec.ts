import { ComponentFixture, TestBed } from '@angular/core/testing';
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
        outcome: 'scheduled',
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
        // 23:30 UTC is the NEXT day anywhere east of UTC. Slicing the string
        // would file this under the wrong heading for exactly the users in
        // those zones, so the key must come from a real Date.
        const late = row({ id: 'late', scheduled_at: '2026-09-10T23:30:00Z' });
        const key = (component as unknown as { localDateKey(iso: string): string }).localDateKey(
            late.scheduled_at,
        );
        const local = new Date(late.scheduled_at);
        const expected = `${local.getFullYear()}-${`${local.getMonth() + 1}`.padStart(2, '0')}-${`${local.getDate()}`.padStart(2, '0')}`;
        expect(key).toBe(expected);
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

    it('surfaces an outcome failure without losing the row', () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        const r = row();
        flushUpcoming([r]);

        component.setOutcome(component.days[0].interviews[0], 'passed');
        httpMock
            .expectOne(`${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1`)
            .flush({ detail: 'no' }, { status: 500, statusText: 'Server Error' });

        expect(component.error).toBe('Failed to update the outcome');
        expect(component.days[0].interviews[0].outcome).toBe('scheduled');
    });

    it('offers a per-round .ics download link', () => {
        flushUpcoming([row()]);
        const link = (fixture.nativeElement as HTMLElement).querySelector('a.ics');
        expect(link?.getAttribute('href')).toContain('/admin/interviews/i1.ics');
    });
});
