import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CvRequestPayload {
    name: string;
    email: string;
    company?: string;
    message: string;
}

export interface CvResponse {
    success: boolean;
    message: string;
    download_url: string;
}

@Injectable({
    providedIn: 'root'
})
export class CvService {
    private apiUrl = `${environment.apiUrl}/api/cv`;

    constructor(private http: HttpClient) { }

    requestCv(payload: CvRequestPayload): Observable<CvResponse> {
        return this.http.post<CvResponse>(`${this.apiUrl}/request`, payload);
    }

    getDownloadUrl(relativePath: string): string {
        // If the URL is relative, prepend API URL base if needed, 
        // but usually the backend returns a path that works with the base.
        // If backend returns "/api/cv/download", and apiUrl includes "/api", we might need adjustment 
        // depending on environment.apiUrl (usually "http://localhost:8000" or empty for proxy).
        // Let's assume environment.apiUrl is the base host (e.g. http://localhost:8000).
        if (relativePath.startsWith('http')) return relativePath;
        if (environment.apiUrl) {
            return `${environment.apiUrl}${relativePath}`;
        }
        return relativePath;
    }
}
