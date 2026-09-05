import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router, NavigationEnd } from '@angular/router';
import { filter, take } from 'rxjs/operators';
import { SiteConfigService } from './site-config.service';

// Declare gtag as a global variable
declare const gtag: Function;

@Injectable({
    providedIn: 'root'
})
export class GoogleAnalyticsService {
    // The measurement id comes from the runtime site config (#65) — empty
    // disables analytics entirely; no id is ever baked into the bundle.
    private googleAnalyticsId = '';

    constructor(
        @Inject(PLATFORM_ID) private platformId: Object,
        private router: Router,
        private siteConfig: SiteConfigService
    ) { }

    private isInitialized = false;

    public initialize() {
        if (!isPlatformBrowser(this.platformId) || this.isInitialized) {
            return;
        }
        // config$ is a one-shot shareReplay stream; take(1) both bounds the
        // subscription and re-checks the guards once the id is known.
        // cd-safety-ok: assigns a private service field and injects <script> tags — nothing template-bound.
        this.siteConfig.config$.pipe(take(1)).subscribe((cfg) => {
            this.googleAnalyticsId = cfg.analyticsId;
            if (this.googleAnalyticsId) {
                this.loadScript();
                this.initGtag();
                this.trackPageViews();
                this.isInitialized = true;
            }
        });
    }

    private loadScript() {
        const scriptId = 'google-analytics-script';
        if (document.getElementById(scriptId)) {
            return;
        }
        const script = document.createElement('script');
        script.id = scriptId;
        script.async = true;
        script.src = `https://www.googletagmanager.com/gtag/js?id=${this.googleAnalyticsId}`;
        document.head.appendChild(script);
    }

    private initGtag() {
        const scriptId = 'google-analytics-init';
        if (document.getElementById(scriptId)) {
            return;
        }
        const script = document.createElement('script');
        script.id = scriptId;
        script.innerHTML = `
      window.dataLayer = window.dataLayer || [];
      if (!window.gtag) {
        function gtag(){dataLayer.push(arguments);}
        window.gtag = gtag;
        gtag('js', new Date());
        gtag('config', '${this.googleAnalyticsId}');
      }
    `;
        document.head.appendChild(script);
    }

    private trackPageViews() {
        this.router.events
            .pipe(filter(event => event instanceof NavigationEnd))
            .subscribe((event: any) => {
                if (typeof gtag !== 'undefined') {
                    gtag('config', this.googleAnalyticsId, {
                        'page_path': event.urlAfterRedirects
                    });
                }
            });
    }
}
