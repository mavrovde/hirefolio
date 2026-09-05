import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map, shareReplay } from 'rxjs/operators';
import { environment } from '../../environments/environment';

/**
 * Site identity (#65) — everything the public app shows about its owner.
 * Fetched at runtime from the backend so a prebuilt image is rebranded by
 * env vars alone; components never hardcode identity.
 */
export interface SiteConfig {
    siteName: string;
    siteUrl: string;
    ownerName: string;
    ownerHeadline: string;
    ownerDescription: string;
    socialLinks: string[];
    analyticsId: string;
}

/** Backend wire shape (snake_case, see backend/app/api/site_config.py). */
interface SiteConfigDto {
    site_name: string;
    site_url: string;
    owner_name: string;
    owner_headline: string;
    owner_description: string;
    social_links: string[];
    analytics_id: string;
}

/**
 * Neutral fallback so the site still renders (unbranded, analytics off) when
 * the backend is unreachable — identity degrades, the page never breaks.
 */
export const DEFAULT_SITE_CONFIG: SiteConfig = {
    siteName: 'Portfolio',
    siteUrl: '',
    ownerName: 'Portfolio Owner',
    ownerHeadline: 'Software Engineer',
    ownerDescription: 'Professional software engineering portfolio.',
    socialLinks: [],
    analyticsId: '',
};

@Injectable({
    providedIn: 'root'
})
export class SiteConfigService {
    /** One fetch per app lifecycle; late subscribers replay the value. */
    public readonly config$: Observable<SiteConfig>;

    constructor(private http: HttpClient) {
        const url = `${environment.apiUrl}${environment.apiPrefix}/config/site`;
        this.config$ = this.http.get<SiteConfigDto>(url).pipe(
            map((dto) => ({
                siteName: dto.site_name,
                siteUrl: dto.site_url,
                ownerName: dto.owner_name,
                ownerHeadline: dto.owner_headline,
                ownerDescription: dto.owner_description,
                socialLinks: dto.social_links,
                analyticsId: dto.analytics_id,
            })),
            catchError(() => of(DEFAULT_SITE_CONFIG)),
            shareReplay(1)
        );
    }
}
