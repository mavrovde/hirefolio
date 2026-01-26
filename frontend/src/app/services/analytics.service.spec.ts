import { TestBed } from '@angular/core/testing';
import { GoogleAnalyticsService } from './analytics.service';
import { NavigationEnd, Router } from '@angular/router';
import { Subject } from 'rxjs';
import { vi } from 'vitest';

describe('GoogleAnalyticsService', () => {
  let service: GoogleAnalyticsService;
  let router: Router;
  let routerEventsSubject: Subject<any>;

  beforeEach(() => {
    routerEventsSubject = new Subject<any>();
    const routerMock = {
      events: routerEventsSubject.asObservable(),
    };

    TestBed.configureTestingModule({
      providers: [GoogleAnalyticsService, { provide: Router, useValue: routerMock }],
    });
    service = TestBed.inject(GoogleAnalyticsService);
    router = TestBed.inject(Router);

    // Mock window.gtag
    (window as any).gtag = vi.fn();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should initialize Google Analytics script', () => {
    const createElementSpy = vi.spyOn(document, 'createElement');
    const appendChildSpy = vi.spyOn(document.head, 'appendChild');

    service.initializeGoogleAnalytics();

    expect(createElementSpy).toHaveBeenCalledWith('script');
    expect(appendChildSpy).toHaveBeenCalled();
  });
});
