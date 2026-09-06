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
    return { logged_in: false };
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
