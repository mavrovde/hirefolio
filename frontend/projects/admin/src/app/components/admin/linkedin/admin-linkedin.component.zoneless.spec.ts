/**
 * Zoneless repaint regression pin (#276) — see the header of
 * admin-layout.component.zoneless.spec.ts for why this TestBed opts into
 * `provideZonelessChangeDetection()` instead of relying on the zone.js that
 * src/test-setup.ts loads.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { CommonModule } from '@angular/common';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import { AdminLinkedinComponent } from './admin-linkedin.component';
import { LinkedinService } from '../../../services/linkedin.service';

class MockLinkedinService {
  loggedIn = false;
  async syncProfile() {
    return {};
  }
  async getPosts() {
    return [];
  }
  async transferPost() {
    return { id: 0, message: '' };
  }
  async getStatus() {
    return { logged_in: this.loggedIn };
  }
  async login() {
    return {};
  }
}

describe('AdminLinkedinComponent (zoneless repaint)', () => {
  let component: AdminLinkedinComponent;
  let fixture: ComponentFixture<AdminLinkedinComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminLinkedinComponent, CommonModule],
      providers: [
        provideZonelessChangeDetection(),
        { provide: LinkedinService, useClass: MockLinkedinService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminLinkedinComponent);
    component = fixture.componentInstance;
    host = fixture.nativeElement as HTMLElement;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // #290 review round 1 found this one LIVE, in a file this PR already edits:
  // `checkLoginStatus` is the only async method here without a
  // `finally { detectChanges() }`, and it runs from ngOnInit. A logged-in
  // operator saw "🔴 Not Connected" plus the login form, forever.
  //
  // Three layers were blind to it and that is the point of pinning it here:
  // the cd-safety lint does not follow `await` (its documented #234 gap), the
  // other unit specs bundle zone.js so change detection fires for them, and the
  // e2e spec always mocks the initial status as logged_in: false.
  it('repaints the connected state after ngOnInit resolves (no manual CD)', async () => {
    const svc = TestBed.inject(LinkedinService) as unknown as MockLinkedinService;
    svc.loggedIn = true;

    fixture.detectChanges();        // initial render + ngOnInit
    await fixture.whenStable();     // let checkLoginStatus' await resolve

    // Deliberately NO detectChanges() after this point: the component must
    // repaint itself, exactly as every sibling async method here already does.
    expect(component.isLoggedIn).toBe(true);
    expect(host.textContent).toContain('🟢 Connected');
    expect(host.textContent).not.toContain('🔴 Not Connected');
    expect(host.querySelector('.auth-form')).toBeNull();
  });

  it('repaints away the status bar when the 5s auto-clear timer fires', () => {
    component.statusMessage = 'Imported 3 posts.';
    fixture.detectChanges();
    expect(host.querySelector('.status-bar')?.textContent).toContain('Imported 3 posts.');

    // Fake timers cover only the auto-clear window; the render above is real.
    vi.useFakeTimers();
    component.clearMessageAfterDelay();
    vi.advanceTimersByTime(5000);

    // Deliberately NO detectChanges() here: the component must repaint itself,
    // otherwise the operator keeps reading a stale status line forever.
    expect(component.statusMessage).toBe('');
    expect(host.querySelector('.status-bar')).toBeNull();
  });
});
