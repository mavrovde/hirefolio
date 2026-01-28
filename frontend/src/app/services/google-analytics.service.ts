import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { environment } from '../../environments/environment';

// Declare gtag as a global variable
declare const gtag: Function;

@Injectable({
    providedIn: 'root'
})
export class GoogleAnalyticsService {
    private googleAnalyticsId = environment.googleAnalyticsId;

    constructor(
        @Inject(PLATFORM_ID) private platformId: Object,
        private router: Router
    ) { }

    private isInitialized = false;

    public initialize() {
        if (isPlatformBrowser(this.platformId) && this.googleAnalyticsId && !this.isInitialized) {
            this.loadScript();
            this.initGtag();
            this.trackPageViews();
            this.isInitialized = true;
        }
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
