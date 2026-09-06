/**
 * Zoneless repaint pin (#247 phase 2). The other spec bundles zone.js, which
 * fires change detection for free and therefore CANNOT see a missing repaint —
 * that is precisely how five frozen-UI bugs reached the admin app (#276) and a
 * sixth survived the lint (#290). This TestBed opts into
 * `provideZonelessChangeDetection()` so a missing `detectChanges()` shows up as
 * a stale DOM instead of passing quietly.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
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

const ROW: UpcomingInterview = {
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
};

describe('CalendarComponent (zoneless repaint)', () => {
    let fixture: ComponentFixture<CalendarComponent>;
    let httpMock: HttpTestingController;
    let host: HTMLElement;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [CalendarComponent],
            providers: [
                provideZonelessChangeDetection(),
                provideHttpClient(),
                provideHttpClientTesting(),
                InterviewsService,
            ],
        }).compileComponents();

        fixture = TestBed.createComponent(CalendarComponent);
        httpMock = TestBed.inject(HttpTestingController);
        host = fixture.nativeElement as HTMLElement;
    });

    afterEach(() => httpMock.verify());

    it('paints the loaded rounds without a manual detectChanges()', () => {
        fixture.detectChanges(); // initial render + ngOnInit
        httpMock.expectOne((r) => r.url === UPCOMING).flush([ROW]);

        // Deliberately NO detectChanges() here: the subscribe callback must
        // repaint on its own, or the operator stares at "Loading…" forever.
        expect(host.textContent).toContain('Acme GmbH');
        expect(host.textContent).toContain('Staff Engineer');
        expect(host.textContent).not.toContain('Loading the calendar');
    });

    it('paints the error state without a manual detectChanges()', () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        fixture.detectChanges();
        httpMock
            .expectOne((r) => r.url === UPCOMING)
            .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });

        expect(host.textContent).toContain('Failed to load the calendar');
    });

    it('paints a recorded outcome without a manual detectChanges()', async () => {
        fixture.detectChanges();
        httpMock.expectOne((r) => r.url === UPCOMING).flush([ROW]);

        const select = host.querySelector('select.outcome') as HTMLSelectElement;
        expect(select.value).toBe('pending');

        fixture.componentInstance.setOutcome(
            fixture.componentInstance.days[0].interviews[0],
            'passed',
        );
        httpMock
            .expectOne(`${environment.apiUrl}${environment.apiPrefix}/admin/interviews/i1`)
            .flush({ ...ROW, outcome: 'passed' });

        // `[ngModel]` writes the DOM value on a microtask, so wait for that —
        // NOT with detectChanges(), which would defeat the point of this file.
        await fixture.whenStable();
        expect((host.querySelector('select.outcome') as HTMLSelectElement).value).toBe('passed');
    });
});
