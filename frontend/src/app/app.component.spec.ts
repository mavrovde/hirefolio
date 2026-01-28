import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { RouterTestingModule } from '@angular/router/testing';
import { RouterOutlet } from '@angular/router';
import { By } from '@angular/platform-browser';
import { GoogleAnalyticsService } from './services/google-analytics.service';
import { ViewportScroller } from '@angular/common';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Component } from '@angular/core';
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

  beforeEach(async () => {
    const mockGaService = {
      initialize: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [AppComponent, RouterTestingModule],
      providers: [
        { provide: GoogleAnalyticsService, useValue: mockGaService },
        { provide: ViewportScroller, useValue: { setOffset: vi.fn() } }
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
});
