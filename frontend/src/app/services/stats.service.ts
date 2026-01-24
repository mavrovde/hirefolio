import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface PostStats {
    total: number;
    published: number;
    drafts: number;
    by_language: { [key: string]: number };
}

export interface PostSummary {
    title: string;
    slug: string;
    created_at: string;
    views: number;
}

export interface SystemStats {
    posts: PostStats;
    users: number;
    subscribers: number;
    visitors: string;
    top_tags: { [key: string]: number };
    recent_posts: PostSummary[];
    system_health: { [key: string]: boolean };
}

@Injectable({
    providedIn: 'root'
})
export class StatsService {
    private apiUrl = `${environment.apiUrl}/api/stats`;

    constructor(private http: HttpClient) { }

    getStats(): Observable<SystemStats> {
        return this.http.get<SystemStats>(this.apiUrl);
    }
}
