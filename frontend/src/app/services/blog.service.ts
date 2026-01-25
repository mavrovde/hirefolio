import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { switchMap, shareReplay, map } from 'rxjs/operators';
import { LanguageService } from './language.service';
import { environment } from '../../environments/environment';

export interface BlogPost {
    id: number;
    title: string;
    slug: string;
    date: string;
    summary: string;
    content: string;
    language: string;
    published: boolean;
    tags: string[];
    created_at?: string;
}

export interface BlogSearchResult {
    id: number;
    title: string;
    slug: string;
    summary: string;
    relevance: number;
}

@Injectable({
    providedIn: 'root'
})
export class BlogService {
    private apiUrl = `${environment.apiUrl}/api/posts`;

    constructor(private http: HttpClient, private languageService: LanguageService) { }

    getPosts(publishedOnly: boolean = true, lang: string | null | undefined = undefined, tag: string | null = null): Observable<BlogPost[]> {
        // If lang is explicitly provided (string) or null (no filter), use it directly
        if (lang !== undefined) {
            const params: any = {};
            if (lang !== null) {
                params.lang = lang;
            }
            if (tag) {
                params.tag = tag;
            }
            if (publishedOnly) {
                params.published_only = 'true';
            } else {
                params.published_only = 'false';
            }
            return this.http.get<BlogPost[]>(this.apiUrl, { params }).pipe(shareReplay(1));
        }

        // Otherwise fallback to current language from service
        return this.languageService.currentLang$.pipe(
            switchMap(currentLang => {
                const params: any = { lang: currentLang };
                if (tag) {
                    params.tag = tag;
                }
                if (publishedOnly) {
                    params.published_only = 'true';
                } else {
                    params.published_only = 'false';
                }
                return this.http.get<BlogPost[]>(this.apiUrl, { params });
            }),
            shareReplay(1)
        );
    }

    getPost(slug: string): Observable<BlogPost | undefined> {
        return this.http.get<BlogPost>(`${this.apiUrl}/${slug}`);
    }

    createPost(post: any): Observable<BlogPost> {
        return this.http.post<BlogPost>(this.apiUrl, post);
    }


    getPostById(id: number): Observable<BlogPost> {
        return this.http.get<BlogPost>(`${this.apiUrl}/${id}`);
    }

    updatePostById(id: number, post: any): Observable<BlogPost> {
        return this.http.put<BlogPost>(`${this.apiUrl}/${id}`, post);
    }

    deletePostById(id: number): Observable<void> {
        return this.http.delete<void>(`${this.apiUrl}/${id}`);
    }

    searchPosts(query: string): Observable<BlogSearchResult[]> {
        return this.languageService.currentLang$.pipe(
            switchMap(lang => {
                return this.http.get<BlogSearchResult[]>(`${this.apiUrl}/search/semantic`, {
                    params: { q: query, lang: lang }
                });
            })
        );
    }

    suggestTags(title: string, content: string): Observable<{ tags: string[] }> {
        return this.http.post<{ tags: string[] }>(`${this.apiUrl}/suggest-tags`, { title, content });
    }
}
