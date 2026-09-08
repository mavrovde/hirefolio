import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { catchError, map, shareReplay, startWith, switchMap } from 'rxjs/operators';
import {
  EngagementCounts,
  EngagementService,
  EngagementSummary,
} from '../../../services/engagement.service';

/** The whole screen in one value, so the template never renders a half-state. */
export type AnalyticsState =
  | { status: 'loading' }
  /** The backend 404s when ENGAGEMENT_ANALYTICS_ENABLED is off (#249). */
  | { status: 'disabled' }
  | { status: 'error' }
  | { status: 'ready'; summary: EngagementSummary; peak: number };

/**
 * Private engagement dashboard (#249): totals, a per-week trend and the recent
 * activity feed, plus the two housekeeping actions (retention purge, weekly
 * digest) the owner would otherwise have no way to trigger.
 *
 * The admin app is ZONELESS, so this component holds NO imperatively-assigned
 * render state: every value the template reads arrives through the async pipe,
 * which marks the view itself (rule 5 / lessons §1). Reloading is a re-emission
 * on `weeks$`, not a property write.
 */
@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analytics.component.html',
  styleUrls: ['./analytics.component.css'],
})
export class AnalyticsComponent {
  private engagement = inject(EngagementService);

  readonly windows = [4, 8, 12, 26];

  private static readonly LABELS: Record<string, string> = {
    cv_request: 'CV requests',
    cv_download: 'CV downloads',
    contact_submitted: 'Contact submissions',
  };

  private readonly weeksSubject = new BehaviorSubject<number>(8);
  /** Current trend window; read by the template to mark the active button. */
  weeks = 8;

  private readonly actionSubject = new BehaviorSubject<string | null>(null);
  readonly action$: Observable<string | null> = this.actionSubject.asObservable();

  private readonly busySubject = new BehaviorSubject<boolean>(false);
  readonly busy$: Observable<boolean> = this.busySubject.asObservable();

  readonly state$: Observable<AnalyticsState> = this.weeksSubject.pipe(
    switchMap((weeks) =>
      this.engagement.summary(weeks).pipe(
        map(
          (summary): AnalyticsState => ({
            status: 'ready',
            summary,
            peak: this.peakOf(summary),
          }),
        ),
        catchError((err: { status?: number }) =>
          of<AnalyticsState>(err.status === 404 ? { status: 'disabled' } : { status: 'error' }),
        ),
        startWith<AnalyticsState>({ status: 'loading' }),
      ),
    ),
    shareReplay(1),
  );

  changeWindow(weeks: number): void {
    this.weeks = weeks;
    this.weeksSubject.next(weeks);
  }

  reload(): void {
    this.weeksSubject.next(this.weeks);
  }

  /** The busiest single bar, so the chart scales to its own data. */
  private peakOf(summary: EngagementSummary): number {
    return summary.weeks.reduce(
      (max, week) =>
        Math.max(max, ...summary.kinds.map((k) => this.countOf(week.counts, k))),
      0,
    );
  }

  /** Index access on a `Record<string, number>` is TYPED as `number`, but a
   *  backend that gains a kind mid-deploy really can omit it — and a missing
   *  count must read as 0, not `NaN%`, in the chart. */
  countOf(counts: EngagementCounts, kind: string): number {
    const value: number | undefined = counts[kind];
    return value ?? 0;
  }

  /** Percent height of one bar. A non-zero week always stays visible — a
   *  rounded-to-zero bar reads as "nothing happened", which is a lie. */
  barHeight(count: number, peak: number): number {
    return count === 0 ? 0 : Math.max(4, Math.round((count / peak) * 100));
  }

  weekTotal(counts: Record<string, number>): number {
    return Object.values(counts).reduce((sum, n) => sum + n, 0);
  }

  label(kind: string): string {
    const known: string | undefined = AnalyticsComponent.LABELS[kind];
    return known ?? kind.replace(/_/g, ' ');
  }

  /** Apply the retention knob now (there is no scheduler in this app). */
  purge(): void {
    this.busySubject.next(true);
    this.engagement.purge().subscribe({
      next: (result) => {
        this.actionSubject.next(
          `Purged ${result.deleted} event(s) older than ${result.retention_days} day(s).`,
        );
        this.busySubject.next(false);
        this.reload();
      },
      error: () => {
        this.actionSubject.next('Failed to purge old events.');
        this.busySubject.next(false);
      },
    });
  }

  sendDigest(): void {
    this.busySubject.next(true);
    this.engagement.sendDigest().subscribe({
      next: (result) => {
        this.actionSubject.next(
          result.sent
            ? 'Weekly digest sent.'
            : 'Digest skipped: SMTP is not configured on this server.',
        );
        this.busySubject.next(false);
      },
      error: () => {
        this.actionSubject.next('Failed to send the weekly digest.');
        this.busySubject.next(false);
      },
    });
  }
}
