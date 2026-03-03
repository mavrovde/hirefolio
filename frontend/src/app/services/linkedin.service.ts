import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface LinkedInPost {
    id: string;
    content: string;
    imageUrl?: string;
    url?: string;
    urn?: string;
    time?: string;
}

export interface LinkedInTransferResponse {
    id: number;
    message: string;
}

@Injectable({
    providedIn: 'root'
})
export class LinkedinService {
    private http = inject(HttpClient);
    private apiUrl = `${environment.apiUrl}/linkedin`;

    /**
     * Trigger a LinkedIn profile synchronization scan
     */
    syncProfile(): Observable<any> {
        return this.http.get<any>(`${this.apiUrl}/profile-sync`);
    }

    /**
     * Fetch the admin's recent LinkedIn posts
     */
    getPosts(): Observable<LinkedInPost[]> {
        return this.http.get<LinkedInPost[]>(`${this.apiUrl}/posts`);
    }

    /**
     * Transfer a scraped LinkedIn post to the local system
     * @param post The post to transfer
     */
    transferPost(post: LinkedInPost): Observable<LinkedInTransferResponse> {
        return this.http.post<LinkedInTransferResponse>(`${this.apiUrl}/transfer-post`, {
            content: post.content,
            image_url: post.imageUrl || null,
            urn: post.urn || null
        });
    }
}
