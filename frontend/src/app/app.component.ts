import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { GoogleAnalyticsService } from './services/google-analytics.service';
import { CookieConsentComponent } from './components/cookie-consent/cookie-consent.component';
import { SystemStatsComponent } from './components/stats/stats.component';

import { ViewportScroller } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, CookieConsentComponent, SystemStatsComponent],
  template: `
    <router-outlet></router-outlet>
    <app-cookie-consent></app-cookie-consent>
    <app-system-stats></app-system-stats>
  `,
})
export class AppComponent implements OnInit {
  constructor(
    private googleAnalyticsService: GoogleAnalyticsService,
    private viewportScroller: ViewportScroller
  ) { }

  ngOnInit() {
    this.googleAnalyticsService.initialize();
    // Set offset for sticky header (approx 80px)
    this.viewportScroller.setOffset([0, 80]);
  }
}
