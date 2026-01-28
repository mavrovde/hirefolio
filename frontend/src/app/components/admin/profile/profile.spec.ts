import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ProfileComponent } from './profile';
import { AuthService } from '../../../services/auth.service';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { vi } from 'vitest';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let fixture: ComponentFixture<ProfileComponent>;
  let authServiceMock: any;
  let currentUserSubject: BehaviorSubject<any>;

  beforeEach(async () => {
    currentUserSubject = new BehaviorSubject({
      id: 1,
      username: 'testadmin',
      email: 'admin@test.com',
      is_admin: true
    });

    authServiceMock = {
      changePassword: vi.fn().mockReturnValue(of(void 0)),
      currentUser$: currentUserSubject.asObservable()
    };

    await TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [
        provideZonelessChangeDetection(),
        { provide: AuthService, useValue: authServiceMock }
      ]
    })
      .compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    fixture.detectChanges(); // Initial render
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  // LOGIC TESTS: Verify internal state ONLY. Do NOT call fixture.detectChanges().
  it('should handle successful password change (logic)', () => {
    vi.useFakeTimers();

    component.oldPassword = 'old';
    component.newPassword = 'new';

    component.onSubmit();

    expect(component.loading).toBe(true);
    expect(component.statusMessage).toBe('Requesting password change...');

    vi.advanceTimersByTime(500);
    // Phase 1 + Request success
    expect(component.statusMessage).toBe('Password updated successfully.');

    vi.advanceTimersByTime(500);
    // Phase 3
    expect(authServiceMock.changePassword).toHaveBeenCalledWith('old', 'new');
    expect(component.message).toBe('Password changed successfully.');
    expect(component.loading).toBe(false);

    vi.advanceTimersByTime(5000);
    // Phase 4
    expect(component.message).toBe('');

    vi.useRealTimers();
  });

  it('should handle incorrect old password (logic)', () => {
    vi.useFakeTimers();
    component.oldPassword = 'wrong';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(
      throwError(() => ({
        status: 400,
        error: { detail: 'Incorrect old password' }
      }))
    );

    component.onSubmit();
    vi.advanceTimersByTime(500);

    expect(component.error).toBe('Incorrect old password');
    expect(component.loading).toBe(false);

    vi.useRealTimers();
  });

  it('should handle server error (logic)', () => {
    vi.useFakeTimers();
    component.oldPassword = 'old';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(
      throwError(() => ({
        status: 500,
        error: { detail: 'Internal Server Error' }
      }))
    );

    component.onSubmit();
    vi.advanceTimersByTime(500);

    expect(component.error).toBe('Internal Server Error');
    expect(component.loading).toBe(false);

    vi.useRealTimers();
  });



  it('should display user details (UI)', () => {
    // fixture.detectChanges() was called in beforeEach, so view should be ready
    const details = fixture.nativeElement.querySelector('.user-details');
    expect(details?.textContent).toContain('testadmin');
    expect(details?.textContent).toContain('admin@test.com');
  });
});
