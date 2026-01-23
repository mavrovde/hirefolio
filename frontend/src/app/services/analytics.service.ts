import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { environment } from '../../environments/environment';

declare let gtag: Function;

@Injectable({
    providedIn: 'root'
})
export class GoogleAnalyticsService {
    private analyticsId = environment.googleAnalyticsId;

    constructor(@Inject(PLATFORM_ID) private platformId: Object) { }

    public initializeGoogleAnalytics(): void {
        if (isPlatformBrowser(this.platformId) && this.analyticsId) {
            // Load Google Analytics Script
            const script = document.createElement('script');
            script.async = true;
            script.src = `https://www.googletagmanager.com/gtag/js?id=${this.analyticsId}`;
            document.head.appendChild(script);

            // Initialize GTAG
            const script2 = document.createElement('script');
            script2.innerHTML = `
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', '${this.analyticsId}');
      `;
            document.head.appendChild(script2);
        }
    }

    public trackPageViews(): void {
        if (isPlatformBrowser(this.platformId) && typeof gtag === 'function') {
            // Can be extended to listen to Router events if needed
            // For single page, initial load is tracked by config
        }
    }
}
