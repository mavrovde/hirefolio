import { Injectable } from '@angular/core';
import { BehaviorSubject, map, Observable, of } from 'rxjs';

@Injectable()
export class MockLanguageService {
  currentLangSubject = new BehaviorSubject<string>('en');
  currentLang$ = this.currentLangSubject.asObservable();

  translationsSubject = new BehaviorSubject<any>({});
  translations$ = this.translationsSubject.asObservable();

  setLanguage(lang: string) {
    this.currentLangSubject.next(lang);
  }

  getCurrentLanguage() {
    return this.currentLangSubject.value;
  }

  translate(key: string): Observable<string> {
    if (!key) return of(key);
    return this.translations$.pipe(
      map(t => {
        const keys = key.split('.');
        let val = t;
        for (const k of keys) {
          val = val?.[k];
        }
        return val || key;
      })
    );
  }

  // Helper for tests
  setTranslations(t: any) {
    this.translationsSubject.next(t);
  }
}
