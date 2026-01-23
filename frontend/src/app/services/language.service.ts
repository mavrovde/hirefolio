import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { map, catchError, shareReplay } from 'rxjs/operators';

export type Language = 'en' | 'de';

@Injectable({
    providedIn: 'root'
})
export class LanguageService {
    private currentLangSubject = new BehaviorSubject<Language>('en');
    currentLang$ = this.currentLangSubject.asObservable();

    private translationsSubject = new BehaviorSubject<any>({});
    translations$ = this.translationsSubject.asObservable();

    constructor(private http: HttpClient) {
        this.loadTranslations('en');
    }

    setLanguage(lang: Language) {
        if (this.currentLangSubject.value !== lang) {
            this.currentLangSubject.next(lang);
            this.loadTranslations(lang);
        }
    }

    getCurrentLanguage(): Language {
        return this.currentLangSubject.value;
    }

    private loadTranslations(lang: Language) {
        this.http.get(`assets/i18n/${lang}.json`).pipe(
            catchError(err => {
                console.error(`Error loading translations for ${lang}`, err);
                return of({});
            }),
            shareReplay(1)
        ).subscribe(translations => {
            this.translationsSubject.next(translations);
        });
    }

    translate(key: string): Observable<string> {
        return this.translations$.pipe(
            map(translations => {
                const keys = key.split('.');
                let value = translations;
                for (const k of keys) {
                    value = value?.[k];
                }
                return value || key;
            })
        );
    }
}
