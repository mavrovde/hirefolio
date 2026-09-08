import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/** Private engagement analytics (#249) — owner-only, first-party counts. */
export const ENGAGEMENT_KINDS = ['cv_request', 'cv_download', 'contact_submitted'] as const;
export type EngagementKind = (typeof ENGAGEMENT_KINDS)[number];

/** Counts keyed by kind. The backend zero-fills every known kind, so a key is
 *  always present — but a future backend kind is still just a string key. */
export type EngagementCounts = Record<string, number>;

export interface EngagementWeek {
  /** Monday of the bucket, `YYYY-MM-DD` in UTC. */
  week_start: string;
  counts: EngagementCounts;
}

export interface EngagementFeedItem {
  id: string;
  kind: string;
  subject_id: string | null;
  /** Resolved from the source record server-side; null when it is gone. */
  label: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface EngagementSummary {
  kinds: string[];
  totals: EngagementCounts;
  weeks: EngagementWeek[];
  recent: EngagementFeedItem[];
}

export interface PurgeResult {
  deleted: number;
  retention_days: number;
}

export interface DigestResult {
  sent: boolean;
}

@Injectable({ providedIn: 'root' })
export class EngagementService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}${environment.apiPrefix}/admin/analytics`;

  summary(weeks = 8, limit = 20): Observable<EngagementSummary> {
    const params = new HttpParams().set('weeks', weeks).set('limit', limit);
    return this.http.get<EngagementSummary>(`${this.apiUrl}/engagement`, { params });
  }

  /** Apply the retention knob now (the backend owns the cutoff). */
  purge(): Observable<PurgeResult> {
    return this.http.post<PurgeResult>(`${this.apiUrl}/purge`, {});
  }

  /** Send the weekly summary email now; `sent: false` = SMTP unconfigured. */
  sendDigest(): Observable<DigestResult> {
    return this.http.post<DigestResult>(`${this.apiUrl}/digest`, {});
  }
}
