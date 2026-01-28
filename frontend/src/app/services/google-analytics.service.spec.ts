import { TestBed } from '@angular/core/testing';
import { GoogleAnalyticsService } from './google-analytics.service';
import { NavigationEnd, Router } from '@angular/router';
import { Subject } from 'rxjs';
import { vi } from 'vitest';
import { PLATFORM_ID } from '@angular/core';

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

    // Prevent script execution in JSDOM for all tests by mocking appendChild
    vi.spyOn(document.head, 'appendChild').mockImplementation((node: Node) => node);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    ['google-analytics-script', 'google-analytics-init'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.remove();
    });
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should initialize Google Analytics script', () => {
    const createElementSpy = vi.spyOn(document, 'createElement');
    const appendChildSpy = vi.spyOn(document.head, 'appendChild');

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

  it('should not throw if gtag is undefined during navigation', () => {
    service.initialize();

    // Unset gtag
    (window as any).gtag = undefined;

    const navigationEnd = new NavigationEnd(1, '/test-url', '/test-url');
    // Should not throw
    routerEventsSubject.next(navigationEnd);
  });

  it('should not initialize on server platform', () => {
    // Re-configure for server platform
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        GoogleAnalyticsService,
        { provide: Router, useValue: { events: new Subject() } },
        { provide: PLATFORM_ID, useValue: 'server' }
      ]
    });
    const serverService = TestBed.inject(GoogleAnalyticsService);
    // Spy again because TestBed reset might rely on fresh injectors, but document is global.
    // However, vi.restoreAllMocks() in afterEach removes the spy. 
    // We need to re-spy or rely on proper cleanup.
    // Since we restore mocks in afterEach, we must re-spy here or remove restoreAllMocks.
    const appendChildSpy = vi.spyOn(document.head, 'appendChild').mockImplementation((node: Node) => node);

    serverService.initialize();

    expect(appendChildSpy).not.toHaveBeenCalled();
  });

  it('should return early if scripts already exist', () => {
    // Reset state for this test
    (service as any).isInitialized = false;

    // Mock getElementById to simulate scripts already existing in DOM
    const getSpy = vi.spyOn(document, 'getElementById').mockReturnValue({} as HTMLElement);
    const appendChildSpy = vi.spyOn(document.head, 'appendChild');

    service.initialize();

    expect(appendChildSpy).not.toHaveBeenCalled();
    getSpy.mockRestore();
  });

  it('should return early from loadScript/initGtag if elements exist by ID', () => {
    // Reset state
    (service as any).isInitialized = false;

    // Mock getElementById to return something for both script IDs
    const getSpy = vi.spyOn(document, 'getElementById').mockImplementation((id: string) => {
      if (id === 'google-analytics-script' || id === 'google-analytics-init') {
        return {} as HTMLElement;
      }
      return null;
    });

    const appendChildSpy = vi.spyOn(document.head, 'appendChild');
    service.initialize();

    expect(appendChildSpy).not.toHaveBeenCalled();
    getSpy.mockRestore();
  });
});
