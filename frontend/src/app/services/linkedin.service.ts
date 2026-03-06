import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

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
    private authService = inject(AuthService);
    private apiUrl = `${environment.apiUrl}${environment.apiPrefix}/linkedin`;

    private getHeaders(): HeadersInit {
        const token = this.authService.getToken();
        const headers: HeadersInit = { 'Content-Type': 'application/json' };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    /**
     * Trigger a LinkedIn profile synchronization scan
     */
    async syncProfile(): Promise<any> {
        const response = await fetch(`${this.apiUrl}/profile-sync`, { headers: this.getHeaders() });
        if (!response.ok) throw new Error('Failed to sync profile');
        return await response.json();
    }

    /**
     * Fetch the admin's recent LinkedIn posts
     */
    async getPosts(): Promise<LinkedInPost[]> {
        const response = await fetch(`${this.apiUrl}/posts`, { headers: this.getHeaders() });
        if (!response.ok) throw new Error('Failed to fetch posts');
        return await response.json();
    }

    /**
     * Transfer a scraped LinkedIn post to the local system
     * @param post The post to transfer
     */
    async transferPost(post: LinkedInPost): Promise<LinkedInTransferResponse> {
        const response = await fetch(`${this.apiUrl}/transfer-post`, {
            method: 'POST',
            headers: this.getHeaders(),
            body: JSON.stringify({
                content: post.content,
                image_url: post.imageUrl || null,
                urn: post.urn || null
            })
        });
        if (!response.ok) throw new Error('Failed to transfer post');
        return await response.json();
    }
}
