import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/** Admin interview calendar (#247 phase 2 / #70). Mirrors the backend schemas
 *  in `app/api/interviews.py` — every field is explicit, no `any` (rule 4). */
export interface Interview {
    id: string;
    opportunity_id: string;
    scheduled_at: string;
    duration_minutes: number;
    kind: string;
    location_or_link: string | null;
    interviewer: string | null;
    notes: string | null;
    outcome: string;
    created_at: string;
    updated_at: string;
}

/** `/upcoming` returns the interview plus the company context the dashboard
 *  needs, so the caller never has to fan out to the opportunities endpoint. */
export interface UpcomingInterview extends Interview {
    company: string;
    role_title: string;
    stage: string;
}

export interface InterviewInput {
    scheduled_at: string;
    duration_minutes?: number;
    kind?: string;
    location_or_link?: string | null;
    interviewer?: string | null;
    notes?: string | null;
}

// Mirrors OUTCOMES in backend/app/models/interview.py — rows are created
// 'pending', and PATCH 422s on anything outside this set. The first version
// of this list said 'scheduled', a value the backend has never had; both specs
// hard-coded the fiction, so 371 green tests never sent one real PATCH (#292
// review round 1 — the §34 fake-green, in a fixture this time).
export const INTERVIEW_OUTCOMES = [
    'pending',
    'passed',
    'failed',
    'cancelled',
] as const;

@Injectable({
    providedIn: 'root'
})
export class InterviewsService {
    private http = inject(HttpClient);
    private base = `${environment.apiUrl}${environment.apiPrefix}/admin`;

    /** Scheduled rounds across ALL opportunities inside the window. */
    upcoming(days = 14): Observable<UpcomingInterview[]> {
        const params = new HttpParams().set('days', days);
        return this.http.get<UpcomingInterview[]>(`${this.base}/interviews/upcoming`, { params });
    }

    listFor(opportunityId: string): Observable<Interview[]> {
        return this.http.get<Interview[]>(
            `${this.base}/opportunities/${opportunityId}/interviews`,
        );
    }

    schedule(opportunityId: string, input: InterviewInput): Observable<Interview> {
        return this.http.post<Interview>(
            `${this.base}/opportunities/${opportunityId}/interviews`,
            input,
        );
    }

    update(id: string, patch: Partial<InterviewInput> & { outcome?: string }): Observable<Interview> {
        return this.http.patch<Interview>(`${this.base}/interviews/${id}`, patch);
    }

    remove(id: string): Observable<void> {
        return this.http.delete<void>(`${this.base}/interviews/${id}`);
    }

    /** The `.ics` for a round, fetched WITH auth. A plain `<a href>` carries
     *  no Bearer token, so the admin-gated endpoint answers 401 for every
     *  user — the first version of this screen shipped exactly that dead link
     *  (#292 review round 1). Fetching through HttpClient lets the auth
     *  interceptor sign the request; the caller turns the blob into a save. */
    downloadIcs(id: string): Observable<Blob> {
        return this.http.get(`${this.base}/interviews/${id}.ics`, {
            responseType: 'blob',
        });
    }
}
