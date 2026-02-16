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
  content: string;
  summary?: string;
  image_url?: string;
  language: string;
  published: boolean;
  tags: string[];
  created_at: string;
  updated_at?: string;
  similarity?: number; // For search results
}

export interface BlogSearchResult {
  id: number;
  title: string;
  slug: string;
  summary: string;
  relevance: number;
  image_url?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

@Injectable({
  providedIn: 'root',
})
export class BlogService {
  private apiUrl = `${environment.apiUrl}${environment.apiPrefix}/posts`;

  constructor(
    private http: HttpClient,
    private languageService: LanguageService,
  ) { }

  getPosts(
    publishedOnly: boolean = true,
    lang: string | null | undefined = undefined,
    tag: string | null = null,
    page: number = 1,
    pageSize: number = 10,
    sortBy: string = 'created_at',
    sortOrder: 'asc' | 'desc' = 'desc',
    search: string | null = null,
  ): Observable<PaginatedResponse<BlogPost>> {
    // If lang is explicitly provided (string) or null (no filter), use it directly
    if (lang !== undefined) {
      const params: any = {
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (lang !== null) {
        params.lang = lang;
      }
      if (tag) {
        params.tag = tag;
      }
      if (search) {
        params.search = search;
      }
      if (publishedOnly) {
        params.published_only = 'true';
      } else {
        params.published_only = 'false';
      }
      return this.http.get<PaginatedResponse<BlogPost>>(this.apiUrl, { params }).pipe(shareReplay(1));
    }

    // Otherwise fallback to current language from service
    return this.languageService.currentLang$.pipe(
      switchMap((currentLang) => {
        const params: any = {
          lang: currentLang,
          page: page.toString(),
          page_size: pageSize.toString(),
          sort_by: sortBy,
          sort_order: sortOrder,
        };
        if (tag) {
          params.tag = tag;
        }
        if (search) {
          params.search = search;
        }
        if (publishedOnly) {
          params.published_only = 'true';
        } else {
          params.published_only = 'false';
        }
        return this.http.get<PaginatedResponse<BlogPost>>(this.apiUrl, { params });
      }),
      shareReplay(1),
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
      switchMap((lang) => {
        return this.http.get<BlogSearchResult[]>(`${this.apiUrl}/search/semantic`, {
          params: { q: query, lang: lang },
        });
      }),
    );
  }

  suggestTags(title: string, content: string): Observable<{ tags: string[] }> {
    return this.http.post<{ tags: string[] }>(`${this.apiUrl}/suggest-tags`, { title, content });
  }

  suggestPostDetails(content: string, field: string = 'all'): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/suggest-details`, { content, field });
  }

  getStaticPosts(page: number = 1, pageSize: number = 10): Observable<PaginatedResponse<BlogPost>> {
    const lang = this.languageService.getCurrentLanguage();
    return this.http.get<any[]>(`/assets/blog_data_${lang}.json`).pipe(
      map((posts) => {
        const total = posts.length;
        const start = (page - 1) * pageSize;
        const items = posts.slice(start, start + pageSize).map((p: any, i: number) => ({
          id: i + start,
          title: p.title,
          slug: p.id || p.slug || `post-${i + start}`,
          content: p.content || '',
          summary: p.summary || '',
          image_url: p.image_url,
          language: lang,
          published: true,
          tags: p.tags || [],
          created_at: p.date || new Date().toISOString(),
        }));
        return {
          items,
          total,
          page,
          page_size: pageSize,
          total_pages: Math.ceil(total / pageSize),
        } as PaginatedResponse<BlogPost>;
      }),
    );
  }

  uploadImage(id: number, file: File): Observable<BlogPost> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.put<BlogPost>(`${this.apiUrl}/${id}/image`, formData);
  }
}
