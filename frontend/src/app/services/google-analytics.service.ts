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

    public initialize() {
        if (isPlatformBrowser(this.platformId) && this.googleAnalyticsId) {
            this.loadScript();
            this.initGtag();
            this.trackPageViews();
        }
    }

    private loadScript() {
        const script = document.createElement('script');
        script.async = true;
        script.src = `https://www.googletagmanager.com/gtag/js?id=${this.googleAnalyticsId}`;
        document.head.appendChild(script);
    }

    private initGtag() {
        const script = document.createElement('script');
        script.innerHTML = `
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', '${this.googleAnalyticsId}');
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
