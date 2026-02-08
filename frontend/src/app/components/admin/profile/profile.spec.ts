import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ProfileComponent } from './profile';
import { AuthService } from '../../../services/auth.service';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { MockTranslatePipe } from '../../../testing/mock-translate.pipe';
import { TranslatePipe } from '../../../pipes/translate.pipe';

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
      imports: [ProfileComponent, MockTranslatePipe],
      providers: [
        provideZonelessChangeDetection(),
        { provide: AuthService, useValue: authServiceMock }
      ]
    })
      .overrideComponent(ProfileComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] }
      })
      .compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    fixture.detectChanges(); // Initial render
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  // LOGIC TESTS: Verify internal state ONLY.
  it('should handle successful password change (logic)', () => {
    vi.useFakeTimers();

    component.oldPassword = 'old';
    component.newPassword = 'new';

    component.onSubmit();

    expect(component.loading).toBe(false);
    // No more "Requesting..." phase wait, service is called immediately

    // Simulate service response
    expect(authServiceMock.changePassword).toHaveBeenCalledWith('old', 'new');
    expect(component.message).toBe('ADMIN.PASSWORD_CHANGED_SUCCESS');

    // Test auto-clear
    vi.advanceTimersByTime(5000);
    expect(component.message).toBe('');

    vi.useRealTimers();
  });

  it('should handle incorrect old password (logic)', () => {
    component.oldPassword = 'wrong';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(
      throwError(() => ({
        status: 400,
        error: { detail: 'Incorrect old password' }
      }))
    );

    component.onSubmit();

    expect(component.error).toBe('Incorrect old password');
    expect(component.loading).toBe(false);
  });

  it('should handle server error (logic)', () => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(
      throwError(() => ({
        status: 500,
        error: { detail: 'Internal Server Error' }
      }))
    );

    component.onSubmit();

    expect(component.error).toBe('Internal Server Error');
    expect(component.loading).toBe(false);
  });



  it('should display user details (UI)', () => {
    // fixture.detectChanges() was called in beforeEach, so view should be ready
    const details = fixture.nativeElement.querySelector('.user-details');
    expect(details?.textContent).toContain('testadmin');
    expect(details?.textContent).toContain('admin@test.com');
  });
});
