import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { switchMap, shareReplay, map } from 'rxjs/operators';
import { LanguageService } from './language.service';

export interface BlogPost {
    id: string;
    title: string;
    date: string;
    summary: string;
    content: string;
}

@Injectable({
    providedIn: 'root'
})
export class BlogService {
    private dataUrlBase = 'assets/blog_data';

    constructor(private http: HttpClient, private languageService: LanguageService) { }

    getPosts(): Observable<BlogPost[]> {
        return this.languageService.currentLang$.pipe(
            switchMap(lang => {
                return this.http.get<BlogPost[]>(`${this.dataUrlBase}_${lang}.json`);
            }),
            shareReplay(1)
        );
    }

    getPost(id: string): Observable<BlogPost | undefined> {
        return this.getPosts().pipe(
            map(posts => posts.find(p => p.id === id))
        );
    }
}
