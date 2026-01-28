import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CvRequestSummary {
    id: string;
    name: string;
    email: string;
    company: string;
    message: string;
    created_at: string;
    consent_given: boolean;
    cv_version: string;
}

export interface CvVersion {
    id: string;
    filename: string;
    version: string;
    is_active: boolean;
    created_at: string;
}

@Injectable({
    providedIn: 'root'
})
export class AdminCvService {
    private apiUrl = `${environment.apiUrl}/admin/cv`;

    constructor(private http: HttpClient) { }

    uploadCv(file: File, version: string): Observable<any> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('version', version);
        return this.http.post(`${this.apiUrl}/upload`, formData);
    }

    getRequests(): Observable<CvRequestSummary[]> {
        return this.http.get<CvRequestSummary[]>(`${this.apiUrl}/requests`);
    }

    getVersions(): Observable<CvVersion[]> {
        return this.http.get<CvVersion[]>(`${this.apiUrl}/versions`);
    }
}
