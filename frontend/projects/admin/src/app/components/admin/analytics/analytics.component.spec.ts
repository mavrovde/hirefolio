import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { AnalyticsComponent } from './analytics.component';
import {
  EngagementService,
  EngagementSummary,
} from '../../../services/engagement.service';

const KINDS = ['cv_request', 'cv_download', 'contact_submitted'];

function summary(overrides: Partial<EngagementSummary> = {}): EngagementSummary {
  return {
    kinds: KINDS,
    totals: { cv_request: 4, cv_download: 9, contact_submitted: 2 },
    weeks: [
      {
        week_start: '2026-08-24',
        counts: { cv_request: 1, cv_download: 0, contact_submitted: 0 },
      },
      {
        week_start: '2026-08-31',
        counts: { cv_request: 3, cv_download: 9, contact_submitted: 2 },
      },
    ],
    recent: [
      {
        id: 'e1',
        kind: 'cv_download',
        subject_id: 'c1',
        label: 'Rita Recruiter (Agency GmbH)',
        payload: null,
        created_at: '2026-09-05T10:00:00+00:00',
      },
      {
        id: 'e2',
        kind: 'contact_submitted',
        subject_id: null,
        label: null,
        payload: null,
        created_at: '2026-09-04T10:00:00+00:00',
      },
    ],
    ...overrides,
  };
}

