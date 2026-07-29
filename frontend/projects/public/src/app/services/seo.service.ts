import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { Title, Meta } from '@angular/platform-browser';
import { isPlatformBrowser } from '@angular/common';
import { BehaviorSubject } from 'rxjs';

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
    private baseTitle = 'Sergii Mavrov | Principal Software Engineer';
    private defaultDescription = 'Professional portfolio of Sergii Mavrov, a Principal Software Engineer specialized in Cloud, AI, and Full-Stack Development.';
    private defaultImage = 'https://mavrov.de/assets/og-image.png';
    private baseUrl = 'https://mavrov.de';

    public jsonLdSchema$ = new BehaviorSubject<any>(null);

    constructor(
        private titleService: Title,
        private metaService: Meta,
        @Inject(PLATFORM_ID) private platformId: Object
    ) { }

    updateSeo(data: SeoData): void {
        const fullTitle = data.title ? `${data.title} | Sergii Mavrov` : this.baseTitle;
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
        this.titleService.setTitle('Post not found | Sergii Mavrov');
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
