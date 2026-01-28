import { TestBed } from '@angular/core/testing';
import { GoogleAnalyticsService } from './google-analytics.service';
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
    Object.defineProperty(window, 'gtag', {
      value: vi.fn(),
      writable: true
    });
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should initialize Google Analytics script', () => {
    const createElementSpy = vi.spyOn(document, 'createElement');
    // Prevent verify script execution
    const appendChildSpy = vi.spyOn(document.head, 'appendChild').mockImplementation((node: Node) => node);

    service.initialize();

    expect(createElementSpy).toHaveBeenCalledWith('script');
    expect(appendChildSpy).toHaveBeenCalled();

    // Verify script content contains correct ID
    const appendedScript = appendChildSpy.mock.calls[1][0] as HTMLScriptElement;
    expect(appendedScript.innerHTML).toContain('G-1QSMT6N045');
    expect(appendedScript.innerHTML).toContain("gtag('js', new Date());");
  });

  it('should track page views on navigation end', () => {
    service.initialize(); // Initialize to set up subscription

    const navigationEnd = new NavigationEnd(1, '/test-url', '/test-url');
    routerEventsSubject.next(navigationEnd);

    expect((window as any).gtag).toHaveBeenCalledWith('config', 'G-1QSMT6N045', {
      page_path: '/test-url',
    });
  });
});
