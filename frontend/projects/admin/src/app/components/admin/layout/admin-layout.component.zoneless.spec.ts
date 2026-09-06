/**
 * Zoneless repaint regression pins (#276).
 *
 * The admin app ships no zone.js (angular.json has no `polyfills` entry for the
 * admin project) and provides no provideZoneChangeDetection(), so Angular's
 * ZONELESS_ENABLED default (`() => true`) applies: it runs zoneless in the
 * browser. The ordinary specs bundle zone.js via src/test-setup.ts, which is
 * exactly why they cannot see a missing repaint — so this file opts the TestBed
 * into `provideZonelessChangeDetection()` and drives change detection ONLY
 * through `whenStable()` (never `detectChanges()`, which would force a repaint
 * the component never asked for and hide the bug).
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { RouterTestingModule } from '@angular/router/testing';
import { BehaviorSubject } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { AdminLayoutComponent } from './admin-layout.component';
import { AuthService, User } from '../../../services/auth.service';

const mockUser: User = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  is_admin: true,
};

describe('AdminLayoutComponent (zoneless repaint)', () => {
  let fixture: ComponentFixture<AdminLayoutComponent>;
  let currentUser$: BehaviorSubject<User | null>;

  beforeEach(async () => {
    currentUser$ = new BehaviorSubject<User | null>(null);
    await TestBed.configureTestingModule({
      imports: [AdminLayoutComponent, RouterTestingModule],
      providers: [
        provideZonelessChangeDetection(),
        {
          provide: AuthService,
          useValue: { logout: vi.fn(), currentUser$ },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AdminLayoutComponent);
  });

  it('repaints the sidebar username on an emission that arrives after first render', async () => {
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('.user-info')).toBeNull();

    currentUser$.next(mockUser);
    await fixture.whenStable();

    expect(host.querySelector('.user-info')?.textContent).toContain('admin');
  });

  it('repaints away the username on logout emission', async () => {
    currentUser$.next(mockUser);
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('.user-info')).not.toBeNull();

    currentUser$.next(null);
    await fixture.whenStable();

    expect(host.querySelector('.user-info')).toBeNull();
  });
});
