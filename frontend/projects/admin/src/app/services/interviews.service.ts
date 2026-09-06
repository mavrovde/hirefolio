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

export const INTERVIEW_KINDS = ['video', 'phone', 'onsite', 'other'] as const;

export const INTERVIEW_OUTCOMES = [
    'scheduled',
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

    /** The `.ics` URL for a round. Returned rather than fetched: the browser
     *  downloads it directly, and building it in one place keeps the route
     *  shape out of the template. */
    icsUrl(id: string): string {
        return `${this.base}/interviews/${id}.ics`;
    }
}