describe('AnalyticsComponent', () => {
  let fixture: ComponentFixture<AnalyticsComponent>;
  let component: AnalyticsComponent;
  let engagement: { summary: Mock; purge: Mock; sendDigest: Mock };

  const el = () => fixture.nativeElement as HTMLElement;
  const testId = (id: string) => el().querySelector(`[data-testid="${id}"]`);

  beforeEach(async () => {
    engagement = {
      summary: vi.fn().mockReturnValue(of(summary())),
      purge: vi.fn().mockReturnValue(of({ deleted: 2, retention_days: 365 })),
      sendDigest: vi.fn().mockReturnValue(of({ sent: true })),
    };
    await TestBed.configureTestingModule({
      imports: [AnalyticsComponent],
      providers: [{ provide: EngagementService, useValue: engagement }],
    }).compileComponents();
    fixture = TestBed.createComponent(AnalyticsComponent);
    component = fixture.componentInstance;
  });

  it('renders totals, a continuous weekly trend and the activity feed', () => {
    fixture.detectChanges();

    expect(engagement.summary).toHaveBeenCalledWith(8);
    const totals = testId('analytics-totals') as HTMLElement;
    expect(
      totals.querySelector('[data-kind="cv_download"] .total-value')?.textContent,
    ).toBe('9');

    // Every week renders a bar per kind — a quiet week is a zero bar, not a gap.
    const weeks = el().querySelectorAll('.chart-week');
    expect(weeks.length).toBe(2);
    const bars = weeks[1].querySelectorAll('.bar');
    expect(bars.length).toBe(KINDS.length);
    expect(bars[1].getAttribute('data-count')).toBe('9');
    // Scaled against the busiest bar in the window.
    expect((bars[1] as HTMLElement).style.height).toBe('100%');
    expect(weeks[1].querySelector('.bars')?.getAttribute('data-total')).toBe('14');

    const feed = testId('analytics-feed') as HTMLElement;
    const rows = feed.querySelectorAll('.feed-item');
    expect(rows.length).toBe(2);
    expect(rows[0].querySelector('.feed-kind')?.textContent).toContain('CV downloads');
    expect(rows[0].querySelector('.feed-who')?.textContent).toContain(
      'Rita Recruiter (Agency GmbH)',
    );
    // A feed row whose source record is gone still counts; it just has no name.
    expect(rows[1].querySelector('.feed-who')?.textContent?.trim()).toBe('—');
  });

  it('shows the loading state until the summary arrives', () => {
    const pending = new Subject<EngagementSummary>();
    engagement.summary.mockReturnValue(pending);
    fixture.detectChanges();

    expect(testId('analytics-loading')).not.toBeNull();
    pending.next(summary());
    fixture.detectChanges();
    expect(testId('analytics-loading')).toBeNull();
    expect(testId('analytics-totals')).not.toBeNull();
  });

  it('says the feature is disabled when the endpoint 404s', () => {
    engagement.summary.mockReturnValue(throwError(() => ({ status: 404 })));
    fixture.detectChanges();

    expect(testId('analytics-disabled')?.textContent).toContain(
      'ENGAGEMENT_ANALYTICS_ENABLED',
    );
    expect(testId('analytics-error')).toBeNull();
  });

  it('shows an error with a retry on any other failure', () => {
    engagement.summary.mockReturnValue(throwError(() => ({ status: 500 })));
    fixture.detectChanges();

    expect(testId('analytics-error')).not.toBeNull();
    engagement.summary.mockReturnValue(of(summary()));
    (el().querySelector('.error + button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(testId('analytics-totals')).not.toBeNull();
  });

  it('reloads the trend for a different window', () => {
    fixture.detectChanges();
    const buttons = Array.from(el().querySelectorAll('.window-btn'));
    (buttons[2] as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(engagement.summary).toHaveBeenLastCalledWith(12);
    expect(buttons[2].classList.contains('active')).toBe(true);
    expect(buttons[0].classList.contains('active')).toBe(false);
  });

  it('renders the empty feed message when nothing has happened yet', () => {
    engagement.summary.mockReturnValue(of(summary({ recent: [] })));
    fixture.detectChanges();
    expect(testId('analytics-feed')?.textContent).toContain('No engagement yet');
  });

  it('purges old events, reports the count and refreshes', () => {
    fixture.detectChanges();
    (testId('analytics-purge') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(testId('analytics-action')?.textContent).toContain(
      'Purged 2 event(s) older than 365 day(s)',
    );
    // The chart must not keep showing rows the purge just deleted.
    expect(engagement.summary).toHaveBeenCalledTimes(2);
  });

  it('reports a failed purge', () => {
    fixture.detectChanges();
    engagement.purge.mockReturnValue(throwError(() => new Error('boom')));
    (testId('analytics-purge') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(testId('analytics-action')?.textContent).toContain('Failed to purge');
  });

  it('reports a sent digest, a skipped one and a failure', () => {
    fixture.detectChanges();
    const button = testId('analytics-digest') as HTMLButtonElement;

    button.click();
    fixture.detectChanges();
    expect(testId('analytics-action')?.textContent).toContain('Weekly digest sent');

    engagement.sendDigest.mockReturnValue(of({ sent: false }));
    button.click();
    fixture.detectChanges();
    expect(testId('analytics-action')?.textContent).toContain('SMTP is not configured');

    engagement.sendDigest.mockReturnValue(throwError(() => new Error('boom')));
    button.click();
    fixture.detectChanges();
    expect(testId('analytics-action')?.textContent).toContain('Failed to send');
  });

  it('disables the housekeeping buttons while a request is in flight', () => {
    fixture.detectChanges();
    const pending = new Subject<{ sent: boolean }>();
    engagement.sendDigest.mockReturnValue(pending);

    (testId('analytics-digest') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect((testId('analytics-purge') as HTMLButtonElement).disabled).toBe(true);

    pending.next({ sent: true });
    fixture.detectChanges();
    expect((testId('analytics-purge') as HTMLButtonElement).disabled).toBe(false);
  });

  it('labels known kinds and falls back to a readable name for new ones', () => {
    expect(component.label('cv_request')).toBe('CV requests');
    // A kind this build does not know about must still read as words.
    expect(component.label('link_visit')).toBe('link visit');
  });

  it('scales bars against the peak and keeps a non-zero week visible', () => {
    expect(component.barHeight(0, 10)).toBe(0);
    expect(component.barHeight(10, 10)).toBe(100);
    // 1/100 rounds to 1% — a bar too small to read as "something happened".
    expect(component.barHeight(1, 100)).toBe(4);
  });

  it('treats a kind missing from a week as zero', () => {
    engagement.summary.mockReturnValue(
      of(
        summary({
          weeks: [{ week_start: '2026-08-31', counts: { cv_request: 2 } }],
        }),
      ),
    );
    fixture.detectChanges();

    const bars = el().querySelectorAll('.chart-week .bar');
    expect((bars[0] as HTMLElement).style.height).toBe('100%');
    expect((bars[1] as HTMLElement).style.height).toBe('0%');
    expect(component.weekTotal({ cv_request: 2 })).toBe(2);
  });
});
