import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { RouterTestingModule } from '@angular/router/testing';
import { RouterOutlet } from '@angular/router';
import { By } from '@angular/platform-browser';
import { GoogleAnalyticsService } from './services/google-analytics.service';
import { ViewportScroller } from '@angular/common';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Component } from '@angular/core';
import { SeoService } from './services/seo.service';
import { DomSanitizer } from '@angular/platform-browser';
import { BehaviorSubject } from 'rxjs';
import { CookieConsentComponent } from './components/cookie-consent/cookie-consent.component';
import { SystemStatsComponent } from './components/stats/stats.component';

@Component({
  selector: 'app-cookie-consent',
  standalone: true,
  template: ''
})
class MockCookieConsentComponent { }

@Component({
  selector: 'app-system-stats',
  standalone: true,
  template: ''
})
class MockSystemStatsComponent { }

describe('AppComponent', () => {
  let component: AppComponent;
  let fixture: ComponentFixture<AppComponent>;
  let mockSeoService: { schemaSubject: BehaviorSubject<any>, jsonLdSchema$: any };
  let mockSanitizer: any;

  beforeEach(async () => {
    const mockGaService = {
      initialize: vi.fn(),
    };

    mockSeoService = {
      schemaSubject: new BehaviorSubject<any>(null),
      get jsonLdSchema$() { return this.schemaSubject.asObservable(); }
    };

    mockSanitizer = {
      bypassSecurityTrustHtml: vi.fn().mockReturnValue('safe-html')
    };

    await TestBed.configureTestingModule({
      imports: [AppComponent, RouterTestingModule],
      providers: [
        { provide: GoogleAnalyticsService, useValue: mockGaService },
        { provide: ViewportScroller, useValue: { setOffset: vi.fn() } },
        { provide: SeoService, useValue: mockSeoService },
        { provide: DomSanitizer, useValue: mockSanitizer }
      ]
    })
      .overrideComponent(AppComponent, {
        remove: { imports: [CookieConsentComponent, SystemStatsComponent] },
        add: { imports: [MockCookieConsentComponent, MockSystemStatsComponent] }
      })
      .compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the app', () => {
    expect(component).toBeTruthy();
  });

  it('should have a router-outlet', () => {
    const debugElement = fixture.debugElement.query(By.directive(RouterOutlet));
    expect(debugElement).toBeTruthy();
  });

  it('should return null when schema is falsy', async () => {
    mockSeoService.schemaSubject.next(null);
    return new Promise<void>((resolve) => {
      component.jsonLd$?.subscribe((val: any) => {
        expect(val).toBeNull();
        resolve();
      });
    });
  });

  it('should bypass security trust html when schema is provided', async () => {
    mockSeoService.schemaSubject.next({ "@context": "https://schema.org" });
    return new Promise<void>((resolve) => {
      component.jsonLd$?.subscribe((val: any) => {
        expect(mockSanitizer.bypassSecurityTrustHtml).toHaveBeenCalledWith(
          '<script type="application/ld+json">{\n  "@context": "https://schema.org"\n}</script>'
        );
        expect(val).toBe('safe-html');
        resolve();
      });
    });
  });
});
