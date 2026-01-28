import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { map, catchError, shareReplay } from 'rxjs/operators';
import { StorageService } from './storage.service';

export type Language = 'en' | 'de';

@Injectable({
  providedIn: 'root',
})
export class LanguageService {
  private currentLangSubject = new BehaviorSubject<Language>('en');
  currentLang$ = this.currentLangSubject.asObservable();

  private translationsSubject = new BehaviorSubject<any>({});
  translations$ = this.translationsSubject.asObservable();

  constructor(private http: HttpClient, private storageService: StorageService) {
    // Try to load saved language if exists (and consented)
    const savedLang = this.storageService.getItem('language') as Language;
    if (savedLang && (savedLang === 'en' || savedLang === 'de')) {
      this.currentLangSubject.next(savedLang);
      this.loadTranslations(savedLang);
    } else {
      this.loadTranslations('en');
    }
  }

  setLanguage(lang: Language) {
    if (this.currentLangSubject.value !== lang) {
      this.currentLangSubject.next(lang);
      this.storageService.setItem('language', lang);
      this.loadTranslations(lang);
    }
  }

  getCurrentLanguage(): Language {
    return this.currentLangSubject.value;
  }

  private loadTranslations(lang: Language) {
    this.http
      .get(`/assets/i18n/${lang}.json`)
      .pipe(
        catchError((err) => {
          console.error(`Error loading translations for ${lang}`, err);
          return of({});
        }),
        shareReplay(1),
      )
      .subscribe((translations) => {
        this.translationsSubject.next(translations);
      });
  }

  translate(key: string): Observable<string> {
    return this.translations$.pipe(
      map((translations) => {
        const keys = key.split('.');
        let value = translations;
        for (const k of keys) {
          value = value?.[k];
        }
        return value || key;
      }),
    );
  }
}
