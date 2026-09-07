import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/** Runtime site settings (#271) — the first key is the owner's job-search
 *  availability, rendered on the public hero. Vocabulary mirrors
 *  AVAILABILITY_STATES in backend/app/api/site_settings.py. */
export const AVAILABILITY_STATES = ['open', 'listening', 'not_looking'] as const;

export interface AvailabilityValue {
    value: string;
}

@Injectable({
    providedIn: 'root'
})
export class SiteSettingsService {
    private http = inject(HttpClient);
    private base = `${environment.apiUrl}${environment.apiPrefix}/admin/site-settings`;

    getAvailability(): Observable<AvailabilityValue> {
        return this.http.get<AvailabilityValue>(`${this.base}/availability`);
    }

    setAvailability(value: string): Observable<AvailabilityValue> {
        return this.http.put<AvailabilityValue>(`${this.base}/availability`, { value });
    }
}
