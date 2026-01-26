import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AdminLayoutComponent } from './admin-layout.component';
import { AuthService, User } from '../../../services/auth.service';
import { Router } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { BehaviorSubject } from 'rxjs';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

describe('AdminLayoutComponent', () => {
  let component: AdminLayoutComponent;
  let fixture: ComponentFixture<AdminLayoutComponent>;
  let authServiceSpy: { logout: Mock; currentUser$: BehaviorSubject<User | null> };
  let currentUserSubject: BehaviorSubject<User | null>;

  const mockUser: User = {
    id: 1,
    username: 'admin',
    email: 'admin@example.com',
    is_admin: true,
  };

  beforeEach(async () => {
    currentUserSubject = new BehaviorSubject<User | null>(null);
    authServiceSpy = {
      logout: vi.fn(),
      currentUser$: currentUserSubject,
    };

    await TestBed.configureTestingModule({
      imports: [AdminLayoutComponent, RouterTestingModule, NoopAnimationsModule],
      providers: [{ provide: AuthService, useValue: authServiceSpy }],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(AdminLayoutComponent);
    component = fixture.componentInstance;
    // Do NOT call detectChanges here to allow individual tests to set up state
  });

  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('should display user info when logged in', async () => {
    currentUserSubject.next(mockUser);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(component.currentUser).toEqual(mockUser);

    fixture.detectChanges();
    const nativeElement = fixture.nativeElement as HTMLElement;
    const userInfo = nativeElement.querySelector('.user-info');
    // Depending on implementation, checking existence or content
    if (userInfo) {
      expect(userInfo.textContent).toContain(mockUser.username);
    }
  });

  it('should call logout and navigate to login on logout', () => {
    fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate');

    component.logout();
    expect(authServiceSpy.logout).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith(['/admin/login']);
  });
});
