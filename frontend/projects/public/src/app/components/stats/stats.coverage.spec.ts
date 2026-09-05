import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { SystemStatsComponent } from './stats.component';
import { StatsService } from '@mavrov/shared';
import { Router, NavigationEnd } from '@angular/router';
import { Subject, of } from 'rxjs';
import { SiteConfigService } from '../../services/site-config.service';

const MOCK_SITE_CONFIG_PROVIDER = {
  provide: SiteConfigService,
  useValue: {
    config$: of({
      siteName: 'mavrov.de', siteUrl: 'https://mavrov.de',
      ownerName: 'Sergii Mavrov', ownerHeadline: 'Principal Software Engineer',
      ownerDescription: 'Desc.', socialLinks: [],
      analyticsId: '',
    }),
  },
};
import { PLATFORM_ID } from '@angular/core';
import { TranslatePipe } from '@mavrov/shared';
import { MockTranslatePipe } from '@mavrov/shared/testing';

describe('SystemStatsComponent visibility + uptime-fallback branches', () => {
  let component: SystemStatsComponent;
  let fixture: ComponentFixture<SystemStatsComponent>;
  let routerEvents: Subject<any>;

  beforeEach(async () => {
    vi.useFakeTimers();
    routerEvents = new Subject<any>();
    await TestBed.configureTestingModule({
      imports: [SystemStatsComponent],
      providers: [
        MOCK_SITE_CONFIG_PROVIDER,
        { provide: PLATFORM_ID, useValue: 'browser' },
        { provide: Router, useValue: { url: '/', events: routerEvents.asObservable() } },
        {
          provide: StatsService,
          useValue: {
            getPublicStats: vi.fn().mockReturnValue({
              subscribe: (observer: any) => {
                // No start_time -> exercises the else branch (line 66)
                observer.next({
                  visitor_ip: '10.0.0.1',
                  backend_version: '2.0.0',
                  uptime: '12:34:56',
                });
                return { unsubscribe: () => {} };
              },
            }),
          },
        },
      ],
    })
      .overrideComponent(SystemStatsComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(SystemStatsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('uses uptime fallback when no start_time is provided (line 66)', () => {
    expect(component.uptime).toBe('12:34:56');
  });

  it('hides on admin route change and shows on public route change (lines 44-47, 52-53)', () => {
    expect(component.isVisible).toBe(true);

    routerEvents.next(new NavigationEnd(1, '/admin/dashboard', '/admin/dashboard'));
    expect(component.isVisible).toBe(false);

    routerEvents.next(new NavigationEnd(2, '/blog', '/blog'));
    expect(component.isVisible).toBe(true);
  });

  it('handles NavigationEnd without urlAfterRedirects (url fallback branch)', () => {
    const ev: any = new NavigationEnd(3, '/admin', '');
    // Force urlAfterRedirects falsy to hit the `|| event.url` branch
    Object.defineProperty(ev, 'urlAfterRedirects', { value: '', configurable: true });
    routerEvents.next(ev);
    expect(component.isVisible).toBe(false);
  });
});

describe('SystemStatsComponent uptime counter (start_time path + days format)', () => {
  let component: SystemStatsComponent;
  let fixture: ComponentFixture<SystemStatsComponent>;

  beforeEach(async () => {
    vi.useFakeTimers();
    // 2 days, 3 hours, 4 minutes, 5 seconds ago
    const past = Date.now() - (2 * 86400 + 3 * 3600 + 4 * 60 + 5) * 1000;
    await TestBed.configureTestingModule({
      imports: [SystemStatsComponent],
      providers: [
        MOCK_SITE_CONFIG_PROVIDER,
        { provide: PLATFORM_ID, useValue: 'browser' },
        { provide: Router, useValue: { url: '/', events: new Subject().asObservable() } },
        {
          provide: StatsService,
          useValue: {
            getPublicStats: vi.fn().mockReturnValue({
              subscribe: (observer: any) => {
                observer.next({
                  visitor_ip: '1.2.3.4',
                  backend_version: '3.0.0',
                  uptime: '0:00:00',
                  start_time: new Date(past).toISOString(),
                });
                return { unsubscribe: () => {} };
              },
            }),
          },
        },
      ],
    })
      .overrideComponent(SystemStatsComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(SystemStatsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('formats uptime with a days prefix and clears an existing interval on restart', () => {
    // Initial call from fetchPublicStats already computed uptime with days
    expect(component.uptime).toMatch(/^2d /);

    const clearSpy = vi.spyOn(window, 'clearInterval');
    // Calling startUptimeCounter again should clear the existing interval (lines 86-87)
    (component as any).startUptimeCounter();
    expect(clearSpy).toHaveBeenCalled();
  });
});
