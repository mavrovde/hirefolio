import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { GoogleAnalyticsService } from './google-analytics.service';
import { NavigationEnd, Router } from '@angular/router';
import { Subject } from 'rxjs';

describe('GoogleAnalyticsService gtag-undefined branch (line 67 false)', () => {
  let service: GoogleAnalyticsService;
  let routerEvents: Subject<any>;

  beforeEach(() => {
    routerEvents = new Subject<any>();
    TestBed.configureTestingModule({
      providers: [
        GoogleAnalyticsService,
        { provide: Router, useValue: { events: routerEvents.asObservable() } },
      ],
    });
    service = TestBed.inject(GoogleAnalyticsService);
    (service as any).googleAnalyticsId = 'G-TESTID0001';
    // Prevent real script injection
    vi.spyOn(document.head, 'appendChild').mockImplementation((n: any) => n);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    ['google-analytics-script', 'google-analytics-init'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.remove();
    });
    delete (globalThis as any).gtag;
    delete (window as any).gtag;
  });

  it('does not throw and does not call gtag when gtag is undefined on navigation', () => {
    // Ensure the global binding is genuinely undefined
    delete (globalThis as any).gtag;
    delete (window as any).gtag;

    service.initialize(); // subscribes to router events

    expect(() => {
      routerEvents.next(new NavigationEnd(1, '/x', '/x'));
    }).not.toThrow();
  });

  it('calls gtag when defined on navigation (line 67 true branch)', () => {
    const gtagSpy = vi.fn();
    (globalThis as any).gtag = gtagSpy;
    (window as any).gtag = gtagSpy;

    service.initialize();
    routerEvents.next(new NavigationEnd(1, '/y', '/y'));

    expect(gtagSpy).toHaveBeenCalledWith('config', 'G-TESTID0001', { page_path: '/y' });
  });
});
