import { Injectable } from '@angular/core';
import { BehaviorSubject, of } from 'rxjs';

@Injectable()
export class MockLanguageService {
  currentLang$ = new BehaviorSubject('en');
  translations$ = new BehaviorSubject({});

  setLanguage(lang: string) {
    this.currentLang$.next(lang);
  }

  getCurrentLanguage() {
    return this.currentLang$.value;
  }

  translate(key: string) {
    return of(key);
  }
}
