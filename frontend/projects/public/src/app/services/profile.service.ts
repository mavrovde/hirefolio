import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { shareReplay, switchMap } from 'rxjs/operators';
import { LanguageService } from './language.service';

export interface Profile {
  name: string;
  headline: string;
  location: string;
  about: string;
  experience: Experience[];
  education: Education[];
  skills: string[];
  certifications: Certification[];
  languages: Language[];
  recommendations: Recommendation[];
  contact: Contact;
}

export interface Contact {
  email: string;
  linkedin: string;
}

export interface Experience {
  title: string;
  company: string;
  employmentType?: string;
  startDate: string;
  endDate: string;
  duration?: string;
  location?: string;
  workType?: string;
  description?: string;
  skills?: string[];
  companyLinkedInUrl?: string;
}

export interface Education {
  school: string;
  degree: string;
  years: string;
  skills?: string;
}

export interface Certification {
  name: string;
  issuer: string;
  date: string;
  credentialUrl?: string;
}

export interface Language {
  name: string;
  proficiency: string;
}

export interface Recommendation {
  author: string;
  authorTitle: string;
  authorLinkedInUrl: string;
  text: string;
}

@Injectable({
  providedIn: 'root',
})
export class ProfileService {
  private dataUrlBase = 'assets/profile_data';

  // Cache observable to prevent multiple requests
  private profile$: Observable<Profile> | null = null;

  constructor(
    private http: HttpClient,
    private languageService: LanguageService,
  ) {}

  getProfile(): Observable<Profile> {
    return this.languageService.currentLang$.pipe(
      switchMap((lang) => {
        return this.http.get<Profile>(`${this.dataUrlBase}_${lang}.json`);
      }),
      shareReplay(1),
    );
  }
}
