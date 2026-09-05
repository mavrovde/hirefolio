import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { Title, Meta } from '@angular/platform-browser';
import { isPlatformBrowser } from '@angular/common';
import { BehaviorSubject } from 'rxjs';
import { SiteConfigService, SiteConfig, DEFAULT_SITE_CONFIG } from './site-config.service';

export interface SeoData {
    title?: string;
    description?: string;
    image?: string;
    url?: string;
    type?: string;
    keywords?: string;
    twitterCard?: string;
}

@Injectable({
    providedIn: 'root'
})
export class SeoService {
    // Identity comes from the runtime site config (#65); these derived fields
    // start at the neutral defaults and update when the config arrives, at
    // which point the last-applied SEO data is re-applied so no page keeps
    // placeholder branding.
    private site: SiteConfig = DEFAULT_SITE_CONFIG;
    private lastSeoData: SeoData | null = null;

    public jsonLdSchema$ = new BehaviorSubject<any>(null);

    constructor(
        private titleService: Title,
        private metaService: Meta,
        @Inject(PLATFORM_ID) private platformId: Object,
        siteConfig: SiteConfigService
    ) {
        // cd-safety-ok: writes go to the Title/Meta DOM services, never to a template-bound property — no repaint needed.
        siteConfig.config$.subscribe((cfg) => {
            this.site = cfg;
            // Re-brand whatever the current page already applied. Title/Meta
            // are DOM-level services, not change-detection consumers, so this
            // is zoneless-safe by construction.
            this.updateSeo(this.lastSeoData ?? {});
        });
    }

    private get baseTitle(): string {
        return `${this.site.ownerName} | ${this.site.ownerHeadline}`;
    }
    private get defaultDescription(): string {
        return this.site.ownerDescription;
    }
    private get baseUrl(): string {
        return this.site.siteUrl;
    }
    private get defaultImage(): string {
        return `${this.site.siteUrl}/assets/og-image.png`;
    }

    updateSeo(data: SeoData): void {
        this.lastSeoData = data;
        const fullTitle = data.title ? `${data.title} | ${this.site.ownerName}` : this.baseTitle;
        const description = data.description || this.defaultDescription;
        const image = data.image ? `${this.baseUrl}${data.image}` : this.defaultImage;
        const url = data.url ? `${this.baseUrl}${data.url}` : this.baseUrl;
        const type = data.type || 'website';
        const keywords = data.keywords || 'Software Engineering, Angular, Python, AI, Cloud Architecture';

        this.titleService.setTitle(fullTitle);

        // Standard Meta
        this.metaService.updateTag({ name: 'description', content: description });
        this.metaService.updateTag({ name: 'keywords', content: keywords });

        // Open Graph
        this.metaService.updateTag({ property: 'og:title', content: fullTitle });
        this.metaService.updateTag({ property: 'og:description', content: description });
        this.metaService.updateTag({ property: 'og:image', content: image });
        this.metaService.updateTag({ property: 'og:url', content: url });
        this.metaService.updateTag({ property: 'og:type', content: type });

        // Twitter
        this.metaService.updateTag({ name: 'twitter:card', content: data.twitterCard || 'summary_large_image' });
        this.metaService.updateTag({ name: 'twitter:title', content: fullTitle });
        this.metaService.updateTag({ name: 'twitter:description', content: description });
        this.metaService.updateTag({ name: 'twitter:image', content: image });

        // Canonical link
        if (isPlatformBrowser(this.platformId)) {
            this.updateCanonicalUrl(url);
        }
    }

    setJsonLd(schema: any): void {
        this.jsonLdSchema$.next(schema);
    }

    /**
     * Mark the current page as a genuine "not found": a not-found <title> plus a
     * `robots: noindex` meta so crawlers never index a 404 body. Rendered into the
     * SSR HTML (alongside the real 404 status set by the component) and kept after
     * hydration (#109).
     */
    setNotFound(): void {
        this.titleService.setTitle(`Post not found | ${this.site.ownerName}`);
        this.metaService.updateTag({ name: 'robots', content: 'noindex' });
    }

    private updateCanonicalUrl(url: string): void {
        let link: HTMLLinkElement | null = document.querySelector("link[rel='canonical']");
        if (!link) {
            link = document.createElement('link');
            link.setAttribute('rel', 'canonical');
            document.head.appendChild(link);
        }
        link.setAttribute('href', url);
    }
}
